"""Verifica el cálculo de estadísticas obligatorias (sección 5) y que las
métricas indefinidas se reporten como None (-> N/A), nunca inventadas."""

import pandas as pd

from src.backtest import ExperimentResult, Trade
from src.stats import compute_experiment_stats


def _trade(entry_time, exit_time, equity_before, equity_after, holding_hours=24.0, symbol="SYM"):
    return Trade(
        symbol=symbol, entry_time=pd.Timestamp(entry_time, tz="UTC"), entry_price=100.0,
        exit_time=pd.Timestamp(exit_time, tz="UTC"), exit_price=100.0,
        equity_before=equity_before, equity_after=equity_after,
        pnl_pct_net=(equity_after / equity_before) - 1.0, holding_hours=holding_hours,
    )


def test_no_trades_yields_na_not_fabricated_values():
    result = ExperimentResult(
        indicator_id=1, indicator_name="x", timeframe="1h", horizon_hours=24,
        initial_capital=100.0, final_equity=100.0, total_signals=5,
        signals_skipped_capital_locked=0, trades=[], symbols_with_signals=set(),
    )
    stats = compute_experiment_stats(result)
    assert stats["operaciones_ejecutadas"] == 0
    assert stats["win_rate_pct"] is None
    assert stats["profit_factor"] is None
    assert stats["rentabilidad_neta_pct"] is None


def test_basic_win_rate_and_profit_factor():
    trades = [
        _trade("2026-01-01", "2026-01-02", 100.0, 110.0),
        _trade("2026-01-03", "2026-01-04", 110.0, 99.0),
        _trade("2026-01-05", "2026-01-06", 99.0, 108.9),
    ]
    result = ExperimentResult(
        indicator_id=1, indicator_name="x", timeframe="1h", horizon_hours=24,
        initial_capital=100.0, final_equity=108.9, total_signals=3,
        signals_skipped_capital_locked=0, trades=trades,
        symbols_with_signals={"SYM"},
    )
    stats = compute_experiment_stats(result)
    assert stats["operaciones_ejecutadas"] == 3
    assert stats["win_rate_pct"] == round(100 * 2 / 3, 2)
    assert stats["rentabilidad_neta_pct"] == round(100 * ((108.9 / 100.0) - 1), 4)
    assert stats["profit_factor"] > 1.0  # dos ganadoras mayores que una perdedora


def test_drawdown_is_non_positive():
    trades = [
        _trade("2026-01-01", "2026-01-02", 100.0, 120.0),
        _trade("2026-01-03", "2026-01-04", 120.0, 90.0),
    ]
    result = ExperimentResult(
        indicator_id=1, indicator_name="x", timeframe="1h", horizon_hours=24,
        initial_capital=100.0, final_equity=90.0, total_signals=2,
        signals_skipped_capital_locked=0, trades=trades, symbols_with_signals={"SYM"},
    )
    stats = compute_experiment_stats(result)
    assert stats["drawdown_maximo_pct"] <= 0
