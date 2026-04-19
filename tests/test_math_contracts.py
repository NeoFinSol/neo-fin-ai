from __future__ import annotations

from decimal import Decimal

from src.analysis.math.contracts import DerivedMetric, ValidityState


def test_derived_metric_requires_trace_and_inputs() -> None:
    metric = DerivedMetric(
        metric_id="current_ratio",
        canonical_value=Decimal("1.25"),
        projected_value=1.25,
        unit="ratio",
        formula_id="current_ratio",
        formula_version="v1",
        validity_state=ValidityState.VALID,
        inputs_used=[{"metric_key": "current_assets", "value": 125.0}],
        trace={"status": "valid", "numerator": 125.0, "denominator": 100.0},
    )

    assert metric.metric_id == "current_ratio"
    assert metric.trace["denominator"] == 100.0
    # Wave 1b: value is computed from projected_value
    assert metric.value == 1.25
    assert metric.value == metric.projected_value


def test_derived_metric_without_trace_is_invalid() -> None:
    from src.analysis.math.reason_codes import MATH_FORMULA_INPUTS_MISSING

    metric = DerivedMetric.invalid(
        metric_id="current_ratio",
        formula_id="current_ratio",
        formula_version="v1",
        reason_codes=[MATH_FORMULA_INPUTS_MISSING],
        inputs_snapshot={"current_assets": 125.0, "short_term_liabilities": None},
    )

    assert metric.validity_state == ValidityState.INVALID
    assert metric.reason_code == MATH_FORMULA_INPUTS_MISSING
    assert metric.reason_codes[0] == metric.reason_code
    assert MATH_FORMULA_INPUTS_MISSING in metric.reason_codes
    assert metric.trace["status"] == "invalid"
    assert metric.trace["formula_id"] == "current_ratio"
    assert metric.trace["inputs_snapshot"]["current_assets"] == 125.0
