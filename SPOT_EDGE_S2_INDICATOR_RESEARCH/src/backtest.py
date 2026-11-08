"""
backtest.py — Motor de backtest LONG-only Spot, sin apalancamiento, sin
información futura (sección 4 del encargo).

Diseño en dos etapas, para evitar look-ahead y para respetar una única cuenta
ficticia compartida entre símbolos dentro de cada experimento
(indicador × timeframe × horizonte):

  1. DETECCIÓN (por símbolo, independiente): a partir de la señal booleana ya
     calculada (que sólo usa información hasta el cierre de la vela t), se
     generan "candidatos de operación": entrada en la apertura de t+1,
     salida en la apertura de t+1+horizonte. Ningún precio posterior a la
     señal se usa para decidir si entrar.

  2. EJECUCIÓN (global, cronológica, por experimento): todos los candidatos
     de todos los símbolos se ordenan por tiempo de entrada real y se
     procesan en ese orden sobre UNA sola cuenta de 100 USDT. Mientras una
     posición está abierta, cualquier candidato cuya entrada caiga dentro de
     esa ventana se descarta como "señal bloqueada por capital" (se cuenta en
     el total de señales, no en operaciones ejecutadas).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from config import TIMEFRAME_HOURS


@dataclass
class TradeCandidate:
    symbol: str
    signal_time: pd.Timestamp
    entry_time: pd.Timestamp
    entry_price_raw: float
    exit_time: pd.Timestamp
    exit_price_raw: float
    horizon_hours: int


@dataclass
class Trade:
    symbol: str
    entry_time: pd.Timestamp
    entry_price: float
    exit_time: pd.Timestamp
    exit_price: float
    equity_before: float
    equity_after: float
    pnl_pct_net: float
    holding_hours: float


@dataclass
class ExperimentResult:
    indicator_id: int
    indicator_name: str
    timeframe: str
    horizon_hours: int
    initial_capital: float
    final_equity: float
    total_signals: int
    signals_skipped_capital_locked: int
    trades: list = field(default_factory=list)
    symbols_with_signals: set = field(default_factory=set)


def horizon_to_bars(horizon_hours: int, timeframe: str) -> int:
    tf_hours = TIMEFRAME_HOURS[timeframe]
    return round(horizon_hours / tf_hours)


def build_candidates_for_symbol(
    symbol: str, df: pd.DataFrame, signal_series: pd.Series, timeframe: str, horizon_hours: int
) -> tuple[list[TradeCandidate], int]:
    """Devuelve (candidatos_válidos, total_señales_detectadas_en_la_serie).

    No aplica ninguna restricción de capital aquí: eso ocurre en la etapa de
    ejecución global. `total_señales` cuenta TODAS las veces que la señal es
    True, incluso si no hay suficientes velas futuras para completar el
    horizonte (esas quedan fuera de `candidatos_válidos` pero sí se contaron).
    """
    bars = horizon_to_bars(horizon_hours, timeframe)
    if bars < 1:
        return [], 0

    sig = signal_series.fillna(False)
    total_signals = int(sig.sum())
    if total_signals == 0:
        return [], 0

    n = len(df)
    opens = df["open"].to_numpy()
    times = df["open_time"].to_numpy()
    sig_idx = sig.to_numpy().nonzero()[0]

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
        candidates.append(
            TradeCandidate(
                symbol=symbol,
                signal_time=pd.Timestamp(times[i]),
                entry_time=pd.Timestamp(times[entry_idx]),
                entry_price_raw=float(entry_price),
                exit_time=pd.Timestamp(times[exit_idx]),
                exit_price_raw=float(exit_price),
                horizon_hours=horizon_hours,
            )
        )
    return candidates, total_signals


def execute_experiment(
    indicator_id: int,
    indicator_name: str,
    timeframe: str,
    horizon_hours: int,
    all_candidates: list[TradeCandidate],
    total_signals_across_symbols: int,
    initial_capital: float,
    commission_pct_per_side: float,
    slippage_pct_per_side: float,
) -> ExperimentResult:
    """Ejecuta, en orden cronológico global, los candidatos de TODOS los
    símbolos sobre una única cuenta ficticia de `initial_capital` USDT.
    """
    ordered = sorted(all_candidates, key=lambda c: c.entry_time)
    equity = initial_capital
    position_open_until: pd.Timestamp | None = None
    trades: list[Trade] = []
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
        capital_after_entry_fee = equity_before * (1 - commission_pct_per_side)
        qty = capital_after_entry_fee / effective_entry
        gross_exit_value = qty * effective_exit
        equity_after = gross_exit_value * (1 - commission_pct_per_side)

        pnl_pct_net = (equity_after / equity_before) - 1.0

        trades.append(
            Trade(
                symbol=cand.symbol,
                entry_time=cand.entry_time,
                entry_price=effective_entry,
                exit_time=cand.exit_time,
                exit_price=effective_exit,
                equity_before=equity_before,
                equity_after=equity_after,
                pnl_pct_net=pnl_pct_net,
                holding_hours=float(horizon_hours),
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
        trades=trades,
        symbols_with_signals=symbols_with_signals,
    )
