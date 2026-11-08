import pandas as pd
import pytest

from tests.conftest import make_synthetic_df
from src_s21.backtest import TradeCandidate, build_candidates_for_symbol, execute_experiment, horizon_to_bars


def _make_signal(df, idx_true):
    sig = pd.Series(False, index=df.index)
    sig.iloc[idx_true] = True
    return sig


def test_candidates_carry_mtm_price_path_and_scores():
    df = make_synthetic_df(seed=5, n=200, freq="1h")
    sig = _make_signal(df, [50])
    cands, n_sig = build_candidates_for_symbol("AAAUSDT", df, sig, "1h", 4)
    assert n_sig == 1
    assert len(cands) == 1
    c = cands[0]
    bars = horizon_to_bars(4, "1h")
    assert len(c.mtm_times) == bars + 1
    assert len(c.mtm_closes) == bars + 1
    assert c.mtm_times[0] == c.entry_time
    assert c.mtm_times[-1] == c.exit_time
    assert isinstance(c.liquidity_score, float)
    assert isinstance(c.quality_score, float)


def test_no_lookahead_candidate_dropped_if_insufficient_future_data():
    df = make_synthetic_df(seed=6, n=60, freq="1h")
    sig = _make_signal(df, [55])  # cerca del final, sin velas suficientes para horizonte 72h
    cands, n_sig = build_candidates_for_symbol("AAAUSDT", df, sig, "1h", 72)
    assert n_sig == 1
    assert len(cands) == 0


def _candidate(symbol, entry_time, entry_price, exit_time, exit_price, liq=1.0, qual=1.0):
    return TradeCandidate(
        symbol=symbol, signal_time=entry_time - pd.Timedelta(hours=1), entry_time=entry_time,
        entry_price_raw=entry_price, exit_time=exit_time, exit_price_raw=exit_price, horizon_hours=4,
        liquidity_score=liq, quality_score=qual,
        mtm_times=[entry_time, exit_time], mtm_closes=[entry_price, exit_price],
    )


def test_simultaneous_entries_tie_break_by_liquidity_method():
    """El defecto P0 de S2: ante entry_time EXACTAMENTE igual, el orden de
    ejecución dependía arbitrariamente del orden en que los símbolos fueron
    descargados. El método A (liquidez) debe elegir determinísticamente el
    candidato de mayor liquidity_score cuando hay empate de tiempo."""
    t0 = pd.Timestamp("2026-01-01T00:00", tz="UTC")
    t1 = pd.Timestamp("2026-01-01T04:00", tz="UTC")
    low_liquidity_first = _candidate("LOWLIQ", t0, 100.0, t1, 110.0, liq=1.0)
    high_liquidity_second = _candidate("HIGHLIQ", t0, 50.0, t1, 60.0, liq=100.0)
    # Deliberadamente en el orden "equivocado" (baja liquidez primero en la lista)
    cands = [low_liquidity_first, high_liquidity_second]

    result = execute_experiment(
        1, "test", "1h", 4, cands, 2, initial_capital=100.0,
        commission_pct_per_side=0.0, slippage_pct_per_side=0.0,
        selection_method="A_LIQUIDEZ",
    )
    assert len(result.trades) == 1
    assert result.trades[0].symbol == "HIGHLIQ", (
        "El método de selección por liquidez debe priorizar el candidato de mayor "
        "liquidity_score ante un empate exacto de entry_time, no el primero de la lista."
    )


def test_selection_method_c_random_is_reproducible_with_fixed_seed():
    t0 = pd.Timestamp("2026-01-01T00:00", tz="UTC")
    t1 = pd.Timestamp("2026-01-01T04:00", tz="UTC")
    cands = [_candidate("SYM_A", t0, 10.0, t1, 11.0), _candidate("SYM_B", t0, 20.0, t1, 22.0)]

    r1 = execute_experiment(1, "t", "1h", 4, cands, 2, 100.0, 0.0, 0.0, selection_method="C_ALEATORIA", selection_seed=7)
    r2 = execute_experiment(1, "t", "1h", 4, cands, 2, 100.0, 0.0, 0.0, selection_method="C_ALEATORIA", selection_seed=7)
    assert r1.trades[0].symbol == r2.trades[0].symbol


def test_selection_never_reorders_across_different_entry_times():
    """La causalidad no se puede violar: un candidato con entry_time POSTERIOR
    nunca puede ejecutarse antes que uno con entry_time anterior, sin importar
    el método de selección."""
    t0 = pd.Timestamp("2026-01-01T00:00", tz="UTC")
    t1 = pd.Timestamp("2026-01-01T04:00", tz="UTC")
    t2 = pd.Timestamp("2026-01-02T00:00", tz="UTC")
    t3 = pd.Timestamp("2026-01-02T04:00", tz="UTC")
    earlier = _candidate("EARLY", t0, 10.0, t1, 11.0, liq=1.0)
    later_higher_liquidity = _candidate("LATE", t2, 10.0, t3, 9.0, liq=1000.0)
    cands = [earlier, later_higher_liquidity]
    result = execute_experiment(1, "t", "1h", 4, cands, 2, 100.0, 0.0, 0.0, selection_method="A_LIQUIDEZ")
    assert [t.symbol for t in result.trades] == ["EARLY", "LATE"]


def test_shared_capital_still_blocks_overlapping_entries():
    t0 = pd.Timestamp("2026-01-01T00:00", tz="UTC")
    t1 = pd.Timestamp("2026-01-01T08:00", tz="UTC")  # posición abierta hasta aquí
    t_overlap = pd.Timestamp("2026-01-01T04:00", tz="UTC")  # dentro de la ventana anterior
    t_overlap_exit = pd.Timestamp("2026-01-01T10:00", tz="UTC")
    c1 = _candidate("A", t0, 100.0, t1, 110.0)
    c2 = _candidate("B", t_overlap, 50.0, t_overlap_exit, 60.0)
    result = execute_experiment(1, "t", "1h", 4, [c1, c2], 2, 100.0, 0.0, 0.0, selection_method="A_LIQUIDEZ")
    assert len(result.trades) == 1
    assert result.signals_skipped_capital_locked == 1
