"""
universe.py — Selección del universo de pares Binance Spot/USDT.

Registra TODOS los símbolos excluidos y su motivo (sección 2 del encargo).
No selecciona únicamente criptomonedas con ganancias recientes: el filtro de
liquidez se aplica sobre volumen, no sobre rendimiento.
"""

from __future__ import annotations

from dataclasses import dataclass

from config import (
    LEVERAGED_TOKEN_SUFFIXES,
    MIN_AVG_DAILY_QUOTE_VOLUME_USDT,
    QUOTE_ASSET,
)

# Nota sobre MIN_LISTING_AGE_DAYS (config.py): la antigüedad mínima de listado
# no se verifica aquí contra un endpoint dedicado (Binance no expone la fecha
# de listado en /exchangeInfo). Se aplica de forma indirecta en la etapa de
# descarga de velas: un símbolo sin suficiente histórico para cubrir
# warm-up + lookback queda documentado como cobertura insuficiente en
# DATA_COVERAGE.csv y sus indicadores quedan sin señales utilizables.
from src.binance_client import BinanceClient
from src.logging_utils import get_logger

logger = get_logger(__name__)


@dataclass
class ExclusionRecord:
    symbol: str
    reason: str


def _is_leveraged_token(base_asset: str) -> bool:
    return any(base_asset.endswith(suffix) for suffix in LEVERAGED_TOKEN_SUFFIXES)


def build_universe(
    client: BinanceClient, max_symbols: int = 0, symbols_override: tuple = ()
) -> tuple[list[str], list[ExclusionRecord]]:
    """Devuelve (símbolos_admitidos, exclusiones_documentadas)."""

    if symbols_override:
        logger.info(f"Universo forzado por configuración: {symbols_override}")
        return list(symbols_override), []

    exchange_info = client.get_exchange_info()
    tickers = {t["symbol"]: t for t in client.get_24h_tickers()}

    included: list[str] = []
    exclusions: list[ExclusionRecord] = []
    seen_base_assets: set[str] = set()

    for s in exchange_info.get("symbols", []):
        symbol = s["symbol"]
        base_asset = s["baseAsset"]
        quote_asset = s["quoteAsset"]

        if quote_asset != QUOTE_ASSET:
            continue  # no es parte del universo USDT; no se registra como "exclusión"

        if not s.get("isSpotTradingAllowed", False):
            exclusions.append(ExclusionRecord(symbol, "No admite operaciones Spot"))
            continue

        if s.get("status") != "TRADING":
            exclusions.append(ExclusionRecord(symbol, f"Estado != TRADING ({s.get('status')})"))
            continue

        if _is_leveraged_token(base_asset):
            exclusions.append(ExclusionRecord(symbol, "Token apalancado (UP/DOWN/BULL/BEAR)"))
            continue

        if symbol in seen_base_assets:
            exclusions.append(ExclusionRecord(symbol, "Par duplicado"))
            continue

        ticker = tickers.get(symbol)
        if ticker is None:
            exclusions.append(ExclusionRecord(symbol, "Sin datos de ticker 24h (posible inválido)"))
            continue

        quote_volume = float(ticker.get("quoteVolume", 0.0))
        if quote_volume < MIN_AVG_DAILY_QUOTE_VOLUME_USDT:
            exclusions.append(
                ExclusionRecord(
                    symbol,
                    f"Liquidez insuficiente: quoteVolume 24h={quote_volume:,.0f} USDT "
                    f"< umbral {MIN_AVG_DAILY_QUOTE_VOLUME_USDT:,.0f} USDT",
                )
            )
            continue

        seen_base_assets.add(symbol)
        included.append(symbol)

    included.sort()
    if max_symbols and max_symbols > 0:
        omitted = included[max_symbols:]
        for sym in omitted:
            exclusions.append(ExclusionRecord(sym, "Omitido por límite --max-symbols (ejecución acotada)"))
        included = included[:max_symbols]

    logger.info(f"Universo admitido: {len(included)} símbolos. Excluidos documentados: {len(exclusions)}")
    return included, exclusions
