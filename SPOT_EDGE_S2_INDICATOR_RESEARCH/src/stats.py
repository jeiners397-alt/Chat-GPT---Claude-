"""
stats.py — Estadísticas obligatorias por indicador/temporalidad/horizonte
(sección 5 del encargo). Cuando una métrica es indefinida o la muestra es
insuficiente, se devuelve None (-> "N/A" en el CSV final), nunca un valor
inventado.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

from src.backtest import ExperimentResult

NA = None


def _safe_round(x, ndigits=6):
    if x is None or (isinstance(x, float) and (math.isnan(x) or math.isinf(x))):
        return NA
    return round(float(x), ndigits)


def compute_experiment_stats(result: ExperimentResult) -> dict:
    trades = result.trades
    n_trades = len(trades)

    stats = {
        "indicator_id": result.indicator_id,
        "indicator_name": result.indicator_name,
        "timeframe": result.timeframe,
        "horizon_hours": result.horizon_hours,
        "total_signals": result.total_signals,
        "operaciones_ejecutadas": n_trades,
        "senales_bloqueadas_por_capital": result.signals_skipped_capital_locked,
        "numero_activos_con_senal": len(result.symbols_with_signals),
        "capital_inicial_usdt": result.initial_capital,
        "capital_final_usdt": _safe_round(result.final_equity, 4),
    }

    if n_trades == 0:
        stats.update({
            "win_rate_pct": NA, "profit_factor": NA, "expectativa_matematica_pct": NA,
            "rentabilidad_neta_pct": NA, "rentabilidad_diaria_media_pct": NA,
            "rentabilidad_diaria_mediana_pct": NA, "drawdown_maximo_pct": NA,
            "ganancia_media_pct": NA, "perdida_media_pct": NA,
            "ratio_beneficio_riesgo": NA, "tiempo_mantenimiento_medio_horas": NA,
        })
        return stats

    pnl_pcts = np.array([t.pnl_pct_net for t in trades])
    wins = pnl_pcts[pnl_pcts > 0]
    losses = pnl_pcts[pnl_pcts <= 0]

    win_rate = 100.0 * len(wins) / n_trades
    gross_profit = wins.sum() if len(wins) else 0.0
    gross_loss_abs = abs(losses.sum()) if len(losses) else 0.0
    profit_factor = (gross_profit / gross_loss_abs) if gross_loss_abs > 0 else (np.inf if gross_profit > 0 else NA)
    expectancy = float(pnl_pcts.mean())
    net_return_pct = 100.0 * ((result.final_equity / result.initial_capital) - 1.0)

    avg_win = float(wins.mean()) if len(wins) else NA
    avg_loss = float(losses.mean()) if len(losses) else NA
    risk_reward = (abs(avg_win / avg_loss) if (avg_win is not NA and avg_loss not in (NA, 0)) else NA)

    avg_holding = float(np.mean([t.holding_hours for t in trades]))

    equity_curve = _build_equity_curve(trades, result.initial_capital)
    daily_returns = _daily_returns(equity_curve)
    daily_mean = float(daily_returns.mean()) * 100 if len(daily_returns) else NA
    daily_median = float(daily_returns.median()) * 100 if len(daily_returns) else NA
    max_dd = _max_drawdown_pct(equity_curve)

    stats.update({
        "win_rate_pct": _safe_round(win_rate, 2),
        "profit_factor": _safe_round(profit_factor, 4) if profit_factor not in (NA, np.inf) else ("inf" if profit_factor == np.inf else NA),
        "expectativa_matematica_pct": _safe_round(expectancy * 100, 4),
        "rentabilidad_neta_pct": _safe_round(net_return_pct, 4),
        "rentabilidad_diaria_media_pct": _safe_round(daily_mean, 5) if daily_mean is not NA else NA,
        "rentabilidad_diaria_mediana_pct": _safe_round(daily_median, 5) if daily_median is not NA else NA,
        "drawdown_maximo_pct": _safe_round(max_dd, 4),
        "ganancia_media_pct": _safe_round(avg_win * 100, 4) if avg_win is not NA else NA,
        "perdida_media_pct": _safe_round(avg_loss * 100, 4) if avg_loss is not NA else NA,
        "ratio_beneficio_riesgo": _safe_round(risk_reward, 4) if risk_reward is not NA else NA,
        "tiempo_mantenimiento_medio_horas": _safe_round(avg_holding, 2),
    })
    return stats


def _build_equity_curve(trades, initial_capital: float) -> pd.Series:
    times = [t.exit_time for t in trades]
    equities = [t.equity_after for t in trades]
    series = pd.Series(equities, index=pd.DatetimeIndex(times))
    series = pd.concat([pd.Series([initial_capital], index=[trades[0].entry_time]), series])
    return series.sort_index()


def _daily_returns(equity_curve: pd.Series) -> pd.Series:
    if len(equity_curve) < 2:
        return pd.Series(dtype=float)
    daily = equity_curve.resample("1D").last().ffill()
    return daily.pct_change().dropna()


def _max_drawdown_pct(equity_curve: pd.Series) -> float:
    if len(equity_curve) < 2:
        return 0.0
    running_max = equity_curve.cummax()
    drawdown = (equity_curve - running_max) / running_max
    return float(drawdown.min() * 100)


def compute_benchmark_stats(benchmark_close: pd.Series, initial_capital: float) -> dict:
    """Comparación con comprar-y-mantener (BTC o USDT) — sección 9.6."""
    clean = benchmark_close.dropna()
    if len(clean) < 2:
        return {"rentabilidad_neta_pct": NA, "drawdown_maximo_pct": NA}
    ret = (clean.iloc[-1] / clean.iloc[0]) - 1.0
    equity = initial_capital * (clean / clean.iloc[0])
    dd = _max_drawdown_pct(equity)
    return {
        "rentabilidad_neta_pct": _safe_round(ret * 100, 4),
        "drawdown_maximo_pct": _safe_round(dd, 4),
    }
