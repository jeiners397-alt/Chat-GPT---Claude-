"""
classification.py (S2.1) — Clasificación A-E (igual lógica congelada que S2,
ahora alimentada con profit_factor_usdt en vez de profit_factor porcentual)
MÁS una dimensión de ROBUSTEZ independiente (sección 14 de la orden):
ALTA / MEDIA / BAJA / INSUFICIENTE.

IMPORTANTE (instrucción explícita de la orden): Categoría A nunca se
presenta como "rentabilidad validada". Es solo una etiqueta de clasificación
estadística bajo las reglas congeladas; su robustez se reporta por separado.
"""

from __future__ import annotations

from config_s21 import (
    CATEGORY_A_THRESHOLDS,
    CATEGORY_C_THRESHOLDS,
    COST_RESISTANT_MIN_NET_RETURN_PCT_AT_3X,
    EXTREME_TRADE_MAX_SHARE_OF_GAIN,
    MIN_SYMBOLS_FOR_CONCLUSIVE,
    MIN_SYMBOLS_FOR_CROSS_ASSET_STABILITY,
    MIN_TRADES_FOR_CONCLUSIVE,
    ROBUSTNESS_HIGH,
    ROBUSTNESS_INSUFFICIENT,
    ROBUSTNESS_LOW,
    ROBUSTNESS_MEDIUM,
)

CATEGORY_A = "A_PROMETEDOR"
CATEGORY_B = "B_PERDIDAS_MODERADAS"
CATEGORY_C = "C_MUY_NEGATIVO"
CATEGORY_D = "D_NO_CONCLUYENTE"
CATEGORY_E = "E_NO_EVALUABLE"


def classify_indicator_experiment(combined_stats: dict, exploration_stats: dict | None, confirmation_stats: dict | None) -> tuple[str, str]:
    n_trades = combined_stats.get("operaciones_ejecutadas", 0) or 0
    n_symbols = combined_stats.get("numero_activos_con_senal", 0) or 0

    if n_trades < MIN_TRADES_FOR_CONCLUSIVE or n_symbols < MIN_SYMBOLS_FOR_CONCLUSIVE:
        return CATEGORY_D, (
            f"Muestra insuficiente: {n_trades} operaciones (mínimo {MIN_TRADES_FOR_CONCLUSIVE}) "
            f"en {n_symbols} activos (mínimo {MIN_SYMBOLS_FOR_CONCLUSIVE})."
        )

    expectancy = combined_stats.get("expectativa_matematica_pct")
    net_return = combined_stats.get("rentabilidad_neta_pct")
    pf_value = combined_stats.get("profit_factor_usdt")

    if expectancy is None or net_return is None:
        return CATEGORY_D, "Estadísticas clave indefinidas (N/A) con la muestra disponible."

    is_a_candidate = (
        expectancy > CATEGORY_A_THRESHOLDS["expectancy_gt"]
        and pf_value is not None and pf_value > CATEGORY_A_THRESHOLDS["profit_factor_gt"]
        and net_return > CATEGORY_A_THRESHOLDS["net_return_gt"]
    )

    if is_a_candidate and CATEGORY_A_THRESHOLDS["require_consistency"]:
        consistent = _check_consistency(exploration_stats, confirmation_stats)
        if not consistent:
            return CATEGORY_D, (
                "Resultado positivo en el período completo (PF monetario), pero inconsistente "
                "entre exploración y comprobación (posible sobreajuste)."
            )
        return CATEGORY_A, (
            f"Expectativa={expectancy:.4f}%, PF monetario={pf_value:.2f}, "
            f"Rentabilidad neta={net_return:.2f}%, consistente en exploración y comprobación. "
            f"ESTA CATEGORÍA NO IMPLICA RENTABILIDAD VALIDADA — ver dimensión de robustez."
        )

    if (
        net_return < CATEGORY_C_THRESHOLDS["net_return_lt"] * 100
        and (pf_value is not None and pf_value < CATEGORY_C_THRESHOLDS["profit_factor_lt"])
    ):
        return CATEGORY_C, (
            f"Rentabilidad neta muy negativa ({net_return:.2f}%) y PF monetario bajo ({pf_value:.2f})."
        )

    return CATEGORY_B, (
        f"Resultado cercano al equilibrio o levemente negativo "
        f"(Rentabilidad neta={net_return:.2f}%, Expectativa={expectancy:.4f}%)."
    )


def _check_consistency(exploration_stats, confirmation_stats) -> bool:
    if not exploration_stats or not confirmation_stats:
        return False
    exp_ret = exploration_stats.get("rentabilidad_neta_pct")
    conf_ret = confirmation_stats.get("rentabilidad_neta_pct")
    if exp_ret is None or conf_ret is None:
        return False
    return exp_ret > 0 and conf_ret > 0


def classify_robustness(
    combined_stats: dict,
    stats_at_3x_cost: dict | None,
    extreme_trade_removed_stats: dict | None,
    n_symbols_with_signals: int,
    largest_single_trade_gain_usdt: float | None,
) -> tuple[str, str]:
    """Clasifica robustez según: dependencia de operaciones extremas,
    sensibilidad a costos (x3), estabilidad entre activos, calidad de datos.
    """
    n_trades = combined_stats.get("operaciones_ejecutadas", 0) or 0
    net_return = combined_stats.get("rentabilidad_neta_pct")
    gross_profit = combined_stats.get("ganancia_bruta_usdt") or 0.0

    if n_trades < MIN_TRADES_FOR_CONCLUSIVE or net_return is None:
        return ROBUSTNESS_INSUFFICIENT, "Muestra insuficiente para evaluar robustez."

    reasons = []
    penalties = 0

    # (a) dependencia de operación extrema
    extreme_share = None
    if largest_single_trade_gain_usdt is not None and gross_profit > 0:
        extreme_share = largest_single_trade_gain_usdt / gross_profit
        if extreme_share > EXTREME_TRADE_MAX_SHARE_OF_GAIN:
            penalties += 1
            reasons.append(
                f"Una sola operación aporta {extreme_share*100:.1f}% de la ganancia bruta "
                f"(umbral {EXTREME_TRADE_MAX_SHARE_OF_GAIN*100:.0f}%)."
            )
    if extreme_trade_removed_stats is not None:
        ret_wo_extreme = extreme_trade_removed_stats.get("rentabilidad_neta_pct")
        if ret_wo_extreme is not None and net_return is not None and net_return > 0 and ret_wo_extreme <= 0:
            penalties += 1
            reasons.append("El resultado se vuelve negativo al re-simular excluyendo la operación extraordinaria.")

    # (b) resistencia a costos x3
    if stats_at_3x_cost is not None:
        ret_3x = stats_at_3x_cost.get("rentabilidad_neta_pct")
        if ret_3x is not None and ret_3x < COST_RESISTANT_MIN_NET_RETURN_PCT_AT_3X:
            penalties += 1
            reasons.append(f"Rentabilidad neta se vuelve negativa ({ret_3x:.2f}%) con comisión/slippage x3.")

    # (c) estabilidad entre activos
    if n_symbols_with_signals < MIN_SYMBOLS_FOR_CROSS_ASSET_STABILITY:
        penalties += 1
        reasons.append(
            f"Resultado concentrado en muy pocos activos ({n_symbols_with_signals} < "
            f"{MIN_SYMBOLS_FOR_CROSS_ASSET_STABILITY})."
        )

    if penalties == 0:
        return ROBUSTNESS_HIGH, "No se detectó dependencia de operaciones extremas, resiste comisión x3 y hay estabilidad entre activos."
    if penalties == 1:
        return ROBUSTNESS_MEDIUM, "; ".join(reasons)
    return ROBUSTNESS_LOW, "; ".join(reasons)
