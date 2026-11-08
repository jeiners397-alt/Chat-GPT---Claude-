"""Verifica los umbrales congelados de clasificación (sección 6)."""

from src.classification import (
    CATEGORY_A,
    CATEGORY_B,
    CATEGORY_C,
    CATEGORY_D,
    classify_indicator_experiment,
)


def _stats(trades=40, symbols=10, expectancy=1.0, pf=1.5, net_return=10.0):
    return {
        "operaciones_ejecutadas": trades,
        "numero_activos_con_senal": symbols,
        "expectativa_matematica_pct": expectancy,
        "profit_factor": pf,
        "rentabilidad_neta_pct": net_return,
    }


def test_insufficient_sample_is_category_d():
    stats = _stats(trades=5, symbols=2)
    cat, _ = classify_indicator_experiment(stats, stats, stats)
    assert cat == CATEGORY_D


def test_consistent_positive_result_is_category_a():
    full = _stats(expectancy=1.0, pf=1.5, net_return=10.0)
    expl = _stats(net_return=8.0)
    conf = _stats(net_return=5.0)
    cat, _ = classify_indicator_experiment(full, expl, conf)
    assert cat == CATEGORY_A


def test_positive_overall_but_inconsistent_subperiods_is_category_d():
    full = _stats(expectancy=1.0, pf=1.5, net_return=10.0)
    expl = _stats(net_return=20.0)
    conf = _stats(net_return=-5.0)  # negativo en comprobación -> no consistente
    cat, _ = classify_indicator_experiment(full, expl, conf)
    assert cat == CATEGORY_D


def test_strongly_negative_result_is_category_c():
    full = _stats(expectancy=-2.0, pf=0.5, net_return=-8.0)
    cat, _ = classify_indicator_experiment(full, full, full)
    assert cat == CATEGORY_C


def test_near_breakeven_is_category_b():
    full = _stats(expectancy=-0.05, pf=0.95, net_return=-1.0)
    cat, _ = classify_indicator_experiment(full, full, full)
    assert cat == CATEGORY_B


def test_thresholds_are_frozen_constants_not_derived_from_data():
    from config import CATEGORY_A_THRESHOLDS, CATEGORY_C_THRESHOLDS, MIN_TRADES_FOR_CONCLUSIVE

    assert CATEGORY_A_THRESHOLDS["profit_factor_gt"] == 1.0
    assert MIN_TRADES_FOR_CONCLUSIVE == 30
    assert CATEGORY_C_THRESHOLDS["net_return_lt"] == -0.05
