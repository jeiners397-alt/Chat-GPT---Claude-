"""
backtest.py (S2.1) — Motor de backtest corregido.

Corrige, respecto a src/backtest.py (S2), los defectos P0 identificados por
la auditoría de ChatGPT:

  1. Sesgo de selección en señales simultáneas (sección 5): cuando varios
     candidatos de distintos símbolos comparten EXACTAMENTE el mismo
     entry_time, S2 los ordenaba con `sorted(..., key=entry_time)`, que al
     ser un sort estable preservaba el orden original de la lista (= orden en
     que se recorrieron los símbolos al descargar datos), es decir, un sesgo
     arbitrario e implícito. S2.1 implementa tres métodos de prioridad
     documentados y reproducibles (A: liquidez causal, B: calidad de señal
     causal, C: aleatoria con semillas fijas) que SOLO actúan como criterio
     de desempate cuando hay coincidencia exacta de entry_time — nunca eligen
     una entrada futura por delante de una presente, lo cual violaría
     causalidad.

  2. Contabilidad no mark-to-market (sección 3): cada TradeCandidate ahora
     lleva adjunta su trayectoria de precios de cierre entre entrada y salida
     (`mtm_times`/`mtm_closes`), capturada mientras el DataFrame del símbolo
     todavía está en memoria, para que accounting.py pueda construir el
     equity real en cada instante, no solo al cerrar.

  3. Profit Factor monetario (sección 4): se calcula en stats.py a partir de
     LedgerTrade.pnl_usdt, no de porcentajes.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from config_s21 import SELECTION_SCORE_LOOKBACK_BARS, TIMEFRAME_HOURS
from src_s21.accounting import LedgerTrade


@dataclass
class TradeCandidate:
    symbol: str
    signal_time: pd.Timestamp
    entry_time: pd.Timestamp
    entry_price_raw: float
    exit_time: pd.Timestamp
    exit_price_raw: float
    horizon_hours: int
    # Puntajes causales (calculados SOLO con información hasta la vela de
    # señal inclusive), usados únicamente para desempatar entry_time idénticos.
    liquidity_score: float
    quality_score: float
    # Trayectoria de cierres entre entry_idx y exit_idx (inclusive), para MTM.
    mtm_times: list = field(default_factory=list)
    mtm_closes: list = field(default_factory=list)


def horizon_to_bars(horizon_hours: int, timeframe: str) -> int:
    tf_hours = TIMEFRAME_HOURS[timeframe]
    return round(horizon_hours / tf_hours)


def build_candidates_for_symbol(
    symbol: str, df: pd.DataFrame, signal_series: pd.Series, timeframe: str, horizon_hours: int,
) -> tuple[list[TradeCandidate], int]:
    """Igual que en S2, pero añade: (a) price_path para MTM, (b) liquidity_score
    y quality_score causales calculados estrictamente con datos <= vela de
    señal (nunca usan la vela de entrada ni posteriores)."""
    bars = horizon_to_bars(horizon_hours, timeframe)
    if bars < 1:
        return [], 0

    sig = signal_series.fillna(False)
    total_signals = int(sig.sum())
    if total_signals == 0:
        return [], 0

    n = len(df)
    opens = df["open"].to_numpy()
    closes = df["close"].to_numpy()
    volumes = df["volume"].to_numpy()
    times = df["open_time"].to_numpy()
    sig_idx = sig.to_numpy().nonzero()[0]

    # Puntaje de calidad causal: momentum normalizado por volatilidad reciente
    # (ROC(lookback) / ATR%(lookback)), fórmula documentada y reproducible.
    lb = SELECTION_SCORE_LOOKBACK_BARS
    close_series = pd.Series(closes)
    roc = close_series.pct_change(lb)
    high = df["high"].to_numpy() if "high" in df.columns else closes
    low = df["low"].to_numpy() if "low" in df.columns else closes
    tr = pd.Series(np.maximum.reduce([
        np.asarray(high) - np.asarray(low),
        np.abs(np.asarray(high) - np.roll(closes, 1)),
        np.abs(np.asarray(low) - np.roll(closes, 1)),
    ]))
    atr_pct = (tr.rolling(lb).mean() / close_series).replace(0, np.nan)
    quality_raw = (roc / atr_pct).to_numpy()

    quote_vol_approx = pd.Series(closes * volumes)
    liquidity_raw = quote_vol_approx.rolling(lb).mean().to_numpy()

    candidates: list[TradeCandidate] = []
    for i in sig_idx:
        entry_idx = i + 1
        exit_idx = entry_idx + bars
        if exit_idx >= n:
            continue
        entry_price = opens[entry_idx]
        exit_price = opens[exit_idx]
        if pd.isna(entry_price) or pd.isna(exit_price) or entry_price <= 0:
            continue

        q_score = float(quality_raw[i]) if i < len(quality_raw) and np.isfinite(quality_raw[i]) else 0.0
        l_score = float(liquidity_raw[i]) if i < len(liquidity_raw) and np.isfinite(liquidity_raw[i]) else 0.0

        mtm_times = [pd.Timestamp(t) for t in times[entry_idx:exit_idx + 1]]
        mtm_closes = [float(c) for c in closes[entry_idx:exit_idx + 1]]

        candidates.append(
            TradeCandidate(
                symbol=symbol,
                signal_time=pd.Timestamp(times[i]),
                entry_time=pd.Timestamp(times[entry_idx]),
                entry_price_raw=float(entry_price),
                exit_time=pd.Timestamp(times[exit_idx]),
                exit_price_raw=float(exit_price),
                horizon_hours=horizon_hours,
                liquidity_score=l_score,
                quality_score=q_score,
                mtm_times=mtm_times,
                mtm_closes=mtm_closes,
            )
        )
    return candidates, total_signals


def _random_tie_key(seed: int, symbol: str, entry_time: pd.Timestamp) -> float:
    """Clave aleatoria reproducible: hash determinístico de (seed, symbol,
    entry_time), NO np.random global (que no sería reproducible entre runs
    si el orden de llamadas cambia)."""
    raw = f"{seed}|{symbol}|{entry_time.isoformat()}".encode("utf-8")
    digest = hashlib.sha256(raw).hexdigest()[:12]
    return int(digest, 16) / float(16 ** 12)


def _sort_key_for_method(cand: TradeCandidate, method: str, seed: int | None):
    if method == "A_LIQUIDEZ":
        return (cand.entry_time, -cand.liquidity_score)
    if method == "B_CALIDAD_SENAL":
        return (cand.entry_time, -cand.quality_score)
    if method == "C_ALEATORIA":
        return (cand.entry_time, _random_tie_key(seed or 0, cand.symbol, cand.entry_time))
    raise ValueError(f"Método de selección desconocido: {method}")


def execute_experiment(
    indicator_id,
    indicator_name: str,
    timeframe: str,
    horizon_hours: int,
    all_candidates: list[TradeCandidate],
    total_signals_across_symbols: int,
    initial_capital: float,
    commission_pct_per_side: float,
    slippage_pct_per_side: float,
    selection_method: str = "A_LIQUIDEZ",
    selection_seed: int | None = None,
):
    """Ejecuta cronológicamente, aplicando el método de selección elegido
    SOLO como desempate de entry_time idénticos (nunca reordena por tiempo:
    sigue siendo estrictamente causal)."""
    ordered = sorted(all_candidates, key=lambda c: _sort_key_for_method(c, selection_method, selection_seed))

    equity = initial_capital
    position_open_until: pd.Timestamp | None = None
    ledger_trades: list[LedgerTrade] = []
    skipped = 0
    symbols_with_signals: set = set()

    for cand in ordered:
        symbols_with_signals.add(cand.symbol)
        if position_open_until is not None and cand.entry_time < position_open_until:
            skipped += 1
            continue

        effective_entry = cand.entry_price_raw * (1 + slippage_pct_per_side)
        effective_exit = cand.exit_price_raw * (1 - slippage_pct_per_side)

        equity_before = equity
        commission_entry_usdt = equity_before * commission_pct_per_side
        capital_after_entry_fee = equity_before - commission_entry_usdt
        qty = capital_after_entry_fee / effective_entry
        gross_exit_value = qty * effective_exit
        commission_exit_usdt = gross_exit_value * commission_pct_per_side
        equity_after = gross_exit_value - commission_exit_usdt

        pnl_usdt = equity_after - equity_before
        pnl_pct_net = (equity_after / equity_before) - 1.0

        ledger_trades.append(
            LedgerTrade(
                symbol=cand.symbol,
                entry_time=cand.entry_time,
                exit_time=cand.exit_time,
                equity_before=equity_before,
                entry_price_effective=effective_entry,
                exit_price_effective=effective_exit,
                qty=qty,
                commission_entry_usdt=commission_entry_usdt,
                commission_exit_usdt=commission_exit_usdt,
                gross_exit_value_usdt=gross_exit_value,
                equity_after=equity_after,
                pnl_usdt=pnl_usdt,
                pnl_pct_net=pnl_pct_net,
                holding_hours=float(horizon_hours),
                mtm_times=cand.mtm_times,
                mtm_closes=cand.mtm_closes,
            )
        )
        equity = equity_after
        position_open_until = cand.exit_time

    return ExperimentResult(
        indicator_id=indicator_id,
        indicator_name=indicator_name,
        timeframe=timeframe,
        horizon_hours=horizon_hours,
        initial_capital=initial_capital,
        final_equity=equity,
        total_signals=total_signals_across_symbols,
        signals_skipped_capital_locked=skipped,
        trades=ledger_trades,
        symbols_with_signals=symbols_with_signals,
        selection_method=selection_method,
        selection_seed=selection_seed,
    )


@dataclass
class ExperimentResult:
    indicator_id: object
    indicator_name: str
    timeframe: str
    horizon_hours: int
    initial_capital: float
    final_equity: float
    total_signals: int
    signals_skipped_capital_locked: int
    trades: list = field(default_factory=list)
    symbols_with_signals: set = field(default_factory=set)
    selection_method: str = "A_LIQUIDEZ"
    selection_seed: int | None = None
