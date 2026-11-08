"""
classification.py — Clasificación automática A-E (sección 6 del encargo).

Los umbrales están CONGELADOS en config.py antes de ejecutar el análisis y
no se ajustan después de observar resultados (sección 6, última línea).
"""

from __future__ import annotations

from config import (
    CATEGORY_A_THRESHOLDS,
    CATEGORY_C_THRESHOLDS,
    MIN_SYMBOLS_FOR_CONCLUSIVE,
    MIN_TRADES_FOR_CONCLUSIVE,
)

CATEGORY_A = "A_PROMETEDOR"
CATEGORY_B = "B_PERDIDAS_MODERADAS"
CATEGORY_C = "C_MUY_NEGATIVO"
CATEGORY_D = "D_NO_CONCLUYENTE"
CATEGORY_E = "E_NO_EVALUABLE"


def classify_indicator_experiment(
    combined_stats: dict, exploration_stats: dict | None, confirmation_stats: dict | None
) -> tuple[str, str]:
    """Clasifica un experimento (indicador×timeframe×horizonte) ya agregado
    (estadísticas sobre el período completo), usando además las estadísticas
    por sub-período (exploración/comprobación) para exigir consistencia.

    Devuelve (categoría, motivo_textual).
    """
    n_trades = combined_stats.get("operaciones_ejecutadas", 0) or 0
    n_symbols = combined_stats.get("numero_activos_con_senal", 0) or 0

    if n_trades < MIN_TRADES_FOR_CONCLUSIVE or n_symbols < MIN_SYMBOLS_FOR_CONCLUSIVE:
        return CATEGORY_D, (
            f"Muestra insuficiente: {n_trades} operaciones (mínimo {MIN_TRADES_FOR_CONCLUSIVE}) "
            f"en {n_symbols} activos (mínimo {MIN_SYMBOLS_FOR_CONCLUSIVE})."
        )

    expectancy = combined_stats.get("expectativa_matematica_pct")
    profit_factor = combined_stats.get("profit_factor")
    net_return = combined_stats.get("rentabilidad_neta_pct")

    if expectancy is None or net_return is None:
        return CATEGORY_D, "Estadísticas clave indefinidas (N/A) con la muestra disponible."

    pf_value = profit_factor if isinstance(profit_factor, (int, float)) else (
        float("inf") if profit_factor == "inf" else None
    )

    is_a_candidate = (
        expectancy > CATEGORY_A_THRESHOLDS["expectancy_gt"]
        and pf_value is not None and pf_value > CATEGORY_A_THRESHOLDS["profit_factor_gt"]
        and net_return > CATEGORY_A_THRESHOLDS["net_return_gt"]
    )

    if is_a_candidate and CATEGORY_A_THRESHOLDS["require_consistency"]:
        consistent = _check_consistency(exploration_stats, confirmation_stats)
        if not consistent:
            return CATEGORY_D, (
                "Resultado positivo en el período completo, pero inconsistente entre el tramo de "
                "exploración y el de comprobación (posible sobreajuste). Clasificado como no "
                "concluyente por la regla de consistencia congelada."
            )
        return CATEGORY_A, (
            f"Expectativa={expectancy:.4f}%, Profit Factor={pf_value:.2f}, "
            f"Rentabilidad neta={net_return:.2f}%, consistente en exploración y comprobación."
        )

    if (
        net_return < CATEGORY_C_THRESHOLDS["net_return_lt"] * 100
        and (pf_value is not None and pf_value < CATEGORY_C_THRESHOLDS["profit_factor_lt"])
    ):
        return CATEGORY_C, (
            f"Rentabilidad neta muy negativa ({net_return:.2f}%) y Profit Factor bajo "
            f"({pf_value:.2f}). Candidato a investigación de señal inversa en fase futura "
            f"(sin ejecutar esa inversión en esta fase)."
        )

    return CATEGORY_B, (
        f"Resultado cercano al equilibrio o levemente negativo "
        f"(Rentabilidad neta={net_return:.2f}%, Expectativa={expectancy:.4f}%)."
    )


def _check_consistency(exploration_stats: dict | None, confirmation_stats: dict | None) -> bool:
    if not exploration_stats or not confirmation_stats:
        return False
    exp_ret = exploration_stats.get("rentabilidad_neta_pct")
    conf_ret = confirmation_stats.get("rentabilidad_neta_pct")
    if exp_ret is None or conf_ret is None:
        return False
    return exp_ret > 0 and conf_ret > 0
