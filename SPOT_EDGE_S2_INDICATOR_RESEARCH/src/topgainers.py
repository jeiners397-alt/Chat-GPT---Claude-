"""
topgainers.py — Análisis de detección temprana de posibles Top Gainers
(sección 7 del encargo).

La condición de "Top Gainer" se usa EXCLUSIVAMENTE como etiqueta posterior
para evaluar señales ya generadas (nunca como información para decidir una
entrada histórica): se calcula con velas diarias y se compara contra el
momento de cada señal, que siempre es anterior.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from config import TOP_GAINERS_N, TOP_GAINER_FORWARD_WINDOW_HOURS


@dataclass
class TopGainerEvaluation:
    indicator_id: int
    indicator_name: str
    timeframe: str
    symbol: str
    signal_time: pd.Timestamp
    became_top_gainer: bool
    hours_before_top_gainer: float | None
    pct_move_captured: float | None
    was_false_alarm: bool
    kept_falling: bool


def compute_daily_top_gainers(daily_closes_by_symbol: dict[str, pd.Series], top_n: int = TOP_GAINERS_N) -> dict[pd.Timestamp, set[str]]:
    """Para cada día (fecha UTC), calcula el conjunto de símbolos que estuvieron
    entre los `top_n` por variación porcentual diaria.
    """
    frame = pd.DataFrame(daily_closes_by_symbol)
    pct_change = frame.pct_change()
    top_gainers_by_day: dict[pd.Timestamp, set[str]] = {}
    for day, row in pct_change.iterrows():
        ranked = row.dropna().sort_values(ascending=False)
        top_gainers_by_day[day] = set(ranked.head(top_n).index)
    return top_gainers_by_day


def evaluate_signal_vs_top_gainers(
    indicator_id: int,
    indicator_name: str,
    timeframe: str,
    symbol: str,
    signal_time: pd.Timestamp,
    df_1d: pd.DataFrame,
    top_gainers_by_day: dict[pd.Timestamp, set[str]],
) -> TopGainerEvaluation:
    signal_day = pd.Timestamp(signal_time).floor("D")
    window_end = signal_time + pd.Timedelta(hours=TOP_GAINER_FORWARD_WINDOW_HOURS)
    window_end_day = window_end.floor("D")

    became_top_gainer = False
    hours_before = None
    for day, members in top_gainers_by_day.items():
        if signal_day <= day <= window_end_day and symbol in members:
            became_top_gainer = True
            hours_before = (day - signal_time).total_seconds() / 3600.0
            break

    future_window = df_1d[(df_1d["open_time"] >= signal_time) & (df_1d["open_time"] <= window_end)]
    pct_move_captured = None
    kept_falling = False
    if len(future_window) >= 1:
        start_price = future_window["open"].iloc[0]
        end_price = future_window["close"].iloc[-1]
        if start_price > 0:
            pct_move_captured = 100.0 * (end_price - start_price) / start_price
            kept_falling = end_price < start_price

    was_false_alarm = not became_top_gainer and (pct_move_captured is not None and pct_move_captured <= 0)

    return TopGainerEvaluation(
        indicator_id=indicator_id,
        indicator_name=indicator_name,
        timeframe=timeframe,
        symbol=symbol,
        signal_time=signal_time,
        became_top_gainer=became_top_gainer,
        hours_before_top_gainer=hours_before,
        pct_move_captured=pct_move_captured,
        was_false_alarm=was_false_alarm,
        kept_falling=kept_falling,
    )


def summarize_detection_quality(evaluations: list[TopGainerEvaluation]) -> dict:
    total = len(evaluations)
    if total == 0:
        return {"precision_pct": None, "cobertura_pct": None, "tasa_falsas_alarmas_pct": None, "total_senales": 0}
    hits = sum(1 for e in evaluations if e.became_top_gainer)
    false_alarms = sum(1 for e in evaluations if e.was_false_alarm)
    precision = 100.0 * hits / total
    false_alarm_rate = 100.0 * false_alarms / total
    return {
        "precision_pct": round(precision, 2),
        "tasa_falsas_alarmas_pct": round(false_alarm_rate, 2),
        "total_senales": total,
        "total_hits_top_gainer": hits,
    }
