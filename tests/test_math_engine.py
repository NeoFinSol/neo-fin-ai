from __future__ import annotations

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


def test_precompute_keeps_ebitda_variants_separate() -> None:
    values = build_precomputed_inputs(
        normalize_inputs(
            {
                "ebitda": {"value": 100.0, "confidence": 0.9},
                "short_term_borrowings": {"value": 20.0, "confidence": 0.8},
                "long_term_borrowings": {"value": 40.0, "confidence": 0.7},
                "liabilities": {"value": 400.0, "confidence": 0.95},
            }
        )
    )

    assert values["ebitda_reported"].value == 100.0
    assert values["ebitda_canonical"].value is None
    assert values["ebitda_approximated"].value is None
    assert values["total_debt"].value == 60.0
    assert values["total_debt"].confidence == 0.7
    assert values["liabilities"].value == 400.0
