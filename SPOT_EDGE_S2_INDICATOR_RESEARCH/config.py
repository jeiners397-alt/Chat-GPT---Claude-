"""
config.py — Parámetros congelados de SPOT EDGE S2.

IMPORTANTE (sección 6 y 9 del encargo): todos los umbrales de clasificación y
parámetros de backtest quedan FIJADOS aquí, ANTES de ejecutar el análisis.
No deben modificarse después de observar resultados. Cualquier cambio futuro
debe hacerse en una nueva versión de este archivo, documentando el motivo.
"""

from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# 1. ENTORNO / API
# ---------------------------------------------------------------------------
BINANCE_DATA_API_BASE = "https://data-api.binance.vision"
BINANCE_SPOT_API_BASE = "https://api.binance.com"  # solo para exchangeInfo / 24h ticker
REQUEST_TIMEOUT_SECONDS = 20
MAX_RETRIES = 5
RETRY_BACKOFF_BASE_SECONDS = 1.5
KLINES_LIMIT_PER_REQUEST = 1000  # máximo permitido por Binance
# Pausa mínima entre requests para no exceder el límite de peso de la API pública.
MIN_SLEEP_BETWEEN_REQUESTS = 0.25

# ---------------------------------------------------------------------------
# 2. UNIVERSO DE INVESTIGACIÓN
# ---------------------------------------------------------------------------
QUOTE_ASSET = "USDT"
# Tokens apalancados / productos no elegibles -> excluidos por patrón de nombre.
LEVERAGED_TOKEN_SUFFIXES = ("UP", "DOWN", "BULL", "BEAR")
# Liquidez mínima: volumen cotizado (quoteVolume) promedio de las últimas 24h,
# expresado en USDT. Documentado y ajustable, pero congelado antes de ejecutar.
MIN_AVG_DAILY_QUOTE_VOLUME_USDT = 2_000_000.0
# Antigüedad mínima del par, en días, para admitirlo en el universo.
MIN_LISTING_AGE_DAYS = 90

# ---------------------------------------------------------------------------
# 3. PERÍODO HISTÓRICO Y TEMPORALIDADES
# ---------------------------------------------------------------------------
DEFAULT_LOOKBACK_DAYS = 60          # experimento principal
EXTENDED_LOOKBACK_DAYS = 180        # ampliación opcional vía --lookback-days
WARMUP_DAYS_BY_TIMEFRAME = {        # calentamiento adicional antes del inicio
    "15m": 10,
    "1h": 15,
    "4h": 30,
    "1d": 60,
}
TIMEFRAMES = ("15m", "1h", "4h", "1d")
TIMEFRAME_HOURS = {"15m": 0.25, "1h": 1.0, "4h": 4.0, "1d": 24.0}

# División cronológica exploración / comprobación (sección 9.3).
# Fracción del período total (sin contar warm-up) asignada a exploración;
# el resto es el tramo de comprobación "fuera de muestra".
EXPLORATION_FRACTION = 0.65

# ---------------------------------------------------------------------------
# 4. BACKTEST
# ---------------------------------------------------------------------------
INITIAL_CAPITAL_USDT = 100.0
COMMISSION_PCT_PER_SIDE = 0.0010     # 0.10 % por lado (escenario base)
SLIPPAGE_PCT_PER_SIDE = 0.0005       # 0.05 % por lado (escenario base)
# Escenario de sensibilidad a comisiones (sección 9.7): se corre una segunda
# pasada con comisión y slippage multiplicados por este factor.
COMMISSION_SENSITIVITY_MULTIPLIER = 2.0
MIN_NOTIONAL_USDT = 10.0             # tamaño mínimo de orden simulado
HOLDING_HORIZONS_HOURS = (4, 24, 72)  # horizontes de mantenimiento fijos

# ---------------------------------------------------------------------------
# 5. CLASIFICACIÓN (sección 6) — UMBRALES CONGELADOS
# ---------------------------------------------------------------------------
MIN_TRADES_FOR_CONCLUSIVE = 30       # por debajo => Categoría D (no concluyente)
MIN_SYMBOLS_FOR_CONCLUSIVE = 5

CATEGORY_A_THRESHOLDS = dict(
    expectancy_gt=0.0,
    profit_factor_gt=1.0,
    net_return_gt=0.0,
    require_consistency=True,   # positivo en exploración Y comprobación
)
CATEGORY_C_THRESHOLDS = dict(
    net_return_lt=-0.05,        # -5% o peor
    profit_factor_lt=0.8,
)
# Todo lo que no cae en A ni C, con muestra suficiente, cae en B.

# ---------------------------------------------------------------------------
# 6. TOP GAINERS
# ---------------------------------------------------------------------------
TOP_GAINERS_N = 10                   # "top N" por variación diaria
TOP_GAINER_FORWARD_WINDOW_HOURS = 24  # ventana para comprobar si hubo Top Gainer

# ---------------------------------------------------------------------------
# 7. SALIDAS
# ---------------------------------------------------------------------------
RESULTS_DIR_NAME = "RESULTADOS_SPOT_EDGE_S2"


@dataclass
class RunConfig:
    """Configuración de una ejecución concreta (puede sobreescribirse por CLI)."""

    lookback_days: int = DEFAULT_LOOKBACK_DAYS
    timeframes: tuple = TIMEFRAMES
    horizons_hours: tuple = HOLDING_HORIZONS_HOURS
    initial_capital_usdt: float = INITIAL_CAPITAL_USDT
    commission_pct_per_side: float = COMMISSION_PCT_PER_SIDE
    slippage_pct_per_side: float = SLIPPAGE_PCT_PER_SIDE
    max_symbols: int = 0  # 0 = sin límite; >0 útil para pruebas rápidas / CI
    run_commission_sensitivity: bool = True
    results_dir: str = RESULTS_DIR_NAME
    symbols_override: tuple = field(default_factory=tuple)
