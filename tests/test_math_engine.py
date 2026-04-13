from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from src.analysis.math.engine import MathEngine
from src.analysis.math.precompute import build_precomputed_inputs
from src.analysis.math.registry import REGISTRY
from src.analysis.math.validators import normalize_inputs


def test_engine_computes_current_ratio_with_full_trace() -> None:
    engine = MathEngine()
    result = engine.compute(
        normalize_inputs(
            {
                "current_assets": {"value": 200.0, "confidence": 0.9},
                "short_term_liabilities": {"value": 100.0, "confidence": 0.8},
                "cash_and_equivalents": {"value": 40.0, "confidence": 0.95},
                "revenue": {"value": 500.0, "confidence": 0.85},
                "net_profit": {"value": 50.0, "confidence": 0.88},
                "equity": {"value": 300.0, "confidence": 0.92},
                "total_assets": {"value": 600.0, "confidence": 0.93},
            }
        )
    )

    metric = result["current_ratio"]
    assert metric.value == 2.0
    assert metric.validity_state == "valid"
    assert metric.trace["status"] == "valid"
    assert metric.trace["denominator"] == 100.0
    assert metric.confidence == 0.8


def test_engine_suppresses_unsafe_ebitda_metric() -> None:
    engine = MathEngine()
    result = engine.compute(
        normalize_inputs({"revenue": {"value": 500.0}, "ebitda": {"value": 80.0}})
    )

    metric = result["ebitda_margin"]
    assert metric.validity_state == "suppressed"
    assert "unsafe_metric_disabled" in metric.reason_codes
    assert metric.trace["status"] == "suppressed"


def test_engine_invalidates_semantically_bad_input() -> None:
    engine = MathEngine()
    result = engine.compute(
        normalize_inputs(
            {
                "current_assets": {"value": -10.0, "confidence": 0.9},
                "short_term_liabilities": {"value": 100.0, "confidence": 0.8},
            }
        )
    )

    metric = result["current_ratio"]
    assert metric.validity_state == "invalid"
    assert "current_assets:unexpected_negative_input" in metric.reason_codes


def test_engine_rejects_raw_inputs() -> None:
    engine = MathEngine()

    try:
        engine.compute({"current_assets": {"value": 200.0}})
    except TypeError as exc:
        assert "TypedInputs" in str(exc)
    else:
        raise AssertionError("MathEngine.compute must reject raw inputs")


def test_engine_invalidates_missing_required_inputs() -> None:
    engine = MathEngine()
    result = engine.compute(
        normalize_inputs({"current_assets": {"value": 200.0, "confidence": 0.9}})
    )

    metric = result["current_ratio"]
    assert metric.validity_state == "invalid"
    assert "missing_required_input:short_term_liabilities" in metric.reason_codes


def test_registry_is_immutable() -> None:
    try:
        REGISTRY["fake_metric"] = object()
    except TypeError:
        pass
    else:
        raise AssertionError("REGISTRY must be immutable")


def test_precompute_routes_approximated_ebitda_to_approximation_variant() -> None:
    values = build_precomputed_inputs(
        normalize_inputs(
            {
                "ebitda": {
                    "value": 100.0,
                    "confidence": 0.9,
                    "reason_codes": ["gross_profit_to_ebitda_approximation"],
                },
            }
        )
    )

    assert values["ebitda_reported"].value is None
    assert values["ebitda_canonical"].value is None
    assert values["ebitda_approximated"].value == 100.0


def test_precompute_routes_explicit_reported_ebitda_to_reported_variant() -> None:
    values = build_precomputed_inputs(
        normalize_inputs(
            {
                "ebitda": {"value": 100.0, "confidence": 0.9, "source": "reported"},
            }
        )
    )

    assert values["ebitda_reported"].value == 100.0
    assert values["ebitda_canonical"].value is None
    assert values["ebitda_approximated"].value is None


def test_precompute_keeps_ambiguous_ebitda_unmapped() -> None:
    values = build_precomputed_inputs(
        normalize_inputs(
            {
                "ebitda": {"value": 100.0, "confidence": 0.9},
            }
        )
    )

    assert values["ebitda_reported"].value is None
    assert values["ebitda_canonical"].value is None
    assert values["ebitda_approximated"].value is None


def test_precompute_keeps_debt_semantics_separate_from_liabilities() -> None:
    values = build_precomputed_inputs(
        normalize_inputs(
            {
                "short_term_borrowings": {"value": 20.0, "confidence": 0.8},
                "long_term_borrowings": {"value": 40.0, "confidence": 0.7},
                "liabilities": {"value": 400.0, "confidence": 0.95},
            }
        )
    )

    assert values["total_debt"].value == 60.0
    assert values["total_debt"].confidence == 0.7
    assert values["liabilities"].value == 400.0


def test_engine_emits_suppressed_placeholders_for_unsupported_legacy_metrics() -> None:
    engine = MathEngine()
    result = engine.compute(
        normalize_inputs(
            {
                "current_assets": {"value": 200.0},
                "short_term_liabilities": {"value": 100.0},
                "cash_and_equivalents": {"value": 25.0},
                "revenue": {"value": 500.0},
                "net_profit": {"value": 50.0},
                "equity": {"value": 300.0},
                "total_assets": {"value": 600.0},
            }
        )
    )

    for metric_id in {
        "quick_ratio",
        "roa",
        "roe",
        "financial_leverage",
        "financial_leverage_total",
        "financial_leverage_debt_only",
        "interest_coverage",
        "asset_turnover",
        "inventory_turnover",
        "receivables_turnover",
    }:
        metric = result[metric_id]
        assert metric.validity_state == "suppressed"
        assert metric.trace["status"] == "suppressed"


def test_engine_is_deterministic_for_same_inputs() -> None:
    engine = MathEngine()
    inputs = normalize_inputs(
        {
            "current_assets": {"value": 200.0, "confidence": 0.9},
            "short_term_liabilities": {"value": 100.0, "confidence": 0.8},
            "cash_and_equivalents": {"value": 25.0, "confidence": 0.9},
            "revenue": {"value": 500.0, "confidence": 0.9},
            "net_profit": {"value": 50.0, "confidence": 0.9},
            "equity": {"value": 300.0, "confidence": 0.9},
            "total_assets": {"value": 600.0, "confidence": 0.9},
        }
    )

    first = engine.compute(inputs)
    second = engine.compute(inputs)

    assert json.dumps(
        first["current_ratio"].model_dump(),
        sort_keys=True,
    ) == json.dumps(
        second["current_ratio"].model_dump(),
        sort_keys=True,
    )


def test_every_metric_has_stable_trace_status() -> None:
    engine = MathEngine()
    result = engine.compute(
        normalize_inputs(
            {
                "current_assets": {"value": 200.0, "confidence": 0.9},
                "short_term_liabilities": {"value": 100.0, "confidence": 0.8},
                "cash_and_equivalents": {"value": 25.0, "confidence": 0.9},
                "revenue": {"value": 500.0, "confidence": 0.9},
                "net_profit": {"value": 50.0, "confidence": 0.9},
                "equity": {"value": 300.0, "confidence": 0.9},
                "total_assets": {"value": 600.0, "confidence": 0.9},
            }
        )
    )

    for metric in result.values():
        assert metric.trace["status"] in {"valid", "invalid", "suppressed"}
        assert metric.trace["formula_id"] == metric.formula_id
        assert metric.trace["formula_version"] == metric.formula_version


def test_engine_strict_positive_denominator_rejects_zero() -> None:
    engine = MathEngine()
    result = engine.compute(
        normalize_inputs(
            {
                "current_assets": {"value": 200.0, "confidence": 0.9},
                "short_term_liabilities": {"value": 0.0, "confidence": 0.8},
            }
        )
    )

    metric = result["current_ratio"]
    assert metric.validity_state == "invalid"
    assert metric.value is None
    assert "denominator:short_term_liabilities:zero" in metric.reason_codes


def test_engine_strict_positive_denominator_rejects_negative() -> None:
    engine = MathEngine()
    result = engine.compute(
        normalize_inputs(
            {
                "current_assets": {"value": 200.0, "confidence": 0.9},
                "short_term_liabilities": {"value": -5.0, "confidence": 0.8},
            }
        )
    )

    metric = result["current_ratio"]
    assert metric.validity_state == "invalid"
    assert metric.value is None


def test_engine_strict_positive_denominator_rejects_near_zero() -> None:
    engine = MathEngine()
    result = engine.compute(
        normalize_inputs(
            {
                "current_assets": {"value": 200.0, "confidence": 0.9},
                "short_term_liabilities": {"value": 1e-12, "confidence": 0.8},
            }
        )
    )

    metric = result["current_ratio"]
    assert metric.validity_state == "invalid"
    assert metric.value is None
    assert "denominator:short_term_liabilities:near_zero" in metric.reason_codes


def test_engine_invalidates_non_finite_input() -> None:
    engine = MathEngine()
    result = engine.compute(
        normalize_inputs(
            {
                "current_assets": {"value": math.inf, "confidence": 0.9},
                "short_term_liabilities": {"value": 100.0, "confidence": 0.8},
            }
        )
    )

    metric = result["current_ratio"]
    assert metric.validity_state == "invalid"
    assert metric.value is None
    assert "current_assets:input_non_finite" in metric.reason_codes


def test_engine_invalidates_unexpected_unit() -> None:
    engine = MathEngine()
    result = engine.compute(
        normalize_inputs(
            {
                "current_assets": {"value": 200.0, "confidence": 0.9, "unit": "turns"},
                "short_term_liabilities": {"value": 100.0, "confidence": 0.8},
            }
        )
    )

    metric = result["current_ratio"]
    assert metric.validity_state == "invalid"
    assert metric.value is None
    assert "current_assets:unexpected_unit" in metric.reason_codes


def test_engine_missing_confidence_applies_penalty() -> None:
    engine = MathEngine()
    result = engine.compute(
        normalize_inputs(
            {
                "current_assets": {"value": 200.0, "confidence": 0.9},
                "short_term_liabilities": {"value": 100.0},
            }
        )
    )

    metric = result["current_ratio"]
    assert metric.value == 2.0
    assert metric.validity_state == "valid"
    assert metric.confidence == pytest.approx(0.9 * 0.9)
    assert metric.confidence_components["missing_confidence_penalty_applied"] is True
    assert metric.confidence_components["missing_confidence_penalty_factor"] == 0.9


def test_registry_derives_input_domain_constraints() -> None:
    from src.analysis.math.registry import (
        INPUT_DOMAIN_CONSTRAINTS,
        get_input_domain_constraint,
    )

    assert INPUT_DOMAIN_CONSTRAINTS["cash_and_equivalents"].requires_non_negative
    assert INPUT_DOMAIN_CONSTRAINTS["revenue"].requires_non_negative
    assert not get_input_domain_constraint("net_profit").requires_non_negative


def test_validators_module_has_no_hardcoded_domain_constraint_sets() -> None:
    source = Path("src/analysis/math/validators.py").read_text(encoding="utf-8")

    assert "EXPECTED_NON_NEGATIVE_INPUTS" not in source
