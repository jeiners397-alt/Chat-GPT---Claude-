"""
results_writer.py (S2.1) — Genera los 17 archivos obligatorios de
RESULTADOS_SPOT_EDGE_S21/ (sección 15 de la orden), pensados para que un
auditor externo (ChatGPT) pueda reconstruir independientemente los
resultados SIN volver a descargar datos de Binance:

 1. INDICATOR_METRICS_S21.csv        — métricas completas por experimento
 2. INDICATOR_RANKING_S21.csv        — ranking ordenado por rentabilidad neta
 3. INDICATOR_BY_SYMBOL_S21.csv      — desagregado por símbolo
 4. INDICATOR_BY_REGIME_S21.csv      — desagregado por régimen BTC (shift 1 día)
 5. TRADE_LEDGER.csv                 — operación por operación, contabilidad completa
 6. EQUITY_DAILY.csv                 — curva de equity mark-to-market diaria
 7. PORTFOLIO_ACCOUNTING.csv         — snapshot cash/posición/equity por operación
 8. SELECTION_METHOD_COMPARISON.csv  — sensibilidad A/B/C de selección simultánea
 9. UNIVERSE_EXCLUSIONS.csv          — exclusiones documentadas + nota de survivorship
10. TOP_GAINERS_CAUSAL.csv           — detección causal forward-only
11. EIGHT_CONFIGS_AUDIT.csv          — auditoría A-F de las 8 configuraciones "prometedoras"
12. INVERSE_RESEARCH_CANDIDATES.csv  — clasificación (NO ejecución) de candidatos a señal inversa
13. BENCHMARKS.csv                   — A: BTC buy&hold, B: 100 USDT, C: exposición pasiva universo
14. CHRONOLOGICAL_VALIDATION.csv     — Fase A vs Fase B + controles estadísticos
15. CAUSALITY_CHECKLIST.csv          — verificación de los 10 puntos de causalidad/temporalidad
16. DATA_COVERAGE_S21.csv            — cobertura de datos descargados
17. SUMMARY_S21.json                 — resumen ejecutivo + metadatos de la corrida
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone

import pandas as pd


def ensure_results_dir(path: str) -> str:
    os.makedirs(path, exist_ok=True)
    return path


def _write_csv(results_dir: str, filename: str, rows: list[dict]) -> None:
    df = pd.DataFrame(rows)
    df.to_csv(os.path.join(results_dir, filename), index=False)


def write_indicator_metrics(results_dir, rows): _write_csv(results_dir, "INDICATOR_METRICS_S21.csv", rows)


def write_indicator_ranking(results_dir, rows):
    df = pd.DataFrame(rows)
    if len(df) and "rentabilidad_neta_pct" in df.columns:
        df = df.sort_values("rentabilidad_neta_pct", ascending=False, na_position="last")
    df.to_csv(os.path.join(results_dir, "INDICATOR_RANKING_S21.csv"), index=False)


def write_by_symbol(results_dir, rows): _write_csv(results_dir, "INDICATOR_BY_SYMBOL_S21.csv", rows)


def write_by_regime(results_dir, rows): _write_csv(results_dir, "INDICATOR_BY_REGIME_S21.csv", rows)


def write_trade_ledger(results_dir, rows): _write_csv(results_dir, "TRADE_LEDGER.csv", rows)


def write_equity_daily(results_dir, rows): _write_csv(results_dir, "EQUITY_DAILY.csv", rows)


def write_portfolio_accounting(results_dir, rows): _write_csv(results_dir, "PORTFOLIO_ACCOUNTING.csv", rows)


def write_selection_method_comparison(results_dir, rows): _write_csv(results_dir, "SELECTION_METHOD_COMPARISON.csv", rows)


def write_universe_exclusions(results_dir, rows, survivorship_note: str):
    df = pd.DataFrame(rows)
    df.to_csv(os.path.join(results_dir, "UNIVERSE_EXCLUSIONS.csv"), index=False)
    with open(os.path.join(results_dir, "UNIVERSE_EXCLUSIONS_NOTA_SURVIVORSHIP.txt"), "w", encoding="utf-8") as f:
        f.write(survivorship_note)


def write_top_gainers_causal(results_dir, rows): _write_csv(results_dir, "TOP_GAINERS_CAUSAL.csv", rows)


def write_eight_configs_audit(results_dir, rows): _write_csv(results_dir, "EIGHT_CONFIGS_AUDIT.csv", rows)


def write_inverse_candidates(results_dir, rows): _write_csv(results_dir, "INVERSE_RESEARCH_CANDIDATES.csv", rows)


def write_benchmarks(results_dir, rows): _write_csv(results_dir, "BENCHMARKS.csv", rows)


def write_chronological_validation(results_dir, rows): _write_csv(results_dir, "CHRONOLOGICAL_VALIDATION.csv", rows)


def write_causality_checklist(results_dir, rows): _write_csv(results_dir, "CAUSALITY_CHECKLIST.csv", rows)


def write_data_coverage(results_dir, rows): _write_csv(results_dir, "DATA_COVERAGE_S21.csv", rows)


def write_summary(results_dir, summary: dict) -> None:
    summary["generado_en_utc"] = datetime.now(timezone.utc).isoformat()
    with open(os.path.join(results_dir, "SUMMARY_S21.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False, default=str)
