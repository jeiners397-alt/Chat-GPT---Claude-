#!/usr/bin/env python3
"""
compare_phases.py — Compara los resultados de Fase A (período original S2.1,
usado para seleccionar/observar indicadores) contra Fase B (período histórico
anterior, nunca usado para esa selección), y sobrescribe
CHRONOLOGICAL_VALIDATION.csv en el directorio de resultados de la Fase A con
la comparación real (sección 11 de la orden).

Uso:
    python scripts/compare_phases.py \
        --phase-a-dir RESULTADOS_SPOT_EDGE_S21 \
        --phase-b-dir RESULTADOS_SPOT_EDGE_S21_PHASE_B
"""
from __future__ import annotations

import argparse
import os

import pandas as pd


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--phase-a-dir", default="RESULTADOS_SPOT_EDGE_S21")
    p.add_argument("--phase-b-dir", default="RESULTADOS_SPOT_EDGE_S21_PHASE_B")
    args = p.parse_args()

    a_path = os.path.join(args.phase_a_dir, "INDICATOR_METRICS_S21.csv")
    b_path = os.path.join(args.phase_b_dir, "INDICATOR_METRICS_S21.csv")
    if not (os.path.exists(a_path) and os.path.exists(b_path)):
        print(f"No se encontraron ambos archivos de métricas ({a_path}, {b_path}); nada que comparar.")
        return 0

    df_a = pd.read_csv(a_path)
    df_b = pd.read_csv(b_path)
    key_cols = ["indicator_id", "timeframe", "horizon_hours"]
    merged = df_a.merge(df_b, on=key_cols, suffixes=("_fase_a", "_fase_b"), how="outer")

    rows = []
    for _, r in merged.iterrows():
        ret_a = r.get("rentabilidad_neta_pct_fase_a")
        ret_b = r.get("rentabilidad_neta_pct_fase_b")
        cat_a = r.get("categoria_fase_a")
        cat_b = r.get("categoria_fase_b")
        consistent_sign = (
            pd.notna(ret_a) and pd.notna(ret_b) and ((ret_a > 0) == (ret_b > 0))
        )
        rows.append({
            "indicator_id": r.get("indicator_id"), "indicator_name": r.get("indicator_name_fase_a") or r.get("indicator_name_fase_b"),
            "timeframe": r.get("timeframe"), "horizon_hours": r.get("horizon_hours"),
            "categoria_fase_a": cat_a, "categoria_fase_b": cat_b,
            "rentabilidad_neta_pct_fase_a": ret_a, "rentabilidad_neta_pct_fase_b": ret_b,
            "mismo_signo_ambas_fases": consistent_sign,
            "categoria_consistente": cat_a == cat_b,
        })

    out = pd.DataFrame(rows)
    out_path = os.path.join(args.phase_a_dir, "CHRONOLOGICAL_VALIDATION.csv")
    out.to_csv(out_path, index=False)

    n_both_positive_consistent = int(out["mismo_signo_ambas_fases"].sum())
    n_total = len(out)
    print(f"CHRONOLOGICAL_VALIDATION.csv escrito en {out_path}: {n_both_positive_consistent}/{n_total} configuraciones con signo consistente entre Fase A y Fase B.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
