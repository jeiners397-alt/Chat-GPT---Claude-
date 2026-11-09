import pandas as pd

from src_s21.accounting import LedgerTrade, daily_equity, daily_returns, mark_to_market_curve, max_drawdown_pct


def _trade(symbol, entry, exit_, equity_before, equity_after, times, closes):
    qty = equity_before / closes[0]
    return LedgerTrade(
        symbol=symbol, entry_time=pd.Timestamp(entry), exit_time=pd.Timestamp(exit_),
        equity_before=equity_before, entry_price_effective=closes[0], exit_price_effective=closes[-1],
        qty=qty, commission_entry_usdt=0.0, commission_exit_usdt=0.0,
        gross_exit_value_usdt=qty * closes[-1], equity_after=equity_after,
        pnl_usdt=equity_after - equity_before, pnl_pct_net=(equity_after / equity_before) - 1,
        holding_hours=4.0,
        mtm_times=[pd.Timestamp(t) for t in times], mtm_closes=closes,
    )


def test_mtm_curve_reflects_intratrade_drawdown_not_only_close():
    """El defecto P0 de S2: _build_equity_curve solo registraba equity_after
    en exit_time, por lo que una caída fuerte y recuperación DENTRO de una
    operación ganadora era invisible en el drawdown. S2.1 debe capturarla."""
    times = ["2026-01-01T00:00", "2026-01-01T01:00", "2026-01-01T02:00", "2026-01-01T03:00"]
    closes = [100.0, 70.0, 70.0, 105.0]  # cae 30% intra-trade, luego cierra +5%
    t = _trade("AAAUSDT", times[0], times[-1], 100.0, 105.0, times, closes)

    curve = mark_to_market_curve([t], initial_capital=100.0)
    assert curve.iloc[-1] == 105.0  # cierre correcto, ganancia neta
    dd = max_drawdown_pct(curve)
    assert dd is not None and dd < -25.0, (
        "El drawdown mark-to-market debe reflejar la caída intra-operación del 30%, "
        "no solo el resultado final positivo."
    )


def test_daily_equity_and_returns_use_full_curve():
    times = pd.date_range("2026-01-01", periods=5, freq="1D", tz="UTC")
    closes = [100.0, 90.0, 95.0, 110.0, 108.0]
    t = _trade("AAAUSDT", times[0], times[-1], 100.0, 108.0, times, closes)
    curve = mark_to_market_curve([t], 100.0)
    d_eq = daily_equity(curve)
    d_ret = daily_returns(d_eq)
    assert len(d_eq) == 5
    assert abs(d_eq.iloc[0] - 100.0) < 1e-9
    assert len(d_ret) == 4


def test_mark_to_market_curve_empty_trades_returns_flat():
    curve = mark_to_market_curve([], initial_capital=100.0, start_time=pd.Timestamp("2026-01-01", tz="UTC"))
    assert len(curve) == 1
    assert curve.iloc[0] == 100.0
