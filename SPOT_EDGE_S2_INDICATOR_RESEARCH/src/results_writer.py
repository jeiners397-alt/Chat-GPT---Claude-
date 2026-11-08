"""
results_writer.py — Genera los artefactos obligatorios (sección 8):
  INDICATOR_RANKING.csv, INDICATOR_METRICS.csv, INDICATOR_BY_SYMBOL.csv,
  INDICATOR_BY_REGIME.csv, TOP_GAINERS_DETECTION.csv, INVERSE_CANDIDATES.csv,
  UNTESTED_INDICATORS.csv, DATA_COVERAGE.csv, SUMMARY.json
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone

import pandas as pd

from src.indicators.registry import STATUS_IMPLEMENTED


def ensure_results_dir(path: str) -> str:
    os.makedirs(path, exist_ok=True)
    return path


def write_indicator_metrics(results_dir: str, rows: list[dict]) -> None:
    df = pd.DataFrame(rows)
    df.to_csv(os.path.join(results_dir, "INDICATOR_METRICS.csv"), index=False)


def write_indicator_ranking(results_dir: str, rows: list[dict]) -> None:
    df = pd.DataFrame(rows)
    if len(df) and "rentabilidad_neta_pct" in df.columns:
        df = df.sort_values("rentabilidad_neta_pct", ascending=False, na_position="last")
    df.to_csv(os.path.join(results_dir, "INDICATOR_RANKING.csv"), index=False)


def write_by_symbol(results_dir: str, rows: list[dict]) -> None:
    df = pd.DataFrame(rows)
    df.to_csv(os.path.join(results_dir, "INDICATOR_BY_SYMBOL.csv"), index=False)


def write_by_regime(results_dir: str, rows: list[dict]) -> None:
    df = pd.DataFrame(rows)
    df.to_csv(os.path.join(results_dir, "INDICATOR_BY_REGIME.csv"), index=False)


def write_top_gainers_detection(results_dir: str, rows: list[dict]) -> None:
    df = pd.DataFrame(rows)
    df.to_csv(os.path.join(results_dir, "TOP_GAINERS_DETECTION.csv"), index=False)


def write_inverse_candidates(results_dir: str, rows: list[dict]) -> None:
    df = pd.DataFrame(rows)
    df.to_csv(os.path.join(results_dir, "INVERSE_CANDIDATES.csv"), index=False)


def write_untested_indicators(results_dir: str, registry_defs) -> None:
    rows = []
    for d in registry_defs:
        if d.implementation_status != STATUS_IMPLEMENTED:
            rows.append({
                "catalog_id": d.catalog_id,
                "name": d.name,
                "status": d.implementation_status,
                "motivo": d.reason_if_not_implemented,
            })
    df = pd.DataFrame(rows)
    df.to_csv(os.path.join(results_dir, "UNTESTED_INDICATORS.csv"), index=False)


def write_data_coverage(results_dir: str, coverage_records: list[dict]) -> None:
    df = pd.DataFrame(coverage_records)
    df.to_csv(os.path.join(results_dir, "DATA_COVERAGE.csv"), index=False)


def write_summary(
    results_dir: str,
    registry_defs,
    classification_counts: dict,
    best_indicator: dict | None,
    worst_indicator: dict | None,
    best_net_return: dict | None,
    best_profit_factor: dict | None,
    best_top_gainer_detector: dict | None,
    run_metadata: dict,
) -> None:
    n_registered = len(registry_defs)
    n_implemented = sum(1 for d in registry_defs if d.implementation_status == STATUS_IMPLEMENTED)

    summary = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "indicadores_registrados": n_registered,
        "indicadores_evaluados": n_implemented,
        "indicadores_prometedores_A": classification_counts.get("A_PROMETEDOR", 0),
        "indicadores_perdidas_moderadas_B": classification_counts.get("B_PERDIDAS_MODERADAS", 0),
        "indicadores_muy_negativos_C": classification_counts.get("C_MUY_NEGATIVO", 0),
        "indicadores_no_concluyentes_D": classification_counts.get("D_NO_CONCLUYENTE", 0),
        "indicadores_no_evaluables_E": n_registered - n_implemented,
        "mejor_indicador_clasificado": best_indicator,
        "peor_indicador_clasificado": worst_indicator,
        "mayor_rentabilidad_neta_observada": best_net_return,
        "mejor_profit_factor_con_muestra_suficiente": best_profit_factor,
        "mejor_detector_de_top_gainers": best_top_gainer_detector,
        "run_metadata": run_metadata,
        "advertencia": (
            f"Se evaluaron realmente {n_implemented} de {n_registered} indicadores registrados. "
            "Los restantes están documentados en UNTESTED_INDICATORS.csv con su motivo; no se "
            "afirma haber analizado los 200 indicadores."
        ),
    }
    with open(os.path.join(results_dir, "SUMMARY.json"), "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2, ensure_ascii=False, default=str)

    print("\n" + "=" * 70)
    print("RESUMEN FINAL — SPOT EDGE S2")
    print("=" * 70)
    for k, v in summary.items():
        if k in ("run_metadata",):
            continue
        print(f"  {k}: {v}")
    print("=" * 70)
