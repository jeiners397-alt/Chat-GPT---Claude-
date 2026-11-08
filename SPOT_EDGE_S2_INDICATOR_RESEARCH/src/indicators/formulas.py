"""
formulas.py — Bloques matemáticos base (fuente pública, estándar) usados por
las señales en signals.py. Cada función es pura (recibe pandas Series/DataFrame,
devuelve Series) y no usa información futura: toda ventana es `rolling` hacia
atrás, nunca `center=True`.

Fuentes: fórmulas de dominio público ampliamente documentadas (J. Welles
Wilder, "New Concepts in Technical Trading Systems", 1978; Appel, Bollinger,
Chande, etc.). Se referencian por indicador en src/indicators/registry.py.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# Medias móviles
# ---------------------------------------------------------------------------
def sma(series: pd.Series, length: int) -> pd.Series:
    return series.rolling(length, min_periods=length).mean()


def ema(series: pd.Series, length: int) -> pd.Series:
    return series.ewm(span=length, adjust=False, min_periods=length).mean()


def wilder_smoothing(series: pd.Series, length: int) -> pd.Series:
    """Suavizado de Wilder (usado en RSI/ADX/ATR originales)."""
    return series.ewm(alpha=1.0 / length, adjust=False, min_periods=length).mean()


def wma(series: pd.Series, length: int) -> pd.Series:
    weights = np.arange(1, length + 1)
    return series.rolling(length, min_periods=length).apply(
        lambda x: np.dot(x, weights) / weights.sum(), raw=True
    )


def hma(series: pd.Series, length: int) -> pd.Series:
    """Hull Moving Average."""
    half = wma(series, max(length // 2, 1))
    full = wma(series, length)
    raw = 2 * half - full
    return wma(raw, max(int(np.sqrt(length)), 1))


def alma(series: pd.Series, length: int = 21, offset: float = 0.85, sigma: float = 6.0) -> pd.Series:
    m = offset * (length - 1)
    s = length / sigma
    weights = np.array([np.exp(-((i - m) ** 2) / (2 * s * s)) for i in range(length)])
    weights /= weights.sum()

    def _window(x):
        return np.dot(x, weights)

    return series.rolling(length, min_periods=length).apply(_window, raw=True)


def kama(series: pd.Series, length: int = 10, fast: int = 2, slow: int = 30) -> pd.Series:
    change = series.diff(length).abs()
    volatility = series.diff().abs().rolling(length, min_periods=length).sum()
    er = (change / volatility.replace(0, np.nan)).fillna(0.0)
    fast_sc = 2.0 / (fast + 1)
    slow_sc = 2.0 / (slow + 1)
    sc = (er * (fast_sc - slow_sc) + slow_sc) ** 2

    kama_vals = pd.Series(index=series.index, dtype=float)
    first_valid = series.first_valid_index()
    if first_valid is None:
        return kama_vals
    start_pos = series.index.get_loc(first_valid) + length
    if start_pos >= len(series):
        return kama_vals
    kama_vals.iloc[start_pos] = series.iloc[start_pos]
    for i in range(start_pos + 1, len(series)):
        prev = kama_vals.iloc[i - 1]
        if pd.isna(prev):
            kama_vals.iloc[i] = series.iloc[i]
            continue
        kama_vals.iloc[i] = prev + sc.iloc[i] * (series.iloc[i] - prev)
    return kama_vals


def zlema(series: pd.Series, length: int) -> pd.Series:
    lag = (length - 1) // 2
    adjusted = series + (series - series.shift(lag))
    return ema(adjusted, length)


def dema(series: pd.Series, length: int) -> pd.Series:
    e1 = ema(series, length)
    e2 = ema(e1, length)
    return 2 * e1 - e2


def tema(series: pd.Series, length: int) -> pd.Series:
    e1 = ema(series, length)
    e2 = ema(e1, length)
    e3 = ema(e2, length)
    return 3 * e1 - 3 * e2 + e3


def t3(series: pd.Series, length: int = 10, vfactor: float = 0.7) -> pd.Series:
    e1 = ema(series, length)
    e2 = ema(e1, length)
    e3 = ema(e2, length)
    e4 = ema(e3, length)
    e5 = ema(e4, length)
    e6 = ema(e5, length)
    c1 = -(vfactor ** 3)
    c2 = 3 * vfactor ** 2 + 3 * vfactor ** 3
    c3 = -6 * vfactor ** 2 - 3 * vfactor - 3 * vfactor ** 3
    c4 = 1 + 3 * vfactor + vfactor ** 3 + 3 * vfactor ** 2
    return c1 * e6 + c2 * e5 + c3 * e4 + c4 * e3


def mcginley_dynamic(series: pd.Series, length: int = 14) -> pd.Series:
    md = pd.Series(index=series.index, dtype=float)
    first_valid = series.first_valid_index()
    if first_valid is None:
        return md
    start_pos = series.index.get_loc(first_valid)
    md.iloc[start_pos] = series.iloc[start_pos]
    for i in range(start_pos + 1, len(series)):
        prev = md.iloc[i - 1]
        price = series.iloc[i]
        if pd.isna(prev) or prev == 0:
            md.iloc[i] = price
            continue
        ratio = price / prev
        md.iloc[i] = prev + (price - prev) / (length * (ratio ** 4))
    return md


# ---------------------------------------------------------------------------
# Volatilidad / rango
# ---------------------------------------------------------------------------
def true_range(high: pd.Series, low: pd.Series, close: pd.Series) -> pd.Series:
    prev_close = close.shift(1)
    tr = pd.concat(
        [(high - low), (high - prev_close).abs(), (low - prev_close).abs()], axis=1
    ).max(axis=1)
    return tr


def atr(high: pd.Series, low: pd.Series, close: pd.Series, length: int = 14) -> pd.Series:
    return wilder_smoothing(true_range(high, low, close), length)


def bollinger_bands(close: pd.Series, length: int = 20, mult: float = 2.0):
    mid = sma(close, length)
    std = close.rolling(length, min_periods=length).std(ddof=0)
    upper = mid + mult * std
    lower = mid - mult * std
    return upper, mid, lower


def keltner_channels(high: pd.Series, low: pd.Series, close: pd.Series, length: int = 20, mult: float = 2.0):
    mid = ema(close, length)
    rng = atr(high, low, close, length)
    upper = mid + mult * rng
    lower = mid - mult * rng
    return upper, mid, lower


def donchian_channels(high: pd.Series, low: pd.Series, length: int = 20):
    upper = high.rolling(length, min_periods=length).max()
    lower = low.rolling(length, min_periods=length).min()
    return upper, lower


def choppiness_index(high: pd.Series, low: pd.Series, close: pd.Series, length: int = 14) -> pd.Series:
    tr_sum = true_range(high, low, close).rolling(length, min_periods=length).sum()
    hh = high.rolling(length, min_periods=length).max()
    ll = low.rolling(length, min_periods=length).min()
    rng = (hh - ll).replace(0, np.nan)
    return 100 * np.log10(tr_sum / rng) / np.log10(length)


def mass_index(high: pd.Series, low: pd.Series, length: int = 9, sum_length: int = 25) -> pd.Series:
    rng = high - low
    ema1 = ema(rng, length)
    ema2 = ema(ema1, length)
    ratio = ema1 / ema2.replace(0, np.nan)
    return ratio.rolling(sum_length, min_periods=sum_length).sum()


def parabolic_sar(high: pd.Series, low: pd.Series, close: pd.Series, af_step: float = 0.02, af_max: float = 0.2) -> pd.Series:
    """Parabolic SAR estándar (Wilder). Devuelve la serie de SAR."""
    n = len(close)
    sar = np.full(n, np.nan)
    if n < 2:
        return pd.Series(sar, index=close.index)
    uptrend = True
    af = af_step
    ep = high.iloc[0]
    sar_val = low.iloc[0]
    sar[0] = sar_val
    for i in range(1, n):
        prev_sar = sar_val
        if uptrend:
            sar_val = prev_sar + af * (ep - prev_sar)
            sar_val = min(sar_val, low.iloc[i - 1], low.iloc[i] if i >= 1 else low.iloc[i])
            if low.iloc[i] < sar_val:
                uptrend = False
                sar_val = ep
                ep = low.iloc[i]
                af = af_step
        else:
            sar_val = prev_sar + af * (ep - prev_sar)
            sar_val = max(sar_val, high.iloc[i - 1], high.iloc[i] if i >= 1 else high.iloc[i])
            if high.iloc[i] > sar_val:
                uptrend = True
                sar_val = ep
                ep = high.iloc[i]
                af = af_step
        if uptrend and high.iloc[i] > ep:
            ep = high.iloc[i]
            af = min(af + af_step, af_max)
        elif not uptrend and low.iloc[i] < ep:
            ep = low.iloc[i]
            af = min(af + af_step, af_max)
        sar[i] = sar_val
    return pd.Series(sar, index=close.index)


def supertrend(high: pd.Series, low: pd.Series, close: pd.Series, length: int = 10, mult: float = 3.0):
    """Devuelve (línea_supertrend, dirección) donde dirección=1 alcista, -1 bajista."""
    hl2 = (high + low) / 2
    rng = atr(high, low, close, length)
    upper_basic = hl2 + mult * rng
    lower_basic = hl2 - mult * rng

    n = len(close)
    final_upper = upper_basic.copy()
    final_lower = lower_basic.copy()
    direction = pd.Series(1, index=close.index)
    st = pd.Series(np.nan, index=close.index)

    for i in range(1, n):
        if close.iloc[i - 1] > final_upper.iloc[i - 1]:
            final_upper.iloc[i] = min(upper_basic.iloc[i], final_upper.iloc[i - 1]) if close.iloc[i] > final_upper.iloc[i-1] else upper_basic.iloc[i]
        final_upper.iloc[i] = upper_basic.iloc[i] if upper_basic.iloc[i] < final_upper.iloc[i - 1] or close.iloc[i - 1] > final_upper.iloc[i - 1] else final_upper.iloc[i - 1]
        final_lower.iloc[i] = lower_basic.iloc[i] if lower_basic.iloc[i] > final_lower.iloc[i - 1] or close.iloc[i - 1] < final_lower.iloc[i - 1] else final_lower.iloc[i - 1]

    for i in range(1, n):
        if pd.isna(final_upper.iloc[i - 1]):
            direction.iloc[i] = 1
            continue
        if direction.iloc[i - 1] == 1:
            direction.iloc[i] = -1 if close.iloc[i] < final_lower.iloc[i] else 1
        else:
            direction.iloc[i] = 1 if close.iloc[i] > final_upper.iloc[i] else -1
        st.iloc[i] = final_lower.iloc[i] if direction.iloc[i] == 1 else final_upper.iloc[i]
    return st, direction


# ---------------------------------------------------------------------------
# Momentum / osciladores
# ---------------------------------------------------------------------------
def rsi(close: pd.Series, length: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = wilder_smoothing(gain, length)
    avg_loss = wilder_smoothing(loss, length)
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def stoch_rsi(close: pd.Series, rsi_length: int = 14, stoch_length: int = 14) -> pd.Series:
    r = rsi(close, rsi_length)
    lowest = r.rolling(stoch_length, min_periods=stoch_length).min()
    highest = r.rolling(stoch_length, min_periods=stoch_length).max()
    return 100 * (r - lowest) / (highest - lowest).replace(0, np.nan)


def macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    macd_line = ema(close, fast) - ema(close, slow)
    signal_line = ema(macd_line, signal)
    hist = macd_line - signal_line
    return macd_line, signal_line, hist


def cci(high: pd.Series, low: pd.Series, close: pd.Series, length: int = 20) -> pd.Series:
    tp = (high + low + close) / 3
    sma_tp = sma(tp, length)
    mean_dev = (tp - sma_tp).abs().rolling(length, min_periods=length).mean()
    return (tp - sma_tp) / (0.015 * mean_dev.replace(0, np.nan))


def williams_r(high: pd.Series, low: pd.Series, close: pd.Series, length: int = 14) -> pd.Series:
    hh = high.rolling(length, min_periods=length).max()
    ll = low.rolling(length, min_periods=length).min()
    return -100 * (hh - close) / (hh - ll).replace(0, np.nan)


def awesome_oscillator(high: pd.Series, low: pd.Series) -> pd.Series:
    median_price = (high + low) / 2
    return sma(median_price, 5) - sma(median_price, 34)


def accelerator_oscillator(high: pd.Series, low: pd.Series) -> pd.Series:
    ao = awesome_oscillator(high, low)
    return ao - sma(ao, 5)


def tsi(close: pd.Series, long_len: int = 25, short_len: int = 13, signal_len: int = 7):
    diff = close.diff()
    abs_diff = diff.abs()
    double_smoothed = ema(ema(diff, long_len), short_len)
    double_smoothed_abs = ema(ema(abs_diff, long_len), short_len)
    tsi_line = 100 * double_smoothed / double_smoothed_abs.replace(0, np.nan)
    signal_line = ema(tsi_line, signal_len)
    return tsi_line, signal_line


def cmo(close: pd.Series, length: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(length, min_periods=length).sum()
    loss = (-delta.clip(upper=0)).rolling(length, min_periods=length).sum()
    return 100 * (gain - loss) / (gain + loss).replace(0, np.nan)


def roc(close: pd.Series, length: int = 12) -> pd.Series:
    return 100 * (close - close.shift(length)) / close.shift(length).replace(0, np.nan)


def balance_of_power(open_: pd.Series, high: pd.Series, low: pd.Series, close: pd.Series) -> pd.Series:
    return (close - open_) / (high - low).replace(0, np.nan)


def ppo(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    ppo_line = 100 * (ema(close, fast) - ema(close, slow)) / ema(close, slow).replace(0, np.nan)
    signal_line = ema(ppo_line, signal)
    return ppo_line, signal_line


def trix(close: pd.Series, length: int = 15) -> pd.Series:
    e3 = ema(ema(ema(close, length), length), length)
    return 100 * e3.diff() / e3.shift(1).replace(0, np.nan)


def dpo(close: pd.Series, length: int = 20) -> pd.Series:
    shift = int(length / 2) + 1
    return close.shift(shift) - sma(close, length)


def rvi_relative_volatility(close: pd.Series, length: int = 10) -> pd.Series:
    std = close.diff().rolling(length, min_periods=length).std(ddof=0)
    up = std.where(close.diff() > 0, 0.0)
    down = std.where(close.diff() <= 0, 0.0)
    up_avg = wilder_smoothing(up, 14)
    down_avg = wilder_smoothing(down, 14)
    return 100 * up_avg / (up_avg + down_avg).replace(0, np.nan)


# ---------------------------------------------------------------------------
# Volumen / flujo de órdenes
# ---------------------------------------------------------------------------
def obv(close: pd.Series, volume: pd.Series) -> pd.Series:
    direction = np.sign(close.diff()).fillna(0)
    return (direction * volume).cumsum()


def chaikin_money_flow(high: pd.Series, low: pd.Series, close: pd.Series, volume: pd.Series, length: int = 20) -> pd.Series:
    mf_mult = ((close - low) - (high - close)) / (high - low).replace(0, np.nan)
    mf_vol = mf_mult * volume
    return mf_vol.rolling(length, min_periods=length).sum() / volume.rolling(length, min_periods=length).sum()


def accumulation_distribution(high: pd.Series, low: pd.Series, close: pd.Series, volume: pd.Series) -> pd.Series:
    mf_mult = ((close - low) - (high - close)) / (high - low).replace(0, np.nan)
    return (mf_mult * volume).cumsum()


def money_flow_index(high: pd.Series, low: pd.Series, close: pd.Series, volume: pd.Series, length: int = 14) -> pd.Series:
    tp = (high + low + close) / 3
    raw_mf = tp * volume
    positive = raw_mf.where(tp.diff() > 0, 0.0).rolling(length, min_periods=length).sum()
    negative = raw_mf.where(tp.diff() < 0, 0.0).rolling(length, min_periods=length).sum()
    mfr = positive / negative.replace(0, np.nan)
    return 100 - (100 / (1 + mfr))


def klinger_volume_oscillator(high: pd.Series, low: pd.Series, close: pd.Series, volume: pd.Series,
                               fast: int = 34, slow: int = 55, signal: int = 13):
    trend = np.sign((high + low + close).diff()).fillna(0)
    dm = high - low
    cm = pd.Series(index=close.index, dtype=float)
    cm_val = 0.0
    prev_trend = 0
    prev_dm = dm.iloc[0] if len(dm) else 0.0
    for i in range(len(close)):
        t = trend.iloc[i]
        if i == 0 or t != prev_trend:
            cm_val = dm.iloc[i] + (prev_dm if i > 0 else 0.0)
        else:
            cm_val = cm.iloc[i - 1] + dm.iloc[i] if not pd.isna(cm.iloc[i - 1]) else dm.iloc[i]
        cm.iloc[i] = cm_val
        prev_trend = t
        prev_dm = dm.iloc[i]
    vf = volume * (2 * (dm / cm.replace(0, np.nan)).abs() - 1) * trend * 100
    kvo_line = ema(vf, fast) - ema(vf, slow)
    signal_line = ema(kvo_line, signal)
    return kvo_line, signal_line


def elder_force_index(close: pd.Series, volume: pd.Series, length: int = 13) -> pd.Series:
    raw = (close - close.shift(1)) * volume
    return ema(raw, length)


def vwap(high: pd.Series, low: pd.Series, close: pd.Series, volume: pd.Series, length: int = 20) -> pd.Series:
    typical = (high + low + close) / 3
    pv = typical * volume
    return pv.rolling(length, min_periods=length).sum() / volume.rolling(length, min_periods=length).sum()


# ---------------------------------------------------------------------------
# Estadística / cuantitativo
# ---------------------------------------------------------------------------
def rolling_zscore(series: pd.Series, length: int = 20) -> pd.Series:
    mean = series.rolling(length, min_periods=length).mean()
    std = series.rolling(length, min_periods=length).std(ddof=0)
    return (series - mean) / std.replace(0, np.nan)


def hurst_exponent(series: pd.Series, length: int = 100, min_chunk: int = 8) -> pd.Series:
    """Exponente de Hurst por el método de rango reescalado (R/S) simplificado,
    calculado sobre ventanas móviles. H>0.5 => persistencia/tendencia,
    H<0.5 => reversión a la media, H≈0.5 => paseo aleatorio."""

    def _hurst_window(x: np.ndarray) -> float:
        x = x[~np.isnan(x)]
        if len(x) < min_chunk:
            return np.nan
        lags = range(2, min(20, len(x) // 2))
        tau = []
        for lag in lags:
            diffs = np.subtract(x[lag:], x[:-lag])
            std = np.std(diffs)
            tau.append(std if std > 0 else np.nan)
        tau = np.array(tau)
        if np.all(np.isnan(tau)) or len(tau) < 2:
            return np.nan
        valid = ~np.isnan(tau)
        if valid.sum() < 2:
            return np.nan
        poly = np.polyfit(np.log(list(lags)[: len(tau)])[valid], np.log(tau[valid]), 1)
        return poly[0] * 2.0

    return series.rolling(length, min_periods=length).apply(_hurst_window, raw=True)


def kalman_filter_1d(series: pd.Series, process_var: float = 1e-5, measurement_var: float = 1e-2) -> pd.Series:
    """Filtro de Kalman escalar simple (sin dependencias externas) para suavizar precio."""
    n = len(series)
    estimates = np.full(n, np.nan)
    if n == 0:
        return pd.Series(estimates, index=series.index)
    x_est = series.iloc[0]
    p_est = 1.0
    estimates[0] = x_est
    for i in range(1, n):
        z = series.iloc[i]
        if pd.isna(z):
            estimates[i] = x_est
            continue
        p_pred = p_est + process_var
        k_gain = p_pred / (p_pred + measurement_var)
        x_est = x_est + k_gain * (z - x_est)
        p_est = (1 - k_gain) * p_pred
        estimates[i] = x_est
    return pd.Series(estimates, index=series.index)


def shannon_entropy(close: pd.Series, length: int = 20, bins: int = 10) -> pd.Series:
    returns = close.pct_change()

    def _entropy_window(x: np.ndarray) -> float:
        x = x[~np.isnan(x)]
        if len(x) < bins:
            return np.nan
        counts, _ = np.histogram(x, bins=bins)
        probs = counts / counts.sum()
        probs = probs[probs > 0]
        return float(-np.sum(probs * np.log2(probs)))

    return returns.rolling(length, min_periods=length).apply(_entropy_window, raw=True)


def kaufman_efficiency_ratio(close: pd.Series, length: int = 10) -> pd.Series:
    change = close.diff(length).abs()
    volatility = close.diff().abs().rolling(length, min_periods=length).sum()
    return change / volatility.replace(0, np.nan)


def rolling_beta(asset_returns: pd.Series, benchmark_returns: pd.Series, length: int = 30) -> pd.Series:
    cov = asset_returns.rolling(length, min_periods=length).cov(benchmark_returns)
    var = benchmark_returns.rolling(length, min_periods=length).var()
    return cov / var.replace(0, np.nan)


def adf_pvalue_rolling(close: pd.Series, length: int = 60) -> pd.Series:
    """p-valor del test de Dickey-Fuller aumentado (ADF) en ventana móvil.
    p-valor bajo => se rechaza la hipótesis de raíz unitaria => serie más
    estacionaria (más apta para mean-reversion) en esa ventana."""
    from statsmodels.tsa.stattools import adfuller

    def _adf_window(x: np.ndarray) -> float:
        x = x[~np.isnan(x)]
        if len(x) < length or np.allclose(x, x[0]):
            return np.nan
        try:
            result = adfuller(x, maxlag=1, autolag=None, result_object=False)
            return float(result[1])
        except Exception:
            return np.nan

    return close.rolling(length, min_periods=length).apply(_adf_window, raw=True)
