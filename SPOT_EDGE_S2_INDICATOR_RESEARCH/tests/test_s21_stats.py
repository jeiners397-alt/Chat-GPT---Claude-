import pandas as pd

from src_s21.accounting import LedgerTrade
from src_s21.backtest import ExperimentResult
from src_s21.stats import compute_experiment_stats


def _ledger_trade(symbol, equity_before, equity_after, entry="2026-01-01T00:00", exit_="2026-01-01T04:00"):
    entry_t, exit_t = pd.Timestamp(entry, tz="UTC"), pd.Timestamp(exit_, tz="UTC")
    qty = equity_before / 100.0
    return LedgerTrade(
        symbol=symbol, entry_time=entry_t, exit_time=exit_t, equity_before=equity_before,
        entry_price_effective=100.0, exit_price_effective=100.0 * (equity_after / equity_before),
        qty=qty, commission_entry_usdt=0.0, commission_exit_usdt=0.0,
        gross_exit_value_usdt=equity_after, equity_after=equity_after,
        pnl_usdt=equity_after - equity_before, pnl_pct_net=(equity_after / equity_before) - 1,
        holding_hours=4.0, mtm_times=[entry_t, exit_t], mtm_closes=[100.0, 100.0 * (equity_after / equity_before)],
    )


def test_profit_factor_is_monetary_not_percentage_based():
    """Defecto P0 de S2: profit_factor se calculaba sobre pnl_pct_net (igual
    peso para cada operación sin importar su tamaño real en USDT). Al
    componer capital, una operación grande y una pequeña con el mismo % no
    pesan igual en USDT. S2.1 debe reportar PF monetario distinto del legacy
    porcentual cuando el tamaño de las operaciones varía con el capital."""
    trades = [
        _ledger_trade("A", equity_before=100.0, equity_after=150.0),   # +50 USDT, +50%
        _ledger_trade("B", equity_before=150.0, equity_after=120.0),   # -30 USDT, -20%
        _ledger_trade("C", equity_before=120.0, equity_after=60.0),    # -60 USDT, -50%
    ]
    for i in range(len(trades) - 1):
        trades[i + 1].entry_time = trades[i].exit_time
        trades[i + 1].exit_time = trades[i].exit_time + pd.Timedelta(hours=4)
        trades[i + 1].mtm_times = [trades[i + 1].entry_time, trades[i + 1].exit_time]

    result = ExperimentResult(
        indicator_id=1, indicator_name="test", timeframe="1h", horizon_hours=4,
        initial_capital=100.0, final_equity=60.0, total_signals=3,
        signals_skipped_capital_locked=0, trades=trades, symbols_with_signals={"A", "B", "C"},
        selection_method="A_LIQUIDEZ",
    )
    stats = compute_experiment_stats(result)
    pf_usdt = stats["profit_factor_usdt"]
    pf_pct_legacy = stats["profit_factor_pct_legacy"]
    assert pf_usdt is not None and pf_pct_legacy is not None
    assert abs(pf_usdt - pf_pct_legacy) > 1e-6, (
        "PF monetario y PF porcentual legacy deben diferir cuando el tamaño real de "
        "las operaciones (compuesto) difiere de su magnitud porcentual relativa."
    )
    # PF monetario correcto: ganancia bruta 50 / pérdida bruta (30+60=90) = 0.5555...
    assert abs(pf_usdt - (50.0 / 90.0)) < 1e-3  # stats redondea a 4 decimales


def test_infinite_profit_factor_reported_as_indefinido_not_inf():
    trades = [_ledger_trade("A", 100.0, 110.0)]
    result = ExperimentResult(
        indicator_id=1, indicator_name="t", timeframe="1h", horizon_hours=4, initial_capital=100.0,
        final_equity=110.0, total_signals=1, signals_skipped_capital_locked=0,
        trades=trades, symbols_with_signals={"A"}, selection_method="A_LIQUIDEZ",
    )
    stats = compute_experiment_stats(result)
    assert stats["profit_factor_usdt"] is None
    assert "indefinido" in stats["profit_factor_estado"]
    assert "no" in stats["profit_factor_estado"].lower() or "NO" in stats["profit_factor_estado"]


def test_drawdown_computed_from_mark_to_market_curve():
    t1 = _ledger_trade("A", 100.0, 150.0)
    t1.mtm_times = [t1.entry_time, t1.entry_time + pd.Timedelta(hours=2), t1.exit_time]
    t1.mtm_closes = [100.0, 50.0, 150.0]  # cae 50% intra-trade antes de cerrar ganador
    result = ExperimentResult(
        indicator_id=1, indicator_name="t", timeframe="1h", horizon_hours=4, initial_capital=100.0,
        final_equity=150.0, total_signals=1, signals_skipped_capital_locked=0,
        trades=[t1], symbols_with_signals={"A"}, selection_method="A_LIQUIDEZ",
    )
    stats = compute_experiment_stats(result)
    assert stats["drawdown_maximo_pct"] is not None
    assert stats["drawdown_maximo_pct"] < -20.0
