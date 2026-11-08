"""
binance_client.py — Cliente de la API pública de Binance Spot.

Condición obligatoria del encargo: NO se descargan históricos a disco (ni ZIP,
ni CSV, ni Parquet). Todo se consulta vía HTTP y se procesa en memoria con
pandas DataFrames, liberados tras analizar cada símbolo.

Incluye: paginación automática de klines, control de límites de la API,
reintentos con backoff exponencial, y validación de continuidad temporal
(detección de huecos en las velas).
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Optional

import pandas as pd
import requests

from config import (
    BINANCE_DATA_API_BASE,
    BINANCE_SPOT_API_BASE,
    KLINES_LIMIT_PER_REQUEST,
    MAX_RETRIES,
    MIN_SLEEP_BETWEEN_REQUESTS,
    REQUEST_TIMEOUT_SECONDS,
    RETRY_BACKOFF_BASE_SECONDS,
)
from src.logging_utils import get_logger

logger = get_logger(__name__)

KLINE_COLUMNS = [
    "open_time", "open", "high", "low", "close", "volume", "close_time",
    "quote_asset_volume", "num_trades", "taker_buy_base_volume",
    "taker_buy_quote_volume", "ignore",
]

TIMEFRAME_TO_BINANCE_INTERVAL = {"15m": "15m", "1h": "1h", "4h": "4h", "1d": "1d"}
TIMEFRAME_MS = {"15m": 15 * 60_000, "1h": 60 * 60_000, "4h": 4 * 60 * 60_000, "1d": 24 * 60 * 60_000}


@dataclass
class DataCoverageRecord:
    symbol: str
    timeframe: str
    requested_start_ms: int
    requested_end_ms: int
    candles_received: int
    gaps_detected: int
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "requested_start": pd.to_datetime(self.requested_start_ms, unit="ms"),
            "requested_end": pd.to_datetime(self.requested_end_ms, unit="ms"),
            "candles_received": self.candles_received,
            "gaps_detected": self.gaps_detected,
            "error": self.error or "",
        }


class BinanceClient:
    """Cliente mínimo, sin estado persistente en disco."""

    def __init__(self, session: Optional[requests.Session] = None):
        self.session = session or requests.Session()

    # -- infraestructura HTTP ------------------------------------------------
    def _get(self, base_url: str, path: str, params: dict) -> list | dict:
        last_exc = None
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                resp = self.session.get(
                    f"{base_url}{path}", params=params, timeout=REQUEST_TIMEOUT_SECONDS
                )
                if resp.status_code == 429 or resp.status_code == 418:
                    wait = RETRY_BACKOFF_BASE_SECONDS * (2 ** attempt)
                    logger.warning(f"Rate limit ({resp.status_code}) en {path}. Esperando {wait:.1f}s")
                    time.sleep(wait)
                    continue
                resp.raise_for_status()
                time.sleep(MIN_SLEEP_BETWEEN_REQUESTS)
                return resp.json()
            except requests.RequestException as exc:
                last_exc = exc
                wait = RETRY_BACKOFF_BASE_SECONDS * (2 ** (attempt - 1))
                logger.warning(f"Error de red en {path} (intento {attempt}/{MAX_RETRIES}): {exc}. Reintentando en {wait:.1f}s")
                time.sleep(wait)
        raise RuntimeError(f"Fallaron {MAX_RETRIES} intentos contra {path}: {last_exc}")

    # -- universo -------------------------------------------------------------
    def get_exchange_info(self) -> dict:
        return self._get(BINANCE_SPOT_API_BASE, "/api/v3/exchangeInfo", {})

    def get_24h_tickers(self) -> list:
        return self._get(BINANCE_SPOT_API_BASE, "/api/v3/ticker/24hr", {})

    # -- velas (en memoria, sin persistir a disco) -----------------------------
    def get_klines_dataframe(
        self, symbol: str, timeframe: str, start_ms: int, end_ms: int
    ) -> tuple[pd.DataFrame, DataCoverageRecord]:
        """Descarga paginada de klines hacia un DataFrame en memoria.

        No escribe nada a disco. Valida continuidad temporal al final.
        """
        interval = TIMEFRAME_TO_BINANCE_INTERVAL[timeframe]
        step_ms = TIMEFRAME_MS[timeframe]
        rows: list = []
        cursor = start_ms
        error_msg = None
        try:
            while cursor < end_ms:
                batch = self._get(
                    BINANCE_DATA_API_BASE,
                    "/api/v3/klines",
                    {
                        "symbol": symbol,
                        "interval": interval,
                        "startTime": cursor,
                        "endTime": end_ms,
                        "limit": KLINES_LIMIT_PER_REQUEST,
                    },
                )
                if not batch:
                    break
                rows.extend(batch)
                last_open_time = batch[-1][0]
                next_cursor = last_open_time + step_ms
                if next_cursor <= cursor:
                    break  # evita loops infinitos si la API no avanza
                cursor = next_cursor
                if len(batch) < KLINES_LIMIT_PER_REQUEST:
                    break  # ya no hay más datos disponibles
        except RuntimeError as exc:
            error_msg = str(exc)

        if not rows:
            record = DataCoverageRecord(symbol, timeframe, start_ms, end_ms, 0, 0, error_msg or "sin_datos")
            return pd.DataFrame(columns=["open_time", "open", "high", "low", "close", "volume",
                                          "taker_buy_base_volume"]), record

        df = pd.DataFrame(rows, columns=KLINE_COLUMNS)
        df = df.drop_duplicates(subset="open_time").sort_values("open_time").reset_index(drop=True)
        numeric_cols = ["open", "high", "low", "close", "volume", "quote_asset_volume",
                         "taker_buy_base_volume", "taker_buy_quote_volume"]
        for col in numeric_cols:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        df["open_time"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)
        df["close_time"] = pd.to_datetime(df["close_time"], unit="ms", utc=True)

        # Validación de continuidad temporal: cuenta huecos mayores a 1 paso.
        deltas = df["open_time"].diff().dropna()
        expected = pd.Timedelta(milliseconds=step_ms)
        gaps = int((deltas > expected * 1.5).sum())

        record = DataCoverageRecord(
            symbol, timeframe, start_ms, end_ms, len(df), gaps, error_msg
        )
        return df[["open_time", "open", "high", "low", "close", "volume", "taker_buy_base_volume"]], record
