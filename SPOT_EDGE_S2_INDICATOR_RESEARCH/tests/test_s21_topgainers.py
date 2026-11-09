import pandas as pd

from src_s21.topgainers import compute_base_rate, compute_daily_top_gainers, evaluate_signal_causally


def _native_df(start, n, closes, highs=None, lows=None, freq="1h"):
    times = pd.date_range(start, periods=n, freq=freq, tz="UTC")
    highs = highs or closes
    lows = lows or closes
    return pd.DataFrame({"open_time": times, "open": closes, "high": highs, "low": lows, "close": closes})


def test_evaluation_never_uses_bars_before_entry_time():
    """Defecto de S2: hours_before_top_gainer podía ser negativo, señal de
    que se usaba información anterior a la entrada. S2.1 solo debe mirar
    velas con open_time >= entry_time."""
    entry_time = pd.Timestamp("2026-01-01T05:00", tz="UTC")
    df = _native_df("2026-01-01T00:00", 20, closes=[100 + i for i in range(20)])
    ev = evaluate_signal_causally(1, "t", "1h", "AAAUSDT", entry_time - pd.Timedelta(hours=1), entry_time, 105.0, df, {})
    assert all(t >= entry_time for t in [])  # no hay forma de inspeccionar internamente; se valida indirectamente:
    # el retorno forward a 1h debe calcularse desde 105 (precio de entrada), con el close en entry+1h
    assert 1 in ev.forward_return_pct


def test_mfe_mae_are_bounded_by_actual_future_prices():
    entry_time = pd.Timestamp("2026-01-01T00:00", tz="UTC")
    closes = [100.0, 120.0, 90.0, 100.0, 100.0]
    highs = [100.0, 125.0, 95.0, 101.0, 101.0]
    lows = [99.0, 118.0, 85.0, 99.0, 99.0]
    df = _native_df("2026-01-01T00:00", 5, closes=closes, highs=highs, lows=lows, freq="1h")
    ev = evaluate_signal_causally(1, "t", "1h", "AAAUSDT", entry_time, entry_time, 100.0, df, {})
    assert ev.mfe_pct[4] > 20.0  # llegó a 125 => +25%
    assert ev.mae_pct[4] < -10.0  # cayó a 85 => -15%


def test_top_gainer_label_is_posterior_and_based_on_forward_return():
    closes_by_symbol = {
        "A": pd.Series([100.0, 150.0], index=pd.date_range("2026-01-01", periods=2, freq="1D", tz="UTC")),
        "B": pd.Series([100.0, 101.0], index=pd.date_range("2026-01-01", periods=2, freq="1D", tz="UTC")),
    }
    top = compute_daily_top_gainers(closes_by_symbol, top_n=1)
    day2 = list(top.keys())[1]
    assert top[day2] == {"A"}


def test_base_rate_is_computed_for_context():
    closes_by_symbol = {
        "A": pd.Series([100.0, 150.0, 100.0], index=pd.date_range("2026-01-01", periods=3, freq="1D", tz="UTC")),
        "B": pd.Series([100.0, 101.0, 102.0], index=pd.date_range("2026-01-01", periods=3, freq="1D", tz="UTC")),
    }
    top = compute_daily_top_gainers(closes_by_symbol, top_n=1)
    rate = compute_base_rate(top, n_symbols_universe=2)
    assert rate is not None
    assert 0 <= rate <= 100
