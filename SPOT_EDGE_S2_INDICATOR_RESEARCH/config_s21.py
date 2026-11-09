"""
config_s21.py — Parámetros congelados de SPOT EDGE S2.1.

No modifica config.py (S2 debe seguir siendo reproducible con sus propios
parámetros). Importa de config.py todo lo que NO cambió, y define aquí
explícitamente todo lo que S2.1 corrige o añade, documentando el motivo
de cada cambio respecto a S2.

IMPORTANTE: igual que en S2, estos umbrales quedan FIJADOS antes de
ejecutar el análisis y no se ajustan después de observar resultados.
"""

from dataclasses import dataclass, field

import config as config_s2  # S2 original, solo para reutilizar lo no-corregido

# ---------------------------------------------------------------------------
# 1. Heredado sin cambios de S2
# ---------------------------------------------------------------------------
BINANCE_DATA_API_BASE = config_s2.BINANCE_DATA_API_BASE
BINANCE_SPOT_API_BASE = config_s2.BINANCE_SPOT_API_BASE
REQUEST_TIMEOUT_SECONDS = config_s2.REQUEST_TIMEOUT_SECONDS
MAX_RETRIES = config_s2.MAX_RETRIES
RETRY_BACKOFF_BASE_SECONDS = config_s2.RETRY_BACKOFF_BASE_SECONDS
KLINES_LIMIT_PER_REQUEST = config_s2.KLINES_LIMIT_PER_REQUEST
MIN_SLEEP_BETWEEN_REQUESTS = config_s2.MIN_SLEEP_BETWEEN_REQUESTS

QUOTE_ASSET = config_s2.QUOTE_ASSET
LEVERAGED_TOKEN_SUFFIXES = config_s2.LEVERAGED_TOKEN_SUFFIXES

TIMEFRAMES = config_s2.TIMEFRAMES
TIMEFRAME_HOURS = config_s2.TIMEFRAME_HOURS
WARMUP_DAYS_BY_TIMEFRAME = config_s2.WARMUP_DAYS_BY_TIMEFRAME
DEFAULT_LOOKBACK_DAYS = config_s2.DEFAULT_LOOKBACK_DAYS
EXTENDED_LOOKBACK_DAYS = config_s2.EXTENDED_LOOKBACK_DAYS
EXPLORATION_FRACTION = config_s2.EXPLORATION_FRACTION

INITIAL_CAPITAL_USDT = config_s2.INITIAL_CAPITAL_USDT
COMMISSION_PCT_PER_SIDE = config_s2.COMMISSION_PCT_PER_SIDE
SLIPPAGE_PCT_PER_SIDE = config_s2.SLIPPAGE_PCT_PER_SIDE
MIN_NOTIONAL_USDT = config_s2.MIN_NOTIONAL_USDT
HOLDING_HORIZONS_HOURS = config_s2.HOLDING_HORIZONS_HOURS

MIN_TRADES_FOR_CONCLUSIVE = config_s2.MIN_TRADES_FOR_CONCLUSIVE
MIN_SYMBOLS_FOR_CONCLUSIVE = config_s2.MIN_SYMBOLS_FOR_CONCLUSIVE
CATEGORY_A_THRESHOLDS = dict(config_s2.CATEGORY_A_THRESHOLDS)
CATEGORY_C_THRESHOLDS = dict(config_s2.CATEGORY_C_THRESHOLDS)

# ---------------------------------------------------------------------------
# 2. Sensibilidad a costos — auditoría pide también 3x (no solo 2x)
# ---------------------------------------------------------------------------
COMMISSION_SENSITIVITY_MULTIPLIERS = (1.0, 2.0, 3.0)

# ---------------------------------------------------------------------------
# 3. Universo — corrección del sesgo retrospectivo (sección 6 de la orden)
# ---------------------------------------------------------------------------
# Se mantiene el mismo umbral monetario, pero ahora se aplica sobre liquidez
# HISTÓRICA (promedio de volumen cotizado real durante la ventana de análisis,
# calculado a partir de las velas 1d ya descargadas), no sobre el ticker 24h
# "actual". Ver src_s21/universe.py.
MIN_AVG_DAILY_QUOTE_VOLUME_USDT = config_s2.MIN_AVG_DAILY_QUOTE_VOLUME_USDT
MIN_LISTING_AGE_DAYS = config_s2.MIN_LISTING_AGE_DAYS

# Activos que, aunque cotizan con quoteAsset=USDT, no representan exposición
# a una criptomoneda líquida tradicional: stablecoins, monedas fiat tokenizadas
# y acciones/ETFs tokenizados. La auditoría identificó USDCUSDT, USD1USDT,
# RLUSDUSDT, EURUSDT, NVDABUSDT, MSTRBUSDT en el universo de S2. Se excluyen
# explícitamente y se documentan en UNIVERSE_EXCLUSIONS.csv.
NON_CRYPTO_BASE_ASSETS = frozenset({
    "USDC", "USD1", "RLUSD", "FDUSD", "TUSD", "BUSD", "DAI", "USDP", "PYUSD",
    "EUR", "GBP", "AUD", "TRY", "BRL", "RUB", "UAH", "NGN", "ZAR", "JPY",
    "MXN", "ARS", "COP", "IDRT", "BIDR", "UST", "USTC",
})
# Prefijos que identifican acciones/ETFs tokenizados listados por Binance
# (p. ej. NVDABUSDT -> base asset "NVDAB"; MSTRBUSDT -> "MSTRB"). Se excluyen
# por sufijo "B" sobre tickers bursátiles conocidos, documentado caso a caso.
TOKENIZED_EQUITY_BASE_ASSETS = frozenset({
    "NVDAB", "MSTRB", "TSLAB", "COINB", "AAPLB", "AMZNB", "GOOGLB", "METAB",
    "MSFTB", "CRCLB",
})

# ---------------------------------------------------------------------------
# 4. Selección de operaciones simultáneas (sección 5 de la orden) — fix P0
# ---------------------------------------------------------------------------
SELECTION_METHOD_LIQUIDITY = "A_LIQUIDEZ"
SELECTION_METHOD_QUALITY = "B_CALIDAD_SENAL"
SELECTION_METHOD_RANDOM = "C_ALEATORIA"
SELECTION_METHODS = (SELECTION_METHOD_LIQUIDITY, SELECTION_METHOD_QUALITY, SELECTION_METHOD_RANDOM)
# El método A (liquidez) es el método PRINCIPAL usado para todos los
# resultados reportados como "el" resultado del indicador; B y C se usan
# únicamente para el análisis de sensibilidad (SELECTION_METHOD_COMPARISON.csv).
PRIMARY_SELECTION_METHOD = SELECTION_METHOD_LIQUIDITY
RANDOM_SELECTION_SEEDS = (11, 22, 33, 42, 99)
# Ventana causal (número de velas antes de la señal, inclusive la de señal)
# usada para calcular los puntajes de prioridad de liquidez y calidad.
SELECTION_SCORE_LOOKBACK_BARS = 20

# ---------------------------------------------------------------------------
# 5. Top Gainers causales (sección 7) — fix P0/P1
# ---------------------------------------------------------------------------
TOP_GAINERS_N = config_s2.TOP_GAINERS_N
TOP_GAINER_HORIZONS_HOURS = (1, 4, 12, 24, 48)

# ---------------------------------------------------------------------------
# 6. Robustez (sección 14) — nueva dimensión de clasificación
# ---------------------------------------------------------------------------
ROBUSTNESS_HIGH = "ALTA"
ROBUSTNESS_MEDIUM = "MEDIA"
ROBUSTNESS_LOW = "BAJA"
ROBUSTNESS_INSUFFICIENT = "INSUFICIENTE"
# Un resultado pierde robustez si al excluir la operación de mayor ganancia
# absoluta (USDT) el retorno neto cae por debajo de este umbral relativo
# de lo que era con esa operación incluida.
EXTREME_TRADE_MAX_SHARE_OF_GAIN = 0.40  # una sola operación no debe aportar >40%
# Umbral de caída de retorno neto bajo comisión x3 para considerar "ALTA" robustez.
COST_RESISTANT_MIN_NET_RETURN_PCT_AT_3X = 0.0
MIN_SYMBOLS_FOR_CROSS_ASSET_STABILITY = 3

# ---------------------------------------------------------------------------
# 7. Validación cronológica (sección 11)
# ---------------------------------------------------------------------------
# Fase A: reproduce exactamente el período original usado en S2 (60 días),
# congelado con fechas absolutas documentadas (no relativas a "ahora"), para
# que sea reproducible exactamente igual sin importar cuándo se re-ejecute.
PHASE_A_START_ISO = "2026-09-08T00:00:00Z"
PHASE_A_END_ISO = "2026-11-07T00:00:00Z"  # fin exclusivo
# Fase B: período histórico adicional, INMEDIATAMENTE ANTERIOR a la Fase A,
# jamás usado para seleccionar parámetros ni indicadores.
PHASE_B_START_ISO = "2026-07-10T00:00:00Z"
PHASE_B_END_ISO = "2026-09-08T00:00:00Z"  # fin exclusivo == inicio Fase A

RESULTS_DIR_NAME = "RESULTADOS_SPOT_EDGE_S21"


@dataclass
class RunConfigS21:
    phase: str = "A"  # "A" (reproducción 60d original) o "B" (histórico adicional)
    start_iso: str = PHASE_A_START_ISO
    end_iso: str = PHASE_A_END_ISO
    timeframes: tuple = TIMEFRAMES
    horizons_hours: tuple = HOLDING_HORIZONS_HOURS
    initial_capital_usdt: float = INITIAL_CAPITAL_USDT
    commission_pct_per_side: float = COMMISSION_PCT_PER_SIDE
    slippage_pct_per_side: float = SLIPPAGE_PCT_PER_SIDE
    max_symbols: int = 0
    run_cost_sensitivity: bool = True
    results_dir: str = RESULTS_DIR_NAME
    symbols_override: tuple = field(default_factory=tuple)
    selection_method: str = PRIMARY_SELECTION_METHOD
    run_selection_sensitivity: bool = True
    max_runtime_minutes: float = 0.0
