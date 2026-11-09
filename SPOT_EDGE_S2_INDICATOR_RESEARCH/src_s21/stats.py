"""
stats.py (S2.1) — Corrige los defectos P0 de src/stats.py (S2):

  1. Profit Factor MONETARIO (sección 4): PF = ganancia_bruta_usdt /
     |pérdida_bruta_usdt|, sobre pnl_usdt (que ya refleja el tamaño real de
     cada operación, el cual varía porque el capital compuesto). El PF
     porcentual de S2 se conserva como métrica AUXILIAR (profit_factor_pct_legacy),
     tal como exige la orden, nunca como la métrica principal.
  2. Drawdown y retornos diarios a partir de la curva mark-to-market real
     (accounting.mark_to_market_curve), no solo de los puntos de cierre.
  3. Nunca se trata un PF infinito como prueba de rentabilidad: si no hay
     ninguna operación perdedora, se reporta "indefinido" con la explicación
     del tamaño de muestra (sección 4, párrafo final).
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

from src_s21.accounting import daily_equity, daily_returns, mark_to_market_curve, max_drawdown_pct
from src_s21.backtest import ExperimentResult

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
        "metodo_seleccion": result.selection_method,
        "semilla_seleccion": result.selection_seed,
    }

    if n_trades == 0:
        stats.update({
            "win_rate_pct": NA, "profit_factor_usdt": NA, "profit_factor_pct_legacy": NA,
            "profit_factor_estado": "sin_operaciones",
            "ganancia_bruta_usdt": NA, "perdida_bruta_usdt": NA,
            "expectativa_matematica_pct": NA, "expectativa_matematica_usdt": NA,
            "rentabilidad_neta_pct": NA, "rentabilidad_diaria_media_pct": NA,
            "rentabilidad_diaria_mediana_pct": NA, "drawdown_maximo_pct": NA,
            "ganancia_media_pct": NA, "perdida_media_pct": NA, "ganancia_promedio_por_operacion_usdt": NA,
            "ratio_beneficio_riesgo": NA, "tiempo_mantenimiento_medio_horas": NA,
        })
        return stats

    pnl_pcts = np.array([t.pnl_pct_net for t in trades])
    pnl_usdt = np.array([t.pnl_usdt for t in trades])
    wins_usdt = pnl_usdt[pnl_usdt > 0]
    losses_usdt = pnl_usdt[pnl_usdt <= 0]
    wins_pct = pnl_pcts[pnl_pcts > 0]
    losses_pct = pnl_pcts[pnl_pcts <= 0]

    win_rate = 100.0 * len(wins_usdt) / n_trades
    gross_profit_usdt = float(wins_usdt.sum()) if len(wins_usdt) else 0.0
    gross_loss_usdt_abs = float(abs(losses_usdt.sum())) if len(losses_usdt) else 0.0

    n_losing = int((pnl_usdt <= 0).sum())
    if gross_loss_usdt_abs > 0:
        profit_factor_usdt = gross_profit_usdt / gross_loss_usdt_abs
        pf_estado = "definido"
    elif gross_profit_usdt > 0:
        profit_factor_usdt = None
        pf_estado = (
            f"indefinido (sin operaciones perdedoras en {n_trades} operaciones totales; "
            f"PF infinito NO se interpreta como prueba de rentabilidad con muestra tan pequeña)"
        )
    else:
        profit_factor_usdt = None
        pf_estado = "indefinido (sin ganancias ni pérdidas: todas las operaciones en cero)"

    # PF porcentual legacy (S2), conservado SOLO como referencia auxiliar.
    gross_profit_pct = float(wins_pct.sum()) if len(wins_pct) else 0.0
    gross_loss_pct_abs = float(abs(losses_pct.sum())) if len(losses_pct) else 0.0
    if gross_loss_pct_abs > 0:
        profit_factor_pct_legacy = gross_profit_pct / gross_loss_pct_abs
    elif gross_profit_pct > 0:
        profit_factor_pct_legacy = None
    else:
        profit_factor_pct_legacy = None

    expectancy_pct = float(pnl_pcts.mean())
    expectancy_usdt = float(pnl_usdt.mean())
    net_return_pct = 100.0 * ((result.final_equity / result.initial_capital) - 1.0)

    avg_win_pct = float(wins_pct.mean()) if len(wins_pct) else NA
    avg_loss_pct = float(losses_pct.mean()) if len(losses_pct) else NA
    risk_reward = (abs(avg_win_pct / avg_loss_pct) if (avg_win_pct is not NA and avg_loss_pct not in (NA, 0)) else NA)

    avg_holding = float(np.mean([t.holding_hours for t in trades]))

    mtm_curve = mark_to_market_curve(trades, result.initial_capital)
    daily_eq = daily_equity(mtm_curve)
    d_returns = daily_returns(daily_eq)
    daily_mean = float(d_returns.mean()) * 100 if len(d_returns) else NA
    daily_median = float(d_returns.median()) * 100 if len(d_returns) else NA
    max_dd = max_drawdown_pct(mtm_curve)

    stats.update({
        "win_rate_pct": _safe_round(win_rate, 2),
        "profit_factor_usdt": _safe_round(profit_factor_usdt, 4),
        "profit_factor_pct_legacy": _safe_round(profit_factor_pct_legacy, 4),
        "profit_factor_estado": pf_estado,
        "ganancia_bruta_usdt": _safe_round(gross_profit_usdt, 4),
        "perdida_bruta_usdt": _safe_round(gross_loss_usdt_abs, 4),
        "numero_operaciones_perdedoras": n_losing,
        "expectativa_matematica_pct": _safe_round(expectancy_pct * 100, 4),
        "expectativa_matematica_usdt": _safe_round(expectancy_usdt, 4),
        "rentabilidad_neta_pct": _safe_round(net_return_pct, 4),
        "rentabilidad_diaria_media_pct": _safe_round(daily_mean, 5) if daily_mean is not NA else NA,
        "rentabilidad_diaria_mediana_pct": _safe_round(daily_median, 5) if daily_median is not NA else NA,
        "drawdown_maximo_pct": _safe_round(max_dd, 4) if max_dd is not None else NA,
        "ganancia_media_pct": _safe_round(avg_win_pct * 100, 4) if avg_win_pct is not NA else NA,
        "perdida_media_pct": _safe_round(avg_loss_pct * 100, 4) if avg_loss_pct is not NA else NA,
        "ganancia_promedio_por_operacion_usdt": _safe_round(float(pnl_usdt.mean()), 4),
        "ratio_beneficio_riesgo": _safe_round(risk_reward, 4) if risk_reward is not NA else NA,
        "tiempo_mantenimiento_medio_horas": _safe_round(avg_holding, 2),
    })
    return stats


def compute_benchmark_stats(benchmark_close: pd.Series, initial_capital: float, label: str) -> dict:
    """Benchmarks A (BTC buy&hold) / B (mantener 100 USDT) / C (exposición
    pasiva al universo elegible) — sección 9 de la orden. Se exporta SIEMPRE
    (defecto P1 de S2: se calculaba pero nunca se invocaba)."""
    clean = benchmark_close.dropna() if benchmark_close is not None else pd.Series(dtype=float)
    if len(clean) < 2:
        return {"benchmark": label, "rentabilidad_neta_pct": NA, "drawdown_maximo_pct": NA, "exposicion_pct": NA}
    ret = (clean.iloc[-1] / clean.iloc[0]) - 1.0
    equity = initial_capital * (clean / clean.iloc[0])
    dd = max_drawdown_pct(equity)
    return {
        "benchmark": label,
        "rentabilidad_neta_pct": _safe_round(ret * 100, 4),
        "drawdown_maximo_pct": _safe_round(dd, 4) if dd is not None else NA,
        "exposicion_pct": 100.0,
    }
