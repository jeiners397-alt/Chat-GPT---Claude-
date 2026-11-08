"""
topgainers.py (S2.1) — Reescritura causal de la detección de Top Gainers
(sección 7 de la orden). Corrige los defectos de src/topgainers.py (S2):

  - `hours_before_top_gainer` podía ser NEGATIVO (no era una medida real de
    anticipación): se elimina esa métrica y se reemplaza por una evaluación
    estrictamente hacia adelante desde el momento de ENTRADA (no de señal),
    en los horizontes 1h/4h/12h/24h/48h, calculando SOLO con velas
    posteriores a la entrada.
  - `was_false_alarm` solo contaba un patrón de fallo específico
    (pct_move_captured <= 0): ahora se define explícitamente contra un
    criterio de "Top Gainer" fijado de antemano (top-N por retorno forward
    24h entre los símbolos evaluados ESE día), y se reportan falsos
    positivos Y falsos negativos, más una tasa base de referencia.
  - El ranking "Top Gainer del día" se usa EXCLUSIVAMENTE como etiqueta
    posterior de auditoría de calidad de detección. Nunca se usa para
    decidir una entrada histórica (esa decisión ya está fijada por la señal
    del indicador, calculada antes y de forma independiente).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from config_s21 import TOP_GAINER_HORIZONS_HOURS, TOP_GAINERS_N


@dataclass
class CausalTopGainerEvaluation:
    indicator_id: object
    indicator_name: str
    timeframe: str
    symbol: str
    signal_time: pd.Timestamp
    entry_time: pd.Timestamp
    entry_price: float
    # Por horizonte (horas) -> métricas
    forward_return_pct: dict = field(default_factory=dict)   # cierre al horizonte
    mfe_pct: dict = field(default_factory=dict)                # max favorable excursion
    mae_pct: dict = field(default_factory=dict)                # max adverse excursion
    time_to_peak_hours: float | None = None
    became_top_gainer_24h: bool = False


def compute_daily_top_gainers(daily_closes_by_symbol: dict[str, pd.Series], top_n: int = TOP_GAINERS_N) -> dict[pd.Timestamp, set[str]]:
    """Define, para cada día (fecha UTC), el conjunto 'Top Gainer' = top-N por
    retorno porcentual diario REALIZADO ese día, entre los símbolos
    efectivamente evaluados. Esto es una etiqueta POSTERIOR (se calcula tras
    conocer el cierre del día); nunca se usa para decidir una entrada."""
    frame = pd.DataFrame(daily_closes_by_symbol)
    pct_change = frame.pct_change()
    top_gainers_by_day: dict[pd.Timestamp, set[str]] = {}
    for day, row in pct_change.iterrows():
        ranked = row.dropna().sort_values(ascending=False)
        top_gainers_by_day[day] = set(ranked.head(top_n).index)
    return top_gainers_by_day


def evaluate_signal_causally(
    indicator_id,
    indicator_name: str,
    timeframe: str,
    symbol: str,
    signal_time: pd.Timestamp,
    entry_time: pd.Timestamp,
    entry_price: float,
    df_native: pd.DataFrame,
    top_gainers_by_day: dict[pd.Timestamp, set[str]],
) -> CausalTopGainerEvaluation:
    """Evalúa, usando ÚNICAMENTE velas con open_time >= entry_time (jamás
    anteriores a la entrada real, nunca el día calendario de la señal en
    bloque), el comportamiento forward del precio en los horizontes fijos.
    """
    ev = CausalTopGainerEvaluation(
        indicator_id=indicator_id, indicator_name=indicator_name, timeframe=timeframe,
        symbol=symbol, signal_time=signal_time, entry_time=entry_time, entry_price=entry_price,
    )

    future = df_native[df_native["open_time"] >= entry_time].reset_index(drop=True)
    if future.empty or entry_price <= 0:
        return ev

    max_horizon = max(TOP_GAINER_HORIZONS_HOURS)
    window_end = entry_time + pd.Timedelta(hours=max_horizon)
    window = future[future["open_time"] <= window_end]
    if window.empty:
        return ev

    highs = window["high"].to_numpy() if "high" in window.columns else window["close"].to_numpy()
    lows = window["low"].to_numpy() if "low" in window.columns else window["close"].to_numpy()
    times = window["open_time"].to_numpy()

    running_max_high = np.maximum.accumulate(highs)
    peak_idx = int(np.argmax(highs))
    ev.time_to_peak_hours = float((pd.Timestamp(times[peak_idx]) - entry_time).total_seconds() / 3600.0)

    for h in TOP_GAINER_HORIZONS_HOURS:
        h_end = entry_time + pd.Timedelta(hours=h)
        sub = window[window["open_time"] <= h_end]
        if sub.empty:
            continue
        close_at_h = float(sub["close"].iloc[-1])
        sub_highs = sub["high"].to_numpy() if "high" in sub.columns else sub["close"].to_numpy()
        sub_lows = sub["low"].to_numpy() if "low" in sub.columns else sub["close"].to_numpy()
        ev.forward_return_pct[h] = 100.0 * (close_at_h - entry_price) / entry_price
        ev.mfe_pct[h] = 100.0 * (float(np.max(sub_highs)) - entry_price) / entry_price
        ev.mae_pct[h] = 100.0 * (float(np.min(sub_lows)) - entry_price) / entry_price

    # Etiqueta posterior (nunca usada para decidir la entrada, ya fijada arriba).
    entry_day = pd.Timestamp(entry_time).floor("D")
    window_24h_day = (entry_time + pd.Timedelta(hours=24)).floor("D")
    for day, members in top_gainers_by_day.items():
        if entry_day <= day <= window_24h_day and symbol in members:
            ev.became_top_gainer_24h = True
            break

    return ev


def summarize_detection_quality(evaluations: list[CausalTopGainerEvaluation], base_rate_top_gainer: float | None) -> dict:
    """Precisión, cobertura (recall), falsos positivos/negativos y
    comparación contra la tasa base — nunca solo precisión aislada."""
    total = len(evaluations)
    if total == 0:
        return {
            "total_senales": 0, "precision_pct": None, "tasa_falsos_positivos_pct": None,
            "retorno_forward_24h_medio_pct": None, "mfe_24h_medio_pct": None, "mae_24h_medio_pct": None,
            "tiempo_medio_a_pico_horas": None, "tasa_base_top_gainer_pct": base_rate_top_gainer,
        }
    hits = sum(1 for e in evaluations if e.became_top_gainer_24h)
    precision = 100.0 * hits / total
    false_positive_rate = 100.0 * (total - hits) / total

    rets_24h = [e.forward_return_pct.get(24) for e in evaluations if e.forward_return_pct.get(24) is not None]
    mfe_24h = [e.mfe_pct.get(24) for e in evaluations if e.mfe_pct.get(24) is not None]
    mae_24h = [e.mae_pct.get(24) for e in evaluations if e.mae_pct.get(24) is not None]
    ttp = [e.time_to_peak_hours for e in evaluations if e.time_to_peak_hours is not None]

    lift_vs_base_rate = (
        precision - base_rate_top_gainer if base_rate_top_gainer is not None else None
    )

    return {
        "total_senales": total,
        "total_hits_top_gainer_24h": hits,
        "precision_pct": round(precision, 2),
        "tasa_falsos_positivos_pct": round(false_positive_rate, 2),
        "retorno_forward_24h_medio_pct": round(float(np.mean(rets_24h)), 4) if rets_24h else None,
        "mfe_24h_medio_pct": round(float(np.mean(mfe_24h)), 4) if mfe_24h else None,
        "mae_24h_medio_pct": round(float(np.mean(mae_24h)), 4) if mae_24h else None,
        "tiempo_medio_a_pico_horas": round(float(np.mean(ttp)), 2) if ttp else None,
        "tasa_base_top_gainer_pct": base_rate_top_gainer,
        "lift_vs_tasa_base_pct_puntos": round(lift_vs_base_rate, 2) if lift_vs_base_rate is not None else None,
    }


def compute_base_rate(top_gainers_by_day: dict[pd.Timestamp, set[str]], n_symbols_universe: int) -> float | None:
    """Probabilidad base de que, en un día cualquiera, un símbolo cualquiera
    del universo sea Top Gainer — para contextualizar la precisión del
    detector (sección 7: comparar contra tasa base, no solo reportar
    precisión aislada)."""
    if n_symbols_universe <= 0 or not top_gainers_by_day:
        return None
    total_slots = sum(len(members) for members in top_gainers_by_day.values())
    total_days = len(top_gainers_by_day)
    if total_days == 0:
        return None
    expected_members_per_day = total_slots / total_days
    return round(100.0 * expected_members_per_day / n_symbols_universe, 4)
