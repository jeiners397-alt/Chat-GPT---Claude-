"""Verifica que el registro cubra los 200 indicadores y que no falte ninguno
sin documentar (sección 3 del encargo: 'NO OMITAS INDICADORES SIN DOCUMENTAR
SU ESTADO')."""

from src.indicators.registry import (
    STATUS_IMPLEMENTED,
    STATUS_NOT_EVALUABLE_DATA,
    STATUS_NOT_EVALUABLE_PATTERN,
    STATUS_NOT_EVALUABLE_PROPRIETARY,
    STATUS_NOT_EVALUABLE_RELATIONAL,
    STATUS_PENDING_NEXT_PHASE,
    build_full_registry,
    get_signal_function,
)
from src.indicators.signals import REGISTRY_FUNCTIONS


def test_registry_has_exactly_200_entries():
    registry = build_full_registry()
    assert len(registry) == 200


def test_every_entry_has_a_documented_status():
    registry = build_full_registry()
    valid_statuses = {
        STATUS_IMPLEMENTED,
        STATUS_NOT_EVALUABLE_DATA,
        STATUS_NOT_EVALUABLE_PATTERN,
        STATUS_NOT_EVALUABLE_PROPRIETARY,
        STATUS_NOT_EVALUABLE_RELATIONAL,
        STATUS_PENDING_NEXT_PHASE,
    }
    for d in registry:
        assert d.implementation_status in valid_statuses, d.name
        if d.implementation_status != STATUS_IMPLEMENTED:
            assert d.reason_if_not_implemented, f"{d.name} no tiene motivo documentado"


def test_every_implemented_indicator_has_a_working_signal_function():
    registry = build_full_registry()
    implemented = [d for d in registry if d.implementation_status == STATUS_IMPLEMENTED]
    assert len(implemented) > 0
    for d in implemented:
        fn = get_signal_function(d.signal_function_name)
        assert callable(fn)
        # Fichas completas: sección 3 exige 10 campos documentados.
        assert d.formula, d.name
        assert d.parameters, d.name
        assert d.timeframes, d.name
        assert d.data_required, d.name
        assert d.long_signal_description, d.name
        assert d.exit_condition, d.name
        assert d.technical_source, d.name


def test_no_catalog_id_is_implemented_and_unimplemented_at_once():
    registry = build_full_registry()
    ids = [d.catalog_id for d in registry]
    assert len(ids) == len(set(ids)), "Hay IDs de catálogo duplicados en el registro"


def test_implemented_count_matches_registered_functions():
    registry = build_full_registry()
    implemented = [d for d in registry if d.implementation_status == STATUS_IMPLEMENTED]
    assert len(implemented) == len(REGISTRY_FUNCTIONS)
