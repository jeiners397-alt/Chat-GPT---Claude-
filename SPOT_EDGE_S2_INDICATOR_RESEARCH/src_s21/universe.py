"""
universe.py (S2.1) — Corrige el sesgo retrospectivo de universo (sección 6
de la orden) y excluye activos no-cripto (stablecoins, fiat tokenizado,
acciones/ETFs tokenizados) detectados por la auditoría en el universo de S2.

Diseño en dos pasos (necesario porque la liquidez histórica solo puede
calcularse DESPUÉS de descargar velas, pero hay que decidir qué símbolos
descargar ANTES):

  Paso 1 (build_universe_candidates): filtro barato por metadatos de
  exchangeInfo (quoteAsset, estado, apalancados, duplicados, no-cripto) +
  prefiltro de liquidez usando el ticker 24h ACTUAL, solo para evitar
  descargar velas de símbolos obviamente inactivos (reduce llamadas a la
  API; no es el filtro final de inclusión).

  Paso 2 (finalize_universe_with_historical_liquidity): una vez descargadas
  las velas 1d de cada símbolo candidato para la ventana de análisis, se
  recalcula la liquidez como el volumen cotizado HISTÓRICO PROMEDIO real
  durante esa ventana (close*volume diario), y la inclusión final se decide
  con ese número — no con el ticker de "hoy". Esto corrige el sesgo
  retrospectivo señalado por la auditoría (sección 6, P1).

LIMITACIÓN DECLARADA EXPLÍCITAMENTE (exigido por la orden, sección 6):
la lista de símbolos candidatos del Paso 1 proviene de /exchangeInfo DE HOY.
Un par que existió y luego fue retirado/deslistado por Binance ANTES de la
fecha de esta ejecución no aparece en /exchangeInfo y por tanto no puede
entrar al universo, sin importar cuán líquido fue durante la ventana
histórica analizada. La API pública de Binance no expone un listado de
pares deslistados con historial completo, por lo que este sesgo de
supervivencia (survivorship bias) NO puede eliminarse por completo con las
fuentes de datos disponibles aquí. Se documenta en SURVIVORSHIP_BIAS_NOTE
dentro de UNIVERSE_EXCLUSIONS.csv / SUMMARY_S21.json.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from config_s21 import (
    LEVERAGED_TOKEN_SUFFIXES,
    MIN_AVG_DAILY_QUOTE_VOLUME_USDT,
    NON_CRYPTO_BASE_ASSETS,
    QUOTE_ASSET,
    TOKENIZED_EQUITY_BASE_ASSETS,
)
from src.binance_client import BinanceClient
from src.logging_utils import get_logger

logger = get_logger(__name__)

SURVIVORSHIP_BIAS_NOTE = (
    "El universo se construye a partir de /exchangeInfo en la fecha de ejecución. "
    "Pares deslistados por Binance antes de esa fecha no pueden incluirse, aunque "
    "hubieran sido líquidos durante la ventana histórica analizada. Este sesgo de "
    "supervivencia NO se elimina por completo con la API pública disponible; se "
    "declara como limitación conocida, no como defecto corregido."
)


@dataclass
class ExclusionRecord:
    symbol: str
    reason: str
    stage: str  # "metadatos" | "liquidez_historica"


def _is_leveraged_token(base_asset: str) -> bool:
    return any(base_asset.endswith(suffix) for suffix in LEVERAGED_TOKEN_SUFFIXES)


def _is_non_crypto(base_asset: str) -> bool:
    return base_asset in NON_CRYPTO_BASE_ASSETS or base_asset in TOKENIZED_EQUITY_BASE_ASSETS


def build_universe_candidates(
    client: BinanceClient, max_symbols: int = 0, symbols_override: tuple = ()
) -> tuple[list[str], list[ExclusionRecord]]:
    """Paso 1: filtro por metadatos + prefiltro barato de liquidez actual
    (solo para acotar qué descargar; la decisión final es el Paso 2)."""

    if symbols_override:
        logger.info(f"Universo forzado por configuración: {symbols_override}")
        return list(symbols_override), []

    exchange_info = client.get_exchange_info()
    tickers = {t["symbol"]: t for t in client.get_24h_tickers()}

    included: list[str] = []
    exclusions: list[ExclusionRecord] = []
    seen: set[str] = set()

    for s in exchange_info.get("symbols", []):
        symbol = s["symbol"]
        base_asset = s["baseAsset"]
        quote_asset = s["quoteAsset"]

        if quote_asset != QUOTE_ASSET:
            continue

        if not s.get("isSpotTradingAllowed", False):
            exclusions.append(ExclusionRecord(symbol, "No admite operaciones Spot", "metadatos"))
            continue
        if s.get("status") != "TRADING":
            exclusions.append(ExclusionRecord(symbol, f"Estado != TRADING ({s.get('status')})", "metadatos"))
            continue
        if _is_leveraged_token(base_asset):
            exclusions.append(ExclusionRecord(symbol, "Token apalancado (UP/DOWN/BULL/BEAR)", "metadatos"))
            continue
        if _is_non_crypto(base_asset):
            exclusions.append(ExclusionRecord(
                symbol,
                f"Activo base '{base_asset}' no representa una criptomoneda líquida tradicional "
                f"(stablecoin/fiat tokenizado/acción o ETF tokenizado) — excluido del universo cripto.",
                "metadatos",
            ))
            continue
        if symbol in seen:
            exclusions.append(ExclusionRecord(symbol, "Par duplicado", "metadatos"))
            continue

        ticker = tickers.get(symbol)
        if ticker is None:
            exclusions.append(ExclusionRecord(symbol, "Sin datos de ticker 24h (posible inválido)", "metadatos"))
            continue
        # Prefiltro barato (NO es la decisión final): usa un umbral laxo
        # (10% del umbral final) solo para evitar descargar velas de pares
        # evidentemente muertos.
        quote_volume_today = float(ticker.get("quoteVolume", 0.0))
        if quote_volume_today < MIN_AVG_DAILY_QUOTE_VOLUME_USDT * 0.10:
            exclusions.append(ExclusionRecord(
                symbol,
                f"Prefiltro: liquidez actual extremadamente baja ({quote_volume_today:,.0f} USDT); "
                f"candidato descartado antes de evaluar liquidez histórica.",
                "metadatos",
            ))
            continue

        seen.add(symbol)
        included.append(symbol)

    included.sort()
    if max_symbols and max_symbols > 0:
        omitted = included[max_symbols:]
        for sym in omitted:
            exclusions.append(ExclusionRecord(sym, "Omitido por límite --max-symbols (ejecución acotada)", "metadatos"))
        included = included[:max_symbols]

    logger.info(f"Candidatos tras filtro de metadatos: {len(included)}. Excluidos: {len(exclusions)}")
    return included, exclusions


def finalize_universe_with_historical_liquidity(
    daily_df_by_symbol: dict[str, pd.DataFrame],
    candidate_symbols: list[str],
) -> tuple[list[str], list[ExclusionRecord]]:
    """Paso 2: decisión FINAL de inclusión usando liquidez histórica real
    (promedio de close*volume diario durante la ventana de análisis
    efectivamente descargada), no el ticker de hoy. Corrige el P1 de la
    auditoría ('universo construido con liquidez retrospectiva/actual')."""
    included: list[str] = []
    exclusions: list[ExclusionRecord] = []

    for symbol in candidate_symbols:
        df = daily_df_by_symbol.get(symbol)
        if df is None or df.empty:
            exclusions.append(ExclusionRecord(
                symbol, "Sin velas diarias disponibles para calcular liquidez histórica.", "liquidez_historica",
            ))
            continue
        approx_quote_volume = (df["close"] * df["volume"])
        avg_quote_volume = float(approx_quote_volume.mean())
        if avg_quote_volume < MIN_AVG_DAILY_QUOTE_VOLUME_USDT:
            exclusions.append(ExclusionRecord(
                symbol,
                f"Liquidez histórica insuficiente: volumen cotizado diario promedio real en la "
                f"ventana analizada = {avg_quote_volume:,.0f} USDT < umbral "
                f"{MIN_AVG_DAILY_QUOTE_VOLUME_USDT:,.0f} USDT.",
                "liquidez_historica",
            ))
            continue
        included.append(symbol)

    logger.info(f"Universo final tras liquidez histórica: {len(included)} de {len(candidate_symbols)} candidatos.")
    return included, exclusions
