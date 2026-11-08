"""Verifica las reglas duras del motor de backtest (sección 4 del encargo):
sin look-ahead, entrada en la apertura siguiente, capital único compartido."""

import pandas as pd

from src.backtest import build_candidates_for_symbol, execute_experiment, horizon_to_bars
from tests.conftest import make_synthetic_df


def test_horizon_to_bars_conversion():
    assert horizon_to_bars(24, "1h") == 24
    assert horizon_to_bars(4, "15m") == 16
    assert horizon_to_bars(72, "4h") == 18
    assert horizon_to_bars(4, "1d") == 0  # horizonte menor al timeframe -> no evaluable


def test_entry_uses_next_bar_open_not_signal_bar_close():
    df = make_synthetic_df(seed=3, n=100)
    signal = pd.Series(False, index=df.index)
    signal.iloc[10] = True  # señal confirmada al cierre de la vela 10

    candidates, total_signals = build_candidates_for_symbol("TEST", df, signal, "1h", 24)
    assert total_signals == 1
    assert len(candidates) == 1
    cand = candidates[0]
    # La entrada debe ser el open de la vela 11 (siguiente a la señal), no el close de la 10.
    assert cand.entry_price_raw == df["open"].iloc[11]
    assert cand.entry_time == df["open_time"].iloc[11]
    # La salida debe ser exactamente `horizonte` velas después de la entrada.
    assert cand.exit_time == df["open_time"].iloc[11 + 24]


def test_candidate_dropped_when_horizon_exceeds_available_data():
    df = make_synthetic_df(seed=3, n=50)
    signal = pd.Series(False, index=df.index)
    signal.iloc[45] = True  # no hay suficientes velas futuras para horizonte=24

    candidates, total_signals = build_candidates_for_symbol("TEST", df, signal, "1h", 24)
    assert total_signals == 1  # la señal SÍ se cuenta
    assert len(candidates) == 0  # pero no genera una operación ejecutable


def test_single_shared_capital_blocks_overlapping_entries():
    df1 = make_synthetic_df(seed=1, n=100)
    df2 = make_synthetic_df(seed=2, n=100)

    sig1 = pd.Series(False, index=df1.index)
    sig1.iloc[5] = True  # entra en vela 6, sale en vela 6+10=16

    sig2 = pd.Series(False, index=df2.index)
    sig2.iloc[7] = True  # entraría en vela 8, DENTRO de la ventana de la posición anterior

    cands1, n1 = build_candidates_for_symbol("SYM1", df1, sig1, "1h", 10)
    cands2, n2 = build_candidates_for_symbol("SYM2", df2, sig2, "1h", 10)

    result = execute_experiment(
        1, "test", "1h", 10, cands1 + cands2, n1 + n2,
        initial_capital=100.0, commission_pct_per_side=0.0, slippage_pct_per_side=0.0,
    )
    assert result.total_signals == 2
    assert len(result.trades) == 1  # la segunda señal debe quedar bloqueada
    assert result.signals_skipped_capital_locked == 1


def test_non_overlapping_entries_both_execute():
    df = make_synthetic_df(seed=1, n=200)
    sig = pd.Series(False, index=df.index)
    sig.iloc[5] = True
    sig.iloc[100] = True  # muy posterior, no se superpone

    cands, n = build_candidates_for_symbol("SYM1", df, sig, "1h", 10)
    result = execute_experiment(
        1, "test", "1h", 10, cands, n, initial_capital=100.0,
        commission_pct_per_side=0.0, slippage_pct_per_side=0.0,
    )
    assert len(result.trades) == 2
    assert result.signals_skipped_capital_locked == 0


def test_commissions_and_slippage_reduce_equity_on_flat_price():
    """Con precio perfectamente plano, sin comisiones ni slippage el PnL debe
    ser ~0; con comisiones/slippage, el PnL neto debe ser negativo."""
    n = 50
    dates = pd.date_range("2026-01-01", periods=n, freq="1h", tz="UTC")
    flat = 100.0
    df = pd.DataFrame({
        "open_time": dates, "open": flat, "high": flat, "low": flat, "close": flat,
        "volume": 1000.0, "taker_buy_base_volume": 500.0,
    })
    sig = pd.Series(False, index=df.index)
    sig.iloc[5] = True
    cands, n_sig = build_candidates_for_symbol("FLAT", df, sig, "1h", 10)

    result_no_cost = execute_experiment(1, "t", "1h", 10, cands, n_sig, 100.0, 0.0, 0.0)
    result_with_cost = execute_experiment(1, "t", "1h", 10, cands, n_sig, 100.0, 0.001, 0.0005)

    assert abs(result_no_cost.final_equity - 100.0) < 1e-9
    assert result_with_cost.final_equity < 100.0
