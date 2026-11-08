"""
signals.py — Reglas LONG objetivas por indicador (sección 3 del encargo).

Cada función recibe un DataFrame con columnas:
    open, high, low, close, volume, taker_buy_base_volume
(y opcionalmente btc_close, alineado por tiempo, para indicadores relativos a BTC)

y devuelve una pd.Series booleana `long_entry_signal`, True en la vela donde
la señal queda confirmada AL CIERRE de esa vela (la entrada se simula en la
apertura de la siguiente vela — ver src/backtest.py). Ninguna función mira
datos posteriores al índice evaluado (sin look-ahead).

IMPORTANTE: estos son protocolos elegidos por el equipo para convertir cada
indicador en un experimento comparable (sección 3.1). Son hipótesis a
contrastar, no resultados probados de antemano.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.indicators import formulas as f


def _cross_above(a: pd.Series, b) -> pd.Series:
    b_series = b if isinstance(b, pd.Series) else pd.Series(b, index=a.index)
    return (a > b_series) & (a.shift(1) <= b_series.shift(1))


def _recovered_above(series: pd.Series, threshold: float, lookback: int = 1) -> pd.Series:
    """True si la serie estaba <= umbral hace `lookback` velas y ahora > umbral."""
    return (series > threshold) & (series.shift(lookback) <= threshold)


# ---------------------------------------------------------------------------
# TREND / MEDIAS MÓVILES  (catálogo #81-#87, #94, #95, #109)
# ---------------------------------------------------------------------------
def sig_hma_cross(df, **_):
    ma = f.hma(df["close"], 21)
    return _cross_above(df["close"], ma)


def sig_alma_cross(df, **_):
    ma = f.alma(df["close"], 21)
    return _cross_above(df["close"], ma)


def sig_kama_cross(df, **_):
    ma = f.kama(df["close"], 10, 2, 30)
    return _cross_above(df["close"], ma)


def sig_t3_cross(df, **_):
    ma = f.t3(df["close"], 10, 0.7)
    return _cross_above(df["close"], ma)


def sig_zlema_cross(df, **_):
    ma = f.zlema(df["close"], 21)
    return _cross_above(df["close"], ma)


def sig_mcginley_cross(df, **_):
    ma = f.mcginley_dynamic(df["close"], 14)
    return _cross_above(df["close"], ma)


def sig_dema_tema_cross(df, **_):
    d = f.dema(df["close"], 20)
    t = f.tema(df["close"], 20)
    return _cross_above(d, t)


def sig_supertrend_flip(df, **_):
    _, direction = f.supertrend(df["high"], df["low"], df["close"], 10, 3.0)
    return (direction == 1) & (direction.shift(1) == -1)


def sig_parabolic_sar_flip(df, **_):
    sar = f.parabolic_sar(df["high"], df["low"], df["close"])
    return (df["close"] > sar) & (df["close"].shift(1) <= sar.shift(1))


def sig_donchian_breakout(df, **_):
    upper, _ = f.donchian_channels(df["high"], df["low"], 20)
    prev_upper = upper.shift(1)
    return (df["close"] > prev_upper) & (df["close"].shift(1) <= prev_upper.shift(1))


def sig_trix_zero_cross(df, **_):
    t = f.trix(df["close"], 15)
    return _cross_above(t, 0.0)


# ---------------------------------------------------------------------------
# MOMENTUM / OSCILADORES (catálogo #121-#149)
# ---------------------------------------------------------------------------
def sig_rsi_recovery(df, **_):
    r = f.rsi(df["close"], 14)
    return _recovered_above(r, 30.0)


def sig_stochrsi_recovery(df, **_):
    s = f.stoch_rsi(df["close"], 14, 14)
    return _recovered_above(s, 20.0)


def sig_connors_rsi_recovery(df, **_):
    rsi3 = f.rsi(df["close"], 3)
    streak = (np.sign(df["close"].diff()).fillna(0))
    streak_len = streak.groupby((streak != streak.shift()).cumsum()).cumcount() if False else None
    # Streak RSI simplificado: RSI(3) de la racha de signos consecutivos.
    sign = np.sign(df["close"].diff()).fillna(0)
    streak_count = pd.Series(0, index=df.index, dtype=float)
    count = 0
    last_sign = 0
    for i, s_ in enumerate(sign):
        if s_ == 0:
            count = 0
        elif s_ == last_sign:
            count += s_
        else:
            count = s_
        streak_count.iat[i] = count
        last_sign = s_
    streak_rsi = f.rsi(streak_count, 2)
    roc_rank = f.roc(df["close"], 100).rolling(100, min_periods=100).rank(pct=True) * 100
    crsi = (rsi3 + streak_rsi + roc_rank) / 3
    return _recovered_above(crsi, 30.0)


def sig_cci_recovery(df, **_):
    c = f.cci(df["high"], df["low"], df["close"], 20)
    return _recovered_above(c, -100.0)


def sig_williams_r_recovery(df, **_):
    w = f.williams_r(df["high"], df["low"], df["close"], 14)
    return _recovered_above(w, -80.0)


def sig_awesome_oscillator_zero_cross(df, **_):
    ao = f.awesome_oscillator(df["high"], df["low"])
    return _cross_above(ao, 0.0)


def sig_accelerator_oscillator_zero_cross(df, **_):
    ac = f.accelerator_oscillator(df["high"], df["low"])
    return _cross_above(ac, 0.0)


def sig_tsi_signal_cross(df, **_):
    tsi_line, signal_line = f.tsi(df["close"])
    return _cross_above(tsi_line, signal_line)


def sig_cmo_recovery(df, **_):
    c = f.cmo(df["close"], 14)
    return _recovered_above(c, -50.0)


def sig_roc_zero_cross(df, **_):
    r = f.roc(df["close"], 12)
    return _cross_above(r, 0.0)


def sig_balance_of_power_zero_cross(df, **_):
    bop = f.balance_of_power(df["open"], df["high"], df["low"], df["close"])
    return _cross_above(bop, 0.0)


def sig_ppo_signal_cross(df, **_):
    ppo_line, signal_line = f.ppo(df["close"])
    return _cross_above(ppo_line, signal_line)


# ---------------------------------------------------------------------------
# VOLATILIDAD / RUPTURA (catálogo #96, #97, #104, #119, #120, #145)
# ---------------------------------------------------------------------------
def sig_keltner_breakout(df, **_):
    upper, _, _ = f.keltner_channels(df["high"], df["low"], df["close"], 20, 2.0)
    prev_upper = upper.shift(1)
    return (df["close"] > prev_upper) & (df["close"].shift(1) <= prev_upper.shift(1))


def sig_choppiness_trend_composite(df, **_):
    chop = f.choppiness_index(df["high"], df["low"], df["close"], 14)
    ema20 = f.ema(df["close"], 20)
    ema50 = f.ema(df["close"], 50)
    trending_regime = chop < 38.2
    bullish_cross = _cross_above(ema20, ema50)
    return trending_regime & bullish_cross


def sig_squeeze_momentum_breakout(df, **_):
    bb_upper, bb_mid, bb_lower = f.bollinger_bands(df["close"], 20, 2.0)
    kc_upper, kc_mid, kc_lower = f.keltner_channels(df["high"], df["low"], df["close"], 20, 1.5)
    squeeze_on = (bb_lower > kc_lower) & (bb_upper < kc_upper)
    was_squeezed = squeeze_on.shift(1).fillna(False)
    momentum = df["close"] - f.sma(df["close"], 20)
    breakout_up = (momentum > 0) & (momentum.shift(1) <= 0)
    return was_squeezed & breakout_up


def sig_dpo_zero_cross(df, **_):
    d = f.dpo(df["close"], 20)
    return _cross_above(d, 0.0)


def sig_mass_index_reversal(df, **_):
    mi = f.mass_index(df["high"], df["low"], 9, 25)
    bulge = (mi > 27.0) & (mi.shift(1) <= 27.0)
    reversal_trigger = mi < 26.5
    price_up = df["close"] > df["close"].shift(1)
    had_bulge_recently = bulge.rolling(10, min_periods=1).max().astype(bool)
    return had_bulge_recently & reversal_trigger & price_up


def sig_rvi_recovery(df, **_):
    r = f.rvi_relative_volatility(df["close"], 10)
    return _recovered_above(r, 50.0)


# ---------------------------------------------------------------------------
# VOLUMEN / FLUJO DE ÓRDENES (catálogo #3, #48, #50-#53, #57, #61, #152)
# ---------------------------------------------------------------------------
def sig_obv_breakout(df, **_):
    o = f.obv(df["close"], df["volume"])
    o_sma = f.sma(o, 20)
    return _cross_above(o, o_sma)


def sig_cmf_zero_cross(df, **_):
    cmf = f.chaikin_money_flow(df["high"], df["low"], df["close"], df["volume"], 20)
    return _cross_above(cmf, 0.0)


def sig_ad_line_breakout(df, **_):
    ad = f.accumulation_distribution(df["high"], df["low"], df["close"], df["volume"])
    ad_sma = f.sma(ad, 20)
    return _cross_above(ad, ad_sma)


def sig_mfi_recovery(df, **_):
    mfi = f.money_flow_index(df["high"], df["low"], df["close"], df["volume"], 14)
    return _recovered_above(mfi, 20.0)


def sig_taker_buy_ratio_pressure(df, **_):
    ratio = df["taker_buy_base_volume"] / df["volume"].replace(0, np.nan)
    ratio_sma = f.sma(ratio, 10)
    price_up = df["close"] > df["close"].shift(1)
    return (ratio > 0.55) & (ratio > ratio_sma) & price_up


def sig_cvd_breakout(df, **_):
    taker_sell = df["volume"] - df["taker_buy_base_volume"]
    delta = df["taker_buy_base_volume"] - taker_sell
    cvd = delta.cumsum()
    cvd_sma = f.sma(cvd, 20)
    return _cross_above(cvd, cvd_sma)


def sig_klinger_signal_cross(df, **_):
    kvo_line, signal_line = f.klinger_volume_oscillator(df["high"], df["low"], df["close"], df["volume"])
    return _cross_above(kvo_line, signal_line)


def sig_elder_force_index_zero_cross(df, **_):
    efi = f.elder_force_index(df["close"], df["volume"], 13)
    return _cross_above(efi, 0.0)


def sig_vwap_zscore_recovery(df, **_):
    vw = f.vwap(df["high"], df["low"], df["close"], df["volume"], 20)
    distance = df["close"] - vw
    z = f.rolling_zscore(distance, 20)
    return _recovered_above(z, -2.0)


# ---------------------------------------------------------------------------
# ESTADÍSTICO / CUANTITATIVO (catálogo #4, #5, #10, #23, #29, #34, #37)
# ---------------------------------------------------------------------------
def sig_hurst_trend_composite(df, **_):
    h = f.hurst_exponent(df["close"], 100)
    ema20 = f.ema(df["close"], 20)
    ema50 = f.ema(df["close"], 50)
    persistent_regime = h > 0.55
    bullish_cross = _cross_above(ema20, ema50)
    return persistent_regime & bullish_cross


def sig_kalman_cross(df, **_):
    kf = f.kalman_filter_1d(df["close"])
    return _cross_above(df["close"], kf)


def sig_entropy_compression_breakout(df, **_):
    ent = f.shannon_entropy(df["close"], 20)
    low_entropy = ent < ent.rolling(60, min_periods=20).quantile(0.25)
    upper, _ = f.donchian_channels(df["high"], df["low"], 20)
    prev_upper = upper.shift(1)
    breakout = (df["close"] > prev_upper) & (df["close"].shift(1) <= prev_upper.shift(1))
    was_compressed = low_entropy.shift(1).fillna(False)
    return was_compressed & breakout


def sig_kaufman_er_trend_composite(df, **_):
    er = f.kaufman_efficiency_ratio(df["close"], 10)
    price_up = df["close"] > df["close"].shift(1)
    efficient_trend = (er > 0.3) & (er.shift(1) <= 0.3)
    return efficient_trend & price_up


def sig_zscore_mean_reversion_recovery(df, **_):
    z = f.rolling_zscore(df["close"], 20)
    return _recovered_above(z, -2.5)


def sig_adf_stationary_meanreversion(df, **_):
    pvalue = f.adf_pvalue_rolling(df["close"], 60)
    z = f.rolling_zscore(df["close"], 20)
    stationary = pvalue < 0.10
    recovering = _recovered_above(z, -1.0)
    return stationary & recovering


def sig_beta_btc_composite(df, btc_close=None, **_):
    if btc_close is None:
        return pd.Series(False, index=df.index)
    asset_ret = df["close"].pct_change()
    btc_ret = btc_close.pct_change().reindex(df.index).ffill()
    beta = f.rolling_beta(asset_ret, btc_ret, 30)
    btc_up = btc_ret > 0
    high_beta = beta > 1.0
    outperforming = asset_ret > btc_ret
    return high_beta & btc_up & outperforming


REGISTRY_FUNCTIONS = {
    "sig_hma_cross": sig_hma_cross,
    "sig_alma_cross": sig_alma_cross,
    "sig_kama_cross": sig_kama_cross,
    "sig_t3_cross": sig_t3_cross,
    "sig_zlema_cross": sig_zlema_cross,
    "sig_mcginley_cross": sig_mcginley_cross,
    "sig_dema_tema_cross": sig_dema_tema_cross,
    "sig_supertrend_flip": sig_supertrend_flip,
    "sig_parabolic_sar_flip": sig_parabolic_sar_flip,
    "sig_donchian_breakout": sig_donchian_breakout,
    "sig_trix_zero_cross": sig_trix_zero_cross,
    "sig_rsi_recovery": sig_rsi_recovery,
    "sig_stochrsi_recovery": sig_stochrsi_recovery,
    "sig_connors_rsi_recovery": sig_connors_rsi_recovery,
    "sig_cci_recovery": sig_cci_recovery,
    "sig_williams_r_recovery": sig_williams_r_recovery,
    "sig_awesome_oscillator_zero_cross": sig_awesome_oscillator_zero_cross,
    "sig_accelerator_oscillator_zero_cross": sig_accelerator_oscillator_zero_cross,
    "sig_tsi_signal_cross": sig_tsi_signal_cross,
    "sig_cmo_recovery": sig_cmo_recovery,
    "sig_roc_zero_cross": sig_roc_zero_cross,
    "sig_balance_of_power_zero_cross": sig_balance_of_power_zero_cross,
    "sig_ppo_signal_cross": sig_ppo_signal_cross,
    "sig_keltner_breakout": sig_keltner_breakout,
    "sig_choppiness_trend_composite": sig_choppiness_trend_composite,
    "sig_squeeze_momentum_breakout": sig_squeeze_momentum_breakout,
    "sig_dpo_zero_cross": sig_dpo_zero_cross,
    "sig_mass_index_reversal": sig_mass_index_reversal,
    "sig_rvi_recovery": sig_rvi_recovery,
    "sig_obv_breakout": sig_obv_breakout,
    "sig_cmf_zero_cross": sig_cmf_zero_cross,
    "sig_ad_line_breakout": sig_ad_line_breakout,
    "sig_mfi_recovery": sig_mfi_recovery,
    "sig_taker_buy_ratio_pressure": sig_taker_buy_ratio_pressure,
    "sig_cvd_breakout": sig_cvd_breakout,
    "sig_klinger_signal_cross": sig_klinger_signal_cross,
    "sig_elder_force_index_zero_cross": sig_elder_force_index_zero_cross,
    "sig_vwap_zscore_recovery": sig_vwap_zscore_recovery,
    "sig_hurst_trend_composite": sig_hurst_trend_composite,
    "sig_kalman_cross": sig_kalman_cross,
    "sig_entropy_compression_breakout": sig_entropy_compression_breakout,
    "sig_kaufman_er_trend_composite": sig_kaufman_er_trend_composite,
    "sig_zscore_mean_reversion_recovery": sig_zscore_mean_reversion_recovery,
    "sig_adf_stationary_meanreversion": sig_adf_stationary_meanreversion,
    "sig_beta_btc_composite": sig_beta_btc_composite,
}
