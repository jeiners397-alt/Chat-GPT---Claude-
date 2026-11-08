#!/usr/bin/env python3
"""
spot_indicator_research.py — SPOT EDGE S2: investigador cuantitativo de
indicadores técnicos para Binance Spot (LONG-only).

Ejecuta el pipeline completo: universo -> datos en memoria (sin descargas a
disco) -> señales -> backtest sin look-ahead -> estadísticas -> clasificación
-> detección de Top Gainers -> exportación de resultados.

Uso:
    python spot_indicator_research.py --lookback-days 60 --max-symbols 15
    python spot_indicator_research.py --lookback-days 180   (ampliación opcional)
"""

from __future__ import annotations

import argparse
import gc
import sys
import time
import traceback
from datetime import datetime, timedelta, timezone

import pandas as pd

import config
from src.backtest import build_candidates_for_symbol, execute_experiment, horizon_to_bars
from src.binance_client import BinanceClient
from src.classification import classify_indicator_experiment
from src.indicators.registry import (
    STATUS_IMPLEMENTED,
    build_full_registry,
    get_signal_function,
)
from src.logging_utils import get_logger
from src.results_writer import (
    ensure_results_dir,
    write_by_regime,
    write_by_symbol,
    write_data_coverage,
    write_indicator_metrics,
    write_indicator_ranking,
    write_inverse_candidates,
    write_summary,
    write_top_gainers_detection,
    write_untested_indicators,
)
from src.stats import compute_benchmark_stats, compute_experiment_stats
from src.topgainers import (
    compute_daily_top_gainers,
    evaluate_signal_vs_top_gainers,
    summarize_detection_quality,
)
from src.universe import build_universe

logger = get_logger("spot_indicator_research")


def parse_args() -> config.RunConfig:
    p = argparse.ArgumentParser(description="SPOT EDGE S2 — Investigador de indicadores Binance Spot")
    p.add_argument("--lookback-days", type=int, default=config.DEFAULT_LOOKBACK_DAYS)
    p.add_argument("--max-symbols", type=int, default=0, help="0 = sin límite (todo el universo)")
    p.add_argument("--timeframes", type=str, default=",".join(config.TIMEFRAMES))
    p.add_argument("--results-dir", type=str, default=config.RESULTS_DIR_NAME)
    p.add_argument("--symbols", type=str, default="", help="Lista separada por comas para forzar el universo (pruebas)")
    p.add_argument("--no-commission-sensitivity", action="store_true")
    p.add_argument("--max-runtime-minutes", type=float, default=0.0,
                   help="0 = sin límite. Si se excede, se guardan resultados parciales y se marca incompleto.")
    args = p.parse_args()

    return config.RunConfig(
        lookback_days=args.lookback_days,
        timeframes=tuple(t.strip() for t in args.timeframes.split(",") if t.strip()),
        max_symbols=args.max_symbols,
        results_dir=args.results_dir,
        symbols_override=tuple(s.strip().upper() for s in args.symbols.split(",") if s.strip()),
        run_commission_sensitivity=not args.no_commission_sensitivity,
    ), args.max_runtime_minutes


def main() -> int:
    run_cfg, max_runtime_minutes = parse_args()
    run_started_at = time.time()
    deadline = run_started_at + max_runtime_minutes * 60 if max_runtime_minutes > 0 else None
    incomplete_run = False

    logger.info(f"Iniciando SPOT EDGE S2 | lookback={run_cfg.lookback_days}d | timeframes={run_cfg.timeframes}")

    results_dir = ensure_results_dir(run_cfg.results_dir)
    client = BinanceClient()

    # 1. Universo -------------------------------------------------------------
    symbols, exclusions = build_universe(client, run_cfg.max_symbols, run_cfg.symbols_override)
    if "BTCUSDT" not in symbols:
        symbols_for_fetch = ["BTCUSDT"] + symbols
    else:
        symbols_for_fetch = symbols
    logger.info(f"Símbolos a procesar: {len(symbols_for_fetch)} (incluye BTCUSDT como benchmark/referencia)")

    # 2. Registro de indicadores ----------------------------------------------
    registry_defs = build_full_registry()
    implemented_defs = [d for d in registry_defs if d.implementation_status == STATUS_IMPLEMENTED]
    logger.info(f"Indicadores registrados: {len(registry_defs)} | Implementados y evaluados: {len(implemented_defs)}")

    # 3. Rango temporal ---------------------------------------------------------
    now_utc = datetime.now(timezone.utc)
    main_end_dt = now_utc
    main_start_dt = now_utc - timedelta(days=run_cfg.lookback_days)
    exploration_end_dt = main_start_dt + (main_end_dt - main_start_dt) * config.EXPLORATION_FRACTION

    # Candidatos acumulados por experimento: (indicator_id, timeframe, horizon) -> list[TradeCandidate]
    candidates_by_experiment: dict[tuple, list] = {}
    total_signals_by_experiment: dict[tuple, int] = {}
    candidates_by_experiment_exploration: dict[tuple, list] = {}
    candidates_by_experiment_confirmation: dict[tuple, list] = {}

    coverage_records: list[dict] = []
    daily_closes_by_symbol: dict[str, pd.Series] = {}
    daily_df_by_symbol: dict[str, pd.DataFrame] = {}
    btc_close_by_timeframe: dict[str, pd.Series] = {}

    # 4. Descarga y procesamiento por símbolo (en memoria, liberado al final) ---
    for sym_idx, symbol in enumerate(symbols_for_fetch, start=1):
        if deadline and time.time() > deadline:
            incomplete_run = True
            logger.warning("Límite de tiempo alcanzado. Deteniendo descarga de nuevos símbolos.")
            break

        logger.info(f"[{sym_idx}/{len(symbols_for_fetch)}] Procesando {symbol}")
        per_timeframe_df: dict[str, pd.DataFrame] = {}

        for tf in run_cfg.timeframes:
            warmup_days = config.WARMUP_DAYS_BY_TIMEFRAME[tf]
            fetch_start = main_start_dt - timedelta(days=warmup_days)
            start_ms = int(fetch_start.timestamp() * 1000)
            end_ms = int(main_end_dt.timestamp() * 1000)
            try:
                df, record = client.get_klines_dataframe(symbol, tf, start_ms, end_ms)
            except Exception as exc:  # noqa: BLE001
                logger.error(f"Error descargando {symbol} {tf}: {exc}")
                coverage_records.append({
                    "symbol": symbol, "timeframe": tf, "candles_received": 0,
                    "gaps_detected": 0, "error": str(exc),
                })
                continue

            coverage_records.append(record.to_dict())
            if df.empty or len(df) < 30:
                continue
            per_timeframe_df[tf] = df

            if tf == "1d":
                daily_closes_by_symbol[symbol] = df.set_index("open_time")["close"]
                daily_df_by_symbol[symbol] = df
            if symbol == "BTCUSDT":
                btc_close_by_timeframe[tf] = df.set_index("open_time")["close"]

        # -- señales por indicador implementado -------------------------------
        if symbol != "BTCUSDT" or symbol in symbols:  # BTCUSDT también se evalúa si pasó el filtro de universo
            for tf, df in per_timeframe_df.items():
                mask_main_range = df["open_time"] >= pd.Timestamp(main_start_dt, tz="UTC")
                btc_close_ref = btc_close_by_timeframe.get(tf)

                for ind_def in implemented_defs:
                    if tf not in ind_def.timeframes:
                        continue
                    try:
                        sig_fn = get_signal_function(ind_def.signal_function_name)
                        sig_full = sig_fn(df, btc_close=btc_close_ref)
                    except Exception as exc:  # noqa: BLE001
                        logger.error(f"Error calculando señal {ind_def.name} en {symbol}/{tf}: {exc}")
                        continue

                    sig_masked = sig_full.fillna(False) & mask_main_range
                    sig_exploration = sig_masked & (df["open_time"] < pd.Timestamp(exploration_end_dt, tz="UTC"))
                    sig_confirmation = sig_masked & (df["open_time"] >= pd.Timestamp(exploration_end_dt, tz="UTC"))

                    for horizon in run_cfg.horizons_hours:
                        bars = horizon_to_bars(horizon, tf)
                        if bars < 1:
                            continue
                        key = (ind_def.catalog_id, tf, horizon)

                        cands, n_sig = build_candidates_for_symbol(symbol, df, sig_masked, tf, horizon)
                        candidates_by_experiment.setdefault(key, []).extend(cands)
                        total_signals_by_experiment[key] = total_signals_by_experiment.get(key, 0) + n_sig

                        cands_expl, _ = build_candidates_for_symbol(symbol, df, sig_exploration, tf, horizon)
                        candidates_by_experiment_exploration.setdefault(key, []).extend(cands_expl)

                        cands_conf, _ = build_candidates_for_symbol(symbol, df, sig_confirmation, tf, horizon)
                        candidates_by_experiment_confirmation.setdefault(key, []).extend(cands_conf)

        # liberar memoria del símbolo procesado
        del per_timeframe_df
        gc.collect()

    # 5. Ejecución de cada experimento (backtest global cronológico) -----------
    metrics_rows: list[dict] = []
    ranking_rows: list[dict] = []
    by_symbol_rows: list[dict] = []
    by_regime_rows: list[dict] = []
    inverse_candidates_rows: list[dict] = []
    classification_counts: dict[str, int] = {}

    regime_by_day = _build_btc_regime_series(daily_df_by_symbol.get("BTCUSDT"))

    ind_def_by_id = {d.catalog_id: d for d in implemented_defs}

    for key, cands in candidates_by_experiment.items():
        ind_id, tf, horizon = key
        ind_def = ind_def_by_id[ind_id]
        total_signals = total_signals_by_experiment.get(key, 0)

        full_result = execute_experiment(
            ind_id, ind_def.name, tf, horizon, cands, total_signals,
            run_cfg.initial_capital_usdt, run_cfg.commission_pct_per_side, run_cfg.slippage_pct_per_side,
        )
        full_stats = compute_experiment_stats(full_result)

        expl_cands = candidates_by_experiment_exploration.get(key, [])
        conf_cands = candidates_by_experiment_confirmation.get(key, [])
        expl_result = execute_experiment(ind_id, ind_def.name, tf, horizon, expl_cands, len(expl_cands),
                                          run_cfg.initial_capital_usdt, run_cfg.commission_pct_per_side, run_cfg.slippage_pct_per_side)
        conf_result = execute_experiment(ind_id, ind_def.name, tf, horizon, conf_cands, len(conf_cands),
                                          run_cfg.initial_capital_usdt, run_cfg.commission_pct_per_side, run_cfg.slippage_pct_per_side)
        expl_stats = compute_experiment_stats(expl_result)
        conf_stats = compute_experiment_stats(conf_result)

        category, motivo = classify_indicator_experiment(full_stats, expl_stats, conf_stats)
        classification_counts[category] = classification_counts.get(category, 0) + 1

        row = dict(full_stats)
        row["categoria"] = category
        row["motivo_categoria"] = motivo
        row["rentabilidad_neta_pct_exploracion"] = expl_stats.get("rentabilidad_neta_pct")
        row["rentabilidad_neta_pct_comprobacion"] = conf_stats.get("rentabilidad_neta_pct")

        if run_cfg.run_commission_sensitivity and full_result.trades:
            sens_result = execute_experiment(
                ind_id, ind_def.name, tf, horizon, cands, total_signals, run_cfg.initial_capital_usdt,
                run_cfg.commission_pct_per_side * config.COMMISSION_SENSITIVITY_MULTIPLIER,
                run_cfg.slippage_pct_per_side * config.COMMISSION_SENSITIVITY_MULTIPLIER,
            )
            sens_stats = compute_experiment_stats(sens_result)
            row["rentabilidad_neta_pct_comision_x2"] = sens_stats.get("rentabilidad_neta_pct")

        metrics_rows.append(row)
        ranking_rows.append(row)

        if category == "C_MUY_NEGATIVO":
            inverse_candidates_rows.append({
                "catalog_id": ind_id, "name": ind_def.name, "timeframe": tf, "horizon_hours": horizon,
                "rentabilidad_neta_pct_long": full_stats.get("rentabilidad_neta_pct"),
                "profit_factor_long": full_stats.get("profit_factor"),
                "operaciones_ejecutadas": full_stats.get("operaciones_ejecutadas"),
                "motivo": motivo,
                "nota": "Candidato a investigar señal inversa en fase futura. No contiene operaciones inversas simuladas.",
            })

        # -- por símbolo -----------------------------------------------------
        by_symbol_rows.extend(_aggregate_by_symbol(ind_id, ind_def.name, tf, horizon, full_result.trades))

        # -- por régimen -------------------------------------------------------
        by_regime_rows.extend(_aggregate_by_regime(ind_id, ind_def.name, tf, horizon, full_result.trades, regime_by_day))

    # 6. Top Gainers ------------------------------------------------------------
    top_gainers_rows: list[dict] = []
    if daily_closes_by_symbol:
        top_gainers_by_day = compute_daily_top_gainers(daily_closes_by_symbol)
        for key, cands in candidates_by_experiment.items():
            ind_id, tf, horizon = key
            if tf != "1d" and tf not in ("4h", "1h"):
                pass  # se evalúa para cualquier timeframe; el 1d de referencia es fijo
            ind_def = ind_def_by_id[ind_id]
            evals = []
            for cand in cands:
                df_1d = daily_df_by_symbol.get(cand.symbol)
                if df_1d is None:
                    continue
                evals.append(
                    evaluate_signal_vs_top_gainers(
                        ind_id, ind_def.name, tf, cand.symbol, cand.signal_time, df_1d, top_gainers_by_day
                    )
                )
            if evals:
                summary = summarize_detection_quality(evals)
                summary.update({"catalog_id": ind_id, "name": ind_def.name, "timeframe": tf, "horizon_hours": horizon})
                top_gainers_rows.append(summary)

    # 7. Escritura de resultados -------------------------------------------------
    write_indicator_metrics(results_dir, metrics_rows)
    write_indicator_ranking(results_dir, ranking_rows)
    write_by_symbol(results_dir, by_symbol_rows)
    write_by_regime(results_dir, by_regime_rows)
    write_top_gainers_detection(results_dir, top_gainers_rows)
    write_inverse_candidates(results_dir, inverse_candidates_rows)
    write_untested_indicators(results_dir, registry_defs)
    write_data_coverage(results_dir, coverage_records)

    best_net_return = _best_row(ranking_rows, "rentabilidad_neta_pct", maximize=True)
    worst_indicator = _best_row(ranking_rows, "rentabilidad_neta_pct", maximize=False)
    best_profit_factor = _best_row(
        [r for r in ranking_rows if (r.get("operaciones_ejecutadas") or 0) >= config.MIN_TRADES_FOR_CONCLUSIVE],
        "profit_factor", maximize=True,
    )
    best_top_gainer_detector = _best_row(top_gainers_rows, "precision_pct", maximize=True)

    write_summary(
        results_dir, registry_defs, classification_counts,
        best_indicator=best_net_return, worst_indicator=worst_indicator,
        best_net_return=best_net_return, best_profit_factor=best_profit_factor,
        best_top_gainer_detector=best_top_gainer_detector,
        run_metadata={
            "lookback_days": run_cfg.lookback_days,
            "timeframes": run_cfg.timeframes,
            "symbols_evaluados": len(symbols_for_fetch),
            "ejecucion_incompleta": incomplete_run,
            "duracion_segundos": round(time.time() - run_started_at, 1),
        },
    )

    if incomplete_run:
        logger.warning("EJECUCIÓN INCOMPLETA: se alcanzó el límite de tiempo. Resultados parciales guardados.")
    logger.info(f"Resultados escritos en: {results_dir}")
    return 0 if not incomplete_run else 2


def _aggregate_by_symbol(ind_id, name, tf, horizon, trades) -> list[dict]:
    by_symbol: dict[str, list] = {}
    for t in trades:
        by_symbol.setdefault(t.symbol, []).append(t)
    rows = []
    for symbol, trs in by_symbol.items():
        pnl = [t.pnl_pct_net for t in trs]
        wins = [p for p in pnl if p > 0]
        rows.append({
            "catalog_id": ind_id, "name": name, "timeframe": tf, "horizon_hours": horizon,
            "symbol": symbol, "operaciones": len(trs),
            "win_rate_pct": round(100 * len(wins) / len(trs), 2) if trs else None,
            "pnl_promedio_pct": round(100 * sum(pnl) / len(pnl), 4) if pnl else None,
            "pnl_acumulado_pct": round(100 * (pd.Series([1 + p for p in pnl]).prod() - 1), 4) if pnl else None,
        })
    return rows


def _build_btc_regime_series(btc_daily_df: pd.DataFrame | None) -> dict[pd.Timestamp, str]:
    if btc_daily_df is None or len(btc_daily_df) < 50:
        return {}
    close = btc_daily_df.set_index("open_time")["close"]
    ema20 = close.ewm(span=20, adjust=False, min_periods=20).mean()
    ema50 = close.ewm(span=50, adjust=False, min_periods=50).mean()
    trend = (ema20 > ema50).map({True: "ALCISTA", False: "BAJISTA"})
    return trend.to_dict()


def _aggregate_by_regime(ind_id, name, tf, horizon, trades, regime_by_day) -> list[dict]:
    if not regime_by_day:
        return []
    by_regime: dict[str, list] = {}
    for t in trades:
        day = pd.Timestamp(t.entry_time).floor("D")
        regime = regime_by_day.get(day, "DESCONOCIDO")
        by_regime.setdefault(regime, []).append(t.pnl_pct_net)
    rows = []
    for regime, pnl in by_regime.items():
        wins = [p for p in pnl if p > 0]
        rows.append({
            "catalog_id": ind_id, "name": name, "timeframe": tf, "horizon_hours": horizon,
            "regimen_btc": regime, "operaciones": len(pnl),
            "win_rate_pct": round(100 * len(wins) / len(pnl), 2) if pnl else None,
            "pnl_promedio_pct": round(100 * sum(pnl) / len(pnl), 4) if pnl else None,
        })
    return rows


def _best_row(rows: list[dict], field: str, maximize: bool) -> dict | None:
    valid = [r for r in rows if isinstance(r.get(field), (int, float))]
    if not valid:
        return None
    best = max(valid, key=lambda r: r[field]) if maximize else min(valid, key=lambda r: r[field])
    return {k: best.get(k) for k in ("catalog_id", "indicator_id", "name", "indicator_name", "timeframe", "horizon_hours", field) if k in best}


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:  # noqa: BLE001
        traceback.print_exc()
        sys.exit(1)
