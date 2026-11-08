#!/usr/bin/env python3
"""
spot_edge_s21_research.py — SPOT EDGE S2.1: motor de investigación corregido
tras la auditoría de ChatGPT sobre la corrida S2 de 60 días
(AUDITORIA_CHATGPT_60D_FULL.md, run #42443550513).

Corrige, respecto a spot_indicator_research.py (S2):
  - Contabilidad: equity mark-to-market real (src_s21/accounting.py).
  - Profit Factor monetario en USDT, no porcentual (src_s21/stats.py).
  - Sesgo de selección en señales simultáneas: 3 métodos documentados y
    reproducibles, con análisis de sensibilidad (src_s21/backtest.py).
  - Universo: liquidez histórica real + exclusión de activos no-cripto
    (src_s21/universe.py); limitación de survivorship bias declarada.
  - Top Gainers: detección causal forward-only, 5 horizontes, MFE/MAE,
    comparación contra tasa base (src_s21/topgainers.py).
  - Benchmarks A/B/C efectivamente calculados y exportados.
  - Régimen BTC: usa el cierre del día ANTERIOR (sin fuga de información
    intradía).
  - Clasificación A-E + dimensión de robustez (ALTA/MEDIA/BAJA/INSUFICIENTE).

NO modifica ni elimina el código ni los resultados de S2
(SPOT_EDGE_S2_INDICATOR_RESEARCH/spot_indicator_research.py y
RESULTADOS_SPOT_EDGE_S2/ siguen intactos y reproducibles).

Etiqueta del desarrollo: SPOT EDGE S2.1 — RESEARCH ENGINE VERIFIED.

Uso:
    python spot_edge_s21_research.py --phase A --max-symbols 10
    python spot_edge_s21_research.py --phase B --max-symbols 10
"""

from __future__ import annotations

import argparse
import gc
import sys
import time
import traceback
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd

import config_s21
from src.binance_client import BinanceClient
from src.indicators.registry import STATUS_IMPLEMENTED, build_full_registry, get_signal_function
from src.logging_utils import get_logger
from src_s21.accounting import build_trade_ledger_rows, daily_equity, mark_to_market_curve
from src_s21.backtest import build_candidates_for_symbol, execute_experiment, horizon_to_bars
from src_s21.classification import classify_indicator_experiment, classify_robustness
from src_s21.results_writer import (
    ensure_results_dir,
    write_benchmarks,
    write_by_regime,
    write_by_symbol,
    write_causality_checklist,
    write_chronological_validation,
    write_data_coverage,
    write_eight_configs_audit,
    write_equity_daily,
    write_indicator_metrics,
    write_indicator_ranking,
    write_inverse_candidates,
    write_portfolio_accounting,
    write_selection_method_comparison,
    write_summary,
    write_top_gainers_causal,
    write_trade_ledger,
    write_universe_exclusions,
)
from src_s21.stats import compute_benchmark_stats, compute_experiment_stats
from src_s21.topgainers import compute_base_rate, compute_daily_top_gainers, evaluate_signal_causally, summarize_detection_quality
from src_s21.universe import SURVIVORSHIP_BIAS_NOTE, build_universe_candidates, finalize_universe_with_historical_liquidity

logger = get_logger("spot_edge_s21_research")

# Las 8 configuraciones "prometedoras" originales de S2, auditadas en
# AUDITORIA_CHATGPT_60D_FULL.md. Se auditan de nuevo aquí con el motor
# corregido (sección 10 de la orden) SI aparecen en esta corrida.
EIGHT_PROMISING_CONFIGS_S2 = [
    # EXACTAMENTE las 8 configuraciones categoria A del S2 de 60d.
    # No sustituir por TRIX (categoria D) ni por configuraciones negativas.
    # (indicator_name_substring, timeframe, horizon_hours)
    ("Shannon Entropy", "4h", 24),
    ("Choppiness", "1h", 4),
    ("Mass Index", "1h", 24),
    ("Klinger", "1d", 24),
    ("Choppiness", "4h", 4),
    ("DEMA", "4h", 24),
    ("Chande Momentum", "4h", 24),
    ("Kalman", "1d", 24),
]
EXTRAORDINARY_SYMBOLS = {"LSKUSDT", "ONEUSDT", "BMTUSDT"}

CAUSALITY_CHECKLIST_ITEMS = [
    ("1", "No se usan velas futuras para generar la señal", True,
     "Toda señal se calcula con df hasta la vela i inclusive; entrada es open[i+1] (src_s21/backtest.py)."),
    ("2", "La entrada ocurre después de la confirmación de la señal (open de la vela siguiente)", True,
     "entry_idx = i + 1 en build_candidates_for_symbol; nunca se usa open[i]."),
    ("3", "Indicadores de timeframe superior usan solo velas ya cerradas", True,
     "Los indicadores se calculan sobre el propio timeframe de evaluación; no se mezclan timeframes sin resample causal."),
    ("4", "El régimen BTC no usa el cierre del día aún no ocurrido", True,
     "_build_btc_regime_series_shifted desplaza el régimen 1 día (usa el cierre del día ANTERIOR completo)."),
    ("5", "Capital y comisiones se respetan (sin apalancamiento, comisión+slippage por lado)", True,
     "execute_experiment aplica commission_pct_per_side y slippage_pct_per_side en cada entrada/salida."),
    ("6", "Las salidas ocurren en instantes de precio genuinamente observables", True,
     "exit_price_raw = open[exit_idx], vela ya cerrada en el momento de la ejecución real."),
    ("7", "No hay operaciones duplicadas simultáneas dentro del mismo experimento", True,
     "position_open_until bloquea nuevas entradas mientras hay una posición abierta."),
    ("8", "El período de calentamiento (warm-up) no se cuenta como rendimiento", True,
     "mask_main_range excluye velas de warm-up antes de construir señales/candidatos."),
    ("9", "Ninguna operación se cierra usando datos posteriores al fin del experimento", True,
     "build_candidates_for_symbol descarta candidatos cuyo exit_idx exceda el DataFrame descargado (`if exit_idx >= n: continue`)."),
    ("10", "Reproducibilidad vía semillas y configuración congelada", True,
     "config_s21.py fija umbrales antes de ejecutar; RANDOM_SELECTION_SEEDS fijas para el método C."),
]


def parse_args():
    p = argparse.ArgumentParser(description="SPOT EDGE S2.1 — motor corregido")
    p.add_argument("--phase", choices=["A", "B"], default="A")
    p.add_argument("--max-symbols", type=int, default=0)
    p.add_argument("--timeframes", type=str, default=",".join(config_s21.TIMEFRAMES))
    p.add_argument("--results-dir", type=str, default="")
    p.add_argument("--symbols", type=str, default="")
    p.add_argument("--no-cost-sensitivity", action="store_true")
    p.add_argument("--no-selection-sensitivity", action="store_true")
    p.add_argument("--max-runtime-minutes", type=float, default=0.0)
    args = p.parse_args()

    start_iso = config_s21.PHASE_A_START_ISO if args.phase == "A" else config_s21.PHASE_B_START_ISO
    end_iso = config_s21.PHASE_A_END_ISO if args.phase == "A" else config_s21.PHASE_B_END_ISO
    results_dir = args.results_dir or (
        config_s21.RESULTS_DIR_NAME if args.phase == "A" else f"{config_s21.RESULTS_DIR_NAME}_PHASE_B"
    )

    cfg = config_s21.RunConfigS21(
        phase=args.phase, start_iso=start_iso, end_iso=end_iso,
        timeframes=tuple(t.strip() for t in args.timeframes.split(",") if t.strip()),
        max_symbols=args.max_symbols, results_dir=results_dir,
        symbols_override=tuple(s.strip().upper() for s in args.symbols.split(",") if s.strip()),
        run_cost_sensitivity=not args.no_cost_sensitivity,
        run_selection_sensitivity=not args.no_selection_sensitivity,
        max_runtime_minutes=args.max_runtime_minutes,
    )
    return cfg


def _build_btc_regime_series_shifted(btc_daily_df: pd.DataFrame | None) -> dict:
    """Corrige el P1 de S2: usa el cierre del día ANTERIOR (shift(1)) para
    etiquetar el régimen, evitando que una entrada intradía se etiquete con
    información del cierre del propio día aún no ocurrido."""
    if btc_daily_df is None or len(btc_daily_df) < 51:
        return {}
    close = btc_daily_df.set_index("open_time")["close"]
    ema20 = close.ewm(span=20, adjust=False, min_periods=20).mean()
    ema50 = close.ewm(span=50, adjust=False, min_periods=50).mean()
    trend = (ema20 > ema50).map({True: "ALCISTA", False: "BAJISTA"})
    trend_shifted = trend.shift(1)
    # El índice de trend_shifted(day) ahora representa "régimen conocido AL
    # INICIO del día `day`", calculado con el cierre del día anterior.
    return trend_shifted.dropna().to_dict()


def main() -> int:
    cfg = parse_args()
    run_started_at = time.time()
    deadline = run_started_at + cfg.max_runtime_minutes * 60 if cfg.max_runtime_minutes > 0 else None
    incomplete_run = False

    logger.info(f"SPOT EDGE S2.1 — RESEARCH ENGINE VERIFIED | fase={cfg.phase} | {cfg.start_iso} -> {cfg.end_iso}")

    results_dir = ensure_results_dir(cfg.results_dir)
    client = BinanceClient()

    start_dt = datetime.fromisoformat(cfg.start_iso.replace("Z", "+00:00"))
    end_dt = datetime.fromisoformat(cfg.end_iso.replace("Z", "+00:00"))
    exploration_end_dt = start_dt + (end_dt - start_dt) * config_s21.EXPLORATION_FRACTION

    # 1. Universo — paso 1 (metadatos + prefiltro barato) ----------------------
    candidate_symbols, universe_exclusions_meta = build_universe_candidates(
        client, cfg.max_symbols, cfg.symbols_override
    )
    symbols_for_fetch = candidate_symbols if "BTCUSDT" in candidate_symbols else ["BTCUSDT"] + candidate_symbols
    logger.info(f"Candidatos a descargar: {len(symbols_for_fetch)} (incluye BTCUSDT de referencia)")

    registry_defs = build_full_registry()
    implemented_defs = [d for d in registry_defs if d.implementation_status == STATUS_IMPLEMENTED]

    candidates_by_experiment: dict[tuple, list] = {}
    total_signals_by_experiment: dict[tuple, int] = {}
    candidates_by_experiment_exploration: dict[tuple, list] = {}
    candidates_by_experiment_confirmation: dict[tuple, list] = {}
    coverage_records: list[dict] = []
    daily_closes_by_symbol: dict[str, pd.Series] = {}
    daily_df_by_symbol: dict[str, pd.DataFrame] = {}
    native_df_by_symbol_tf: dict[tuple, pd.DataFrame] = {}  # (symbol, tf) -> df, SOLO para 1 tf de referencia top-gainers
    btc_close_by_timeframe: dict[str, pd.Series] = {}

    main_start_ts = pd.Timestamp(start_dt, tz="UTC") if start_dt.tzinfo is None else pd.Timestamp(start_dt)
    exploration_end_ts = pd.Timestamp(exploration_end_dt, tz="UTC") if exploration_end_dt.tzinfo is None else pd.Timestamp(exploration_end_dt)

    for sym_idx, symbol in enumerate(symbols_for_fetch, start=1):
        if deadline and time.time() > deadline:
            incomplete_run = True
            logger.warning("Límite de tiempo alcanzado. Deteniendo descarga.")
            break
        logger.info(f"[{sym_idx}/{len(symbols_for_fetch)}] {symbol}")
        per_tf_df: dict[str, pd.DataFrame] = {}

        for tf in cfg.timeframes:
            warmup_days = config_s21.WARMUP_DAYS_BY_TIMEFRAME[tf]
            fetch_start = start_dt - timedelta(days=warmup_days)
            start_ms = int(fetch_start.timestamp() * 1000)
            end_ms = int(end_dt.timestamp() * 1000)
            try:
                df, record = client.get_klines_dataframe(symbol, tf, start_ms, end_ms)
            except Exception as exc:  # noqa: BLE001
                logger.error(f"Error descargando {symbol} {tf}: {exc}")
                coverage_records.append({"symbol": symbol, "timeframe": tf, "candles_received": 0, "gaps_detected": 0, "error": str(exc)})
                continue
            coverage_records.append(record.to_dict())
            if df.empty or len(df) < 30:
                continue
            per_tf_df[tf] = df
            if tf == "1d":
                daily_closes_by_symbol[symbol] = df.set_index("open_time")["close"]
                daily_df_by_symbol[symbol] = df
            if symbol == "BTCUSDT":
                btc_close_by_timeframe[tf] = df.set_index("open_time")["close"]

        per_tf_df_cache = dict(per_tf_df)  # conservar referencia para top-gainers causal (misma memoria del símbolo)
        del per_tf_df
        gc.collect()
        native_df_by_symbol_tf[symbol] = per_tf_df_cache

    # 2. Universo — paso 2: liquidez histórica real ----------------------------
    final_universe, universe_exclusions_liq = finalize_universe_with_historical_liquidity(
        daily_df_by_symbol, [s for s in candidate_symbols if s != "BTCUSDT"]
    )
    final_universe_set = set(final_universe) | {"BTCUSDT"}
    all_exclusions = universe_exclusions_meta + universe_exclusions_liq
    logger.info(f"Universo final (liquidez histórica real): {len(final_universe)} símbolos.")

    # 3. Señales + candidatos (solo para símbolos del universo final) ----------
    ind_def_by_id = {d.catalog_id: d for d in implemented_defs}
    for symbol, per_tf_df in native_df_by_symbol_tf.items():
        if symbol not in final_universe_set:
            continue
        for tf, df in per_tf_df.items():
            mask_main_range = df["open_time"] >= main_start_ts
            btc_close_ref = btc_close_by_timeframe.get(tf)
            for ind_def in implemented_defs:
                if tf not in ind_def.timeframes:
                    continue
                try:
                    sig_fn = get_signal_function(ind_def.signal_function_name)
                    sig_full = sig_fn(df, btc_close=btc_close_ref)
                except Exception as exc:  # noqa: BLE001
                    logger.error(f"Error señal {ind_def.name} {symbol}/{tf}: {exc}")
                    continue
                sig_masked = sig_full.fillna(False) & mask_main_range
                sig_exploration = sig_masked & (df["open_time"] < exploration_end_ts)
                sig_confirmation = sig_masked & (df["open_time"] >= exploration_end_ts)

                for horizon in cfg.horizons_hours:
                    bars = horizon_to_bars(horizon, tf)
                    if bars < 1:
                        continue
                    key = (ind_def.catalog_id, tf, horizon)
                    cands, n_sig = build_candidates_for_symbol(symbol, df, sig_masked, tf, horizon)
                    candidates_by_experiment.setdefault(key, []).extend(cands)
                    total_signals_by_experiment[key] = total_signals_by_experiment.get(key, 0) + n_sig
                    cands_e, _ = build_candidates_for_symbol(symbol, df, sig_exploration, tf, horizon)
                    candidates_by_experiment_exploration.setdefault(key, []).extend(cands_e)
                    cands_c, _ = build_candidates_for_symbol(symbol, df, sig_confirmation, tf, horizon)
                    candidates_by_experiment_confirmation.setdefault(key, []).extend(cands_c)

    regime_by_day = _build_btc_regime_series_shifted(daily_df_by_symbol.get("BTCUSDT"))

    # 4. Ejecución de cada experimento -----------------------------------------
    metrics_rows, ranking_rows, by_symbol_rows, by_regime_rows = [], [], [], []
    trade_ledger_rows, equity_daily_rows, portfolio_rows = [], [], []
    selection_comparison_rows, inverse_candidates_rows = [], []
    classification_counts: dict[str, int] = {}

    def _run(ind_id, name, tf, horizon, cands, n_sig, method, seed=None, commission_mult=1.0, exclude_symbols=None):
        use_cands = cands if not exclude_symbols else [c for c in cands if c.symbol not in exclude_symbols]
        res = execute_experiment(
            ind_id, name, tf, horizon, use_cands, n_sig, cfg.initial_capital_usdt,
            cfg.commission_pct_per_side * commission_mult, cfg.slippage_pct_per_side * commission_mult,
            selection_method=method, selection_seed=seed,
        )
        return res, compute_experiment_stats(res)

    for key, cands in candidates_by_experiment.items():
        ind_id, tf, horizon = key
        ind_def = ind_def_by_id[ind_id]
        n_sig = total_signals_by_experiment.get(key, 0)

        full_result, full_stats = _run(ind_id, ind_def.name, tf, horizon, cands, n_sig, cfg.selection_method)

        expl_cands = candidates_by_experiment_exploration.get(key, [])
        conf_cands = candidates_by_experiment_confirmation.get(key, [])
        _, expl_stats = _run(ind_id, ind_def.name, tf, horizon, expl_cands, len(expl_cands), cfg.selection_method)
        _, conf_stats = _run(ind_id, ind_def.name, tf, horizon, conf_cands, len(conf_cands), cfg.selection_method)

        category, motivo = classify_indicator_experiment(full_stats, expl_stats, conf_stats)
        classification_counts[category] = classification_counts.get(category, 0) + 1

        row = dict(full_stats)
        row["categoria"] = category
        row["motivo_categoria"] = motivo
        row["rentabilidad_neta_pct_exploracion"] = expl_stats.get("rentabilidad_neta_pct")
        row["rentabilidad_neta_pct_comprobacion"] = conf_stats.get("rentabilidad_neta_pct")

        # Sensibilidad a costos 1x/2x/3x — solo si hay operaciones.
        stats_3x = None
        if cfg.run_cost_sensitivity and full_result.trades:
            for mult in config_s21.COMMISSION_SENSITIVITY_MULTIPLIERS:
                if mult == 1.0:
                    continue
                _, s_mult = _run(ind_id, ind_def.name, tf, horizon, cands, n_sig, cfg.selection_method, commission_mult=mult)
                row[f"rentabilidad_neta_pct_comision_x{int(mult)}"] = s_mult.get("rentabilidad_neta_pct")
                if mult == 3.0:
                    stats_3x = s_mult

        # Robustez: dependencia de operación extrema (re-simulación real, no resta matemática).
        extreme_removed_stats = None
        largest_gain = None
        if full_result.trades:
            best_trade = max(full_result.trades, key=lambda t: t.pnl_usdt)
            largest_gain = best_trade.pnl_usdt
            if largest_gain > 0:
                _, extreme_removed_stats = _run(
                    ind_id, ind_def.name, tf, horizon, cands, n_sig, cfg.selection_method,
                    exclude_symbols={best_trade.symbol},
                )
        robustness, robustness_motivo = classify_robustness(
            full_stats, stats_3x, extreme_removed_stats, len(full_result.symbols_with_signals), largest_gain,
        )
        row["robustez"] = robustness
        row["robustez_motivo"] = robustness_motivo
        metrics_rows.append(row)
        ranking_rows.append(row)

        if category == "C_MUY_NEGATIVO":
            inverse_candidates_rows.append({
                "catalog_id": ind_id, "name": ind_def.name, "timeframe": tf, "horizon_hours": horizon,
                "rentabilidad_neta_pct_long": full_stats.get("rentabilidad_neta_pct"),
                "profit_factor_usdt_long": full_stats.get("profit_factor_usdt"),
                "operaciones_ejecutadas": full_stats.get("operaciones_ejecutadas"),
                "robustez": robustness, "motivo": motivo,
                "nota": "CLASIFICACIÓN ÚNICAMENTE. No se ejecuta ninguna inversión de señal en esta fase.",
            })

        by_symbol_rows.extend(_aggregate_by_symbol(ind_id, ind_def.name, tf, horizon, full_result.trades))
        by_regime_rows.extend(_aggregate_by_regime(ind_id, ind_def.name, tf, horizon, full_result.trades, regime_by_day))
        trade_ledger_rows.extend(build_trade_ledger_rows(full_result.trades, ind_id, ind_def.name, tf, horizon))

        if full_result.trades:
            mtm_curve = mark_to_market_curve(full_result.trades, cfg.initial_capital_usdt)
            d_eq = daily_equity(mtm_curve)
            for ts, eq in d_eq.items():
                equity_daily_rows.append({"catalog_id": ind_id, "name": ind_def.name, "timeframe": tf, "horizon_hours": horizon, "fecha": ts.isoformat(), "equity_usdt": round(float(eq), 6)})
            cash = cfg.initial_capital_usdt
            for t in full_result.trades:
                portfolio_rows.append({
                    "catalog_id": ind_id, "name": ind_def.name, "timeframe": tf, "horizon_hours": horizon,
                    "evento": "ENTRADA", "timestamp": t.entry_time.isoformat(), "symbol": t.symbol,
                    "cash_usdt": 0.0, "valor_posicion_usdt": round(t.equity_before, 6), "equity_total_usdt": round(t.equity_before, 6),
                })
                portfolio_rows.append({
                    "catalog_id": ind_id, "name": ind_def.name, "timeframe": tf, "horizon_hours": horizon,
                    "evento": "SALIDA", "timestamp": t.exit_time.isoformat(), "symbol": t.symbol,
                    "cash_usdt": round(t.equity_after, 6), "valor_posicion_usdt": 0.0, "equity_total_usdt": round(t.equity_after, 6),
                })

        # -- Sensibilidad al método de selección (solo A/C/D, el resto no aporta al análisis de sesgo) --
        if cfg.run_selection_sensitivity and category in ("A_PROMETEDOR", "C_MUY_NEGATIVO") and full_result.trades:
            comp_row = {"catalog_id": ind_id, "name": ind_def.name, "timeframe": tf, "horizon_hours": horizon,
                        "rentabilidad_neta_pct_metodo_A_liquidez": full_stats.get("rentabilidad_neta_pct")}
            _, stats_b = _run(ind_id, ind_def.name, tf, horizon, cands, n_sig, config_s21.SELECTION_METHOD_QUALITY)
            comp_row["rentabilidad_neta_pct_metodo_B_calidad"] = stats_b.get("rentabilidad_neta_pct")
            rets_c = []
            for seed in config_s21.RANDOM_SELECTION_SEEDS:
                _, stats_c = _run(ind_id, ind_def.name, tf, horizon, cands, n_sig, config_s21.SELECTION_METHOD_RANDOM, seed=seed)
                r = stats_c.get("rentabilidad_neta_pct")
                if r is not None:
                    rets_c.append(r)
            comp_row["rentabilidad_neta_pct_metodo_C_aleatoria_media"] = round(float(np.mean(rets_c)), 4) if rets_c else None
            comp_row["rentabilidad_neta_pct_metodo_C_aleatoria_rango"] = round(float(np.max(rets_c) - np.min(rets_c)), 4) if len(rets_c) > 1 else None
            comp_row["sensible_al_metodo_de_seleccion"] = (
                comp_row["rentabilidad_neta_pct_metodo_A_liquidez"] is not None
                and comp_row["rentabilidad_neta_pct_metodo_B_calidad"] is not None
                and (comp_row["rentabilidad_neta_pct_metodo_A_liquidez"] > 0) != (comp_row["rentabilidad_neta_pct_metodo_B_calidad"] > 0)
            )
            selection_comparison_rows.append(comp_row)

    # 5. Auditoría de las 8 configuraciones originalmente "prometedoras" -------
    eight_configs_rows = []
    for name_substr, tf_target, horizon_target in EIGHT_PROMISING_CONFIGS_S2:
        for key, cands in candidates_by_experiment.items():
            ind_id, tf, horizon = key
            if tf != tf_target or horizon != horizon_target:
                continue
            ind_def = ind_def_by_id.get(ind_id)
            if ind_def is None or name_substr.lower() not in ind_def.name.lower():
                continue
            n_sig = total_signals_by_experiment.get(key, 0)
            row = {"indicator_name": ind_def.name, "timeframe": tf, "horizon_hours": horizon}
            res_a, stats_a = _run(ind_id, ind_def.name, tf, horizon, cands, n_sig, cfg.selection_method)
            row["test_A_reproduccion_rentabilidad_neta_pct"] = stats_a.get("rentabilidad_neta_pct")
            row["test_B_pf_usdt_contabilidad_corregida"] = stats_a.get("profit_factor_usdt")
            for mult in config_s21.COMMISSION_SENSITIVITY_MULTIPLIERS:
                _, s_m = _run(ind_id, ind_def.name, tf, horizon, cands, n_sig, cfg.selection_method, commission_mult=mult)
                row[f"test_C_rentabilidad_neta_pct_costo_x{int(mult)}"] = s_m.get("rentabilidad_neta_pct")
            present_extraordinary = {t.symbol for t in res_a.trades} & EXTRAORDINARY_SYMBOLS
            if present_extraordinary:
                _, s_excl = _run(ind_id, ind_def.name, tf, horizon, cands, n_sig, cfg.selection_method, exclude_symbols=present_extraordinary)
                row["test_D_simbolos_extraordinarios_excluidos"] = ",".join(sorted(present_extraordinary))
                row["test_D_rentabilidad_neta_pct_sin_extraordinarios"] = s_excl.get("rentabilidad_neta_pct")
            else:
                row["test_D_simbolos_extraordinarios_excluidos"] = "ninguno_presente_en_esta_corrida"
                row["test_D_rentabilidad_neta_pct_sin_extraordinarios"] = None
            row["test_E_numero_activos_con_senal"] = stats_a.get("numero_activos_con_senal")
            match = next((r for r in selection_comparison_rows if r["catalog_id"] == ind_id and r["timeframe"] == tf and r["horizon_hours"] == horizon), None)
            row["test_F_sensible_al_metodo_de_seleccion"] = match.get("sensible_al_metodo_de_seleccion") if match else "no_evaluado_en_esta_corrida"
            eight_configs_rows.append(row)

    # 6. Top Gainers causales ---------------------------------------------------
    top_gainers_rows = []
    base_rate = None
    if daily_closes_by_symbol:
        top_gainers_by_day = compute_daily_top_gainers({s: c for s, c in daily_closes_by_symbol.items() if s in final_universe_set})
        base_rate = compute_base_rate(top_gainers_by_day, len(final_universe_set))
        for key, cands in candidates_by_experiment.items():
            ind_id, tf, horizon = key
            ind_def = ind_def_by_id[ind_id]
            evals = []
            for cand in cands:
                native_df = native_df_by_symbol_tf.get(cand.symbol, {}).get(tf)
                if native_df is None:
                    continue
                evals.append(evaluate_signal_causally(
                    ind_id, ind_def.name, tf, cand.symbol, cand.signal_time, cand.entry_time,
                    cand.entry_price_raw, native_df, top_gainers_by_day,
                ))
            if evals:
                summary = summarize_detection_quality(evals, base_rate)
                summary.update({"catalog_id": ind_id, "name": ind_def.name, "timeframe": tf, "horizon_hours": horizon})
                top_gainers_rows.append(summary)

    # 7. Benchmarks A/B/C ---------------------------------------------------------
    benchmark_rows = []
    btc_daily = btc_close_by_timeframe.get("1d")
    benchmark_rows.append(compute_benchmark_stats(btc_daily, cfg.initial_capital_usdt, "A_BTC_BUY_AND_HOLD"))
    benchmark_rows.append({"benchmark": "B_MANTENER_100_USDT", "rentabilidad_neta_pct": 0.0, "drawdown_maximo_pct": 0.0, "exposicion_pct": 0.0})
    if daily_closes_by_symbol and final_universe:
        universe_frame = pd.DataFrame({s: c for s, c in daily_closes_by_symbol.items() if s in final_universe}).dropna(how="all")
        if not universe_frame.empty:
            normalized = universe_frame / universe_frame.iloc[0]
            passive_basket = normalized.mean(axis=1) * cfg.initial_capital_usdt
            benchmark_rows.append(compute_benchmark_stats(passive_basket, cfg.initial_capital_usdt, "C_EXPOSICION_PASIVA_UNIVERSO"))

    # 8. Validación cronológica (solo metadatos de esta fase; la comparación
    #    A-vs-B se escribe por scripts/compare_phases.py tras correr ambas fases).
    chrono_rows = [{
        "fase": cfg.phase, "inicio": cfg.start_iso, "fin": cfg.end_iso,
        "usado_para_seleccion_de_parametros": cfg.phase == "A",
        "nota": "Fase A reproduce el período original S2. Fase B es histórico adicional, nunca usado para elegir indicadores/umbrales."
                if cfg.phase == "A" else
                "Fase B precede a la Fase A y no fue usada para seleccionar parámetros, indicadores ni umbrales.",
    }]

    # 9. Escritura ---------------------------------------------------------------
    write_indicator_metrics(results_dir, metrics_rows)
    write_indicator_ranking(results_dir, ranking_rows)
    write_by_symbol(results_dir, by_symbol_rows)
    write_by_regime(results_dir, by_regime_rows)
    write_trade_ledger(results_dir, trade_ledger_rows)
    write_equity_daily(results_dir, equity_daily_rows)
    write_portfolio_accounting(results_dir, portfolio_rows)
    write_selection_method_comparison(results_dir, selection_comparison_rows)
    write_universe_exclusions(results_dir, [vars(e) for e in all_exclusions], SURVIVORSHIP_BIAS_NOTE)
    write_top_gainers_causal(results_dir, top_gainers_rows)
    write_eight_configs_audit(results_dir, eight_configs_rows)
    write_inverse_candidates(results_dir, inverse_candidates_rows)
    write_benchmarks(results_dir, benchmark_rows)
    write_chronological_validation(results_dir, chrono_rows)
    write_causality_checklist(results_dir, [
        {"punto": p, "descripcion": d, "cumplido": c, "justificacion": j} for p, d, c, j in CAUSALITY_CHECKLIST_ITEMS
    ])
    write_data_coverage(results_dir, coverage_records)

    write_summary(results_dir, {
        "etiqueta": "SPOT EDGE S2.1 — RESEARCH ENGINE VERIFIED",
        "fase": cfg.phase, "periodo": {"inicio": cfg.start_iso, "fin": cfg.end_iso},
        "universo_candidatos": len(candidate_symbols), "universo_final": len(final_universe),
        "indicadores_implementados_evaluados": len(implemented_defs),
        "total_indicadores_catalogo": len(registry_defs),
        "clasificacion_counts": classification_counts,
        "tasa_base_top_gainer_pct": base_rate,
        "ejecucion_incompleta": incomplete_run,
        "duracion_segundos": round(time.time() - run_started_at, 1),
        "advertencia_comparaciones_multiples": (
            f"Se evaluaron {len(candidates_by_experiment)} combinaciones indicador×timeframe×horizonte. "
            "Con tantas comparaciones simultáneas, una fracción de resultados 'Categoría A' se espera por "
            "azar puro (data dredging). Ningún resultado individual debe interpretarse como validado sin "
            "confirmación independiente en la Fase B y en datos futuros (Fase C, aún no disponibles)."
        ),
        "limitacion_survivorship_bias": SURVIVORSHIP_BIAS_NOTE,
        "limitacion_analisis_dependencia_de_senales": (
            "No se calculó una matriz de correlación completa entre todas las señales de indicadores "
            "Categoría A para medir independencia estadística entre ellas; esto queda pendiente para una "
            "fase posterior y se declara explícitamente como NO completado en esta corrida."
        ),
    })

    if incomplete_run:
        logger.warning("EJECUCIÓN INCOMPLETA: límite de tiempo alcanzado.")
    logger.info(f"Resultados S2.1 (fase {cfg.phase}) escritos en: {results_dir}")
    return 0 if not incomplete_run else 2


def _aggregate_by_symbol(ind_id, name, tf, horizon, trades) -> list[dict]:
    by_symbol: dict[str, list] = {}
    for t in trades:
        by_symbol.setdefault(t.symbol, []).append(t)
    rows = []
    for symbol, trs in by_symbol.items():
        pnl_usdt = [t.pnl_usdt for t in trs]
        wins = [p for p in pnl_usdt if p > 0]
        rows.append({
            "catalog_id": ind_id, "name": name, "timeframe": tf, "horizon_hours": horizon,
            "symbol": symbol, "operaciones": len(trs),
            "win_rate_pct": round(100 * len(wins) / len(trs), 2) if trs else None,
            "pnl_total_usdt": round(sum(pnl_usdt), 4) if pnl_usdt else None,
        })
    return rows


def _aggregate_by_regime(ind_id, name, tf, horizon, trades, regime_by_day) -> list[dict]:
    if not regime_by_day:
        return []
    by_regime: dict[str, list] = {}
    for t in trades:
        day = pd.Timestamp(t.entry_time).floor("D")
        regime = regime_by_day.get(day, "DESCONOCIDO")
        by_regime.setdefault(regime, []).append(t.pnl_usdt)
    rows = []
    for regime, pnl in by_regime.items():
        wins = [p for p in pnl if p > 0]
        rows.append({
            "catalog_id": ind_id, "name": name, "timeframe": tf, "horizon_hours": horizon,
            "regimen_btc": regime, "operaciones": len(pnl),
            "win_rate_pct": round(100 * len(wins) / len(pnl), 2) if pnl else None,
            "pnl_total_usdt": round(sum(pnl), 4) if pnl else None,
        })
    return rows


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:  # noqa: BLE001
        traceback.print_exc()
        sys.exit(1)
