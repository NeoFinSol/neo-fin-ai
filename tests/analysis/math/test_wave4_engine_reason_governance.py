"""Wave 4 — engine outward reason governance (Phase 3 follow-up fixes)."""

from __future__ import annotations

from types import MappingProxyType

import pytest

from src.analysis.math.contracts import MetricInputRef, TypedInputs, ValidityState
from src.analysis.math.engine import MathEngine
from src.analysis.math.policies import (
    AveragingPolicy,
    DenominatorPolicy,
    SuppressionPolicy,
)
from src.analysis.math.reason_codes import (
    MATH_COVERAGE_INTENTIONALLY_SUPPRESSED,
    MATH_DENOMINATOR_INPUT_MISSING,
    MATH_REQUIRED_INPUT_MISSING,
)
from src.analysis.math.registry import MetricCoverageClass, MetricDefinition
from src.analysis.math.validators import normalize_inputs


def _ratio_compute(values):
    from src.analysis.math.registry import _ratio

    return _ratio("input_a", "input_b")(values)


def _forbidden_compute(_values):
    raise AssertionError("compute must not run")


def _patch_registry(
    monkeypatch: pytest.MonkeyPatch,
    definitions: dict[str, MetricDefinition],
) -> None:
    monkeypatch.setattr(
        "src.analysis.math.engine.REGISTRY",
        MappingProxyType(definitions),
    )


def test_engine_integration_invalid_multi_declared_reasons_resolved_deterministically() -> None:
    """Full engine path: multiple eligible codes → primary + ordered supporting (Wave 4)."""
    engine = MathEngine()
    inputs: TypedInputs = {
        "current_assets": MetricInputRef(metric_key="current_assets", value=None),
    }
    result = engine.compute(inputs)["current_ratio"]
    assert result.validity_state is ValidityState.INVALID
    assert result.reason_code == MATH_REQUIRED_INPUT_MISSING
    assert result.reason_codes[0] == result.reason_code
    assert result.reason_codes == [
        MATH_REQUIRED_INPUT_MISSING,
        MATH_DENOMINATOR_INPUT_MISSING,
    ]


def test_invalid_path_undeclared_input_reason_emits_trace_not_outward_codes(
    monkeypatch: pytest.MonkeyPatch,
):
    """Undeclared tokens on inputs must not be invented as MATH_INPUT_NOT_NUMERIC."""
    definition = MetricDefinition(
        metric_id="ratio_probe",
        formula_id="ratio_probe",
        formula_version="v1",
        required_inputs=("input_a", "input_b"),
        averaging_policy=AveragingPolicy.NONE,
        suppression_policy=SuppressionPolicy.NEVER,
        compute=_ratio_compute,
        coverage_class=MetricCoverageClass.FULLY_SUPPORTED,
        denominator_key="input_b",
        denominator_policy=DenominatorPolicy.STRICT_POSITIVE,
    )
    _patch_registry(monkeypatch, {"ratio_probe": definition})
    inputs: TypedInputs = normalize_inputs(
        {
            "input_a": MetricInputRef(
                metric_key="input_a",
                value=10.0,
                reason_codes=["Z_UNDECLARED_ENGINE_GOVERNANCE_PROBE"],
            ),
            "input_b": {"value": 2.0},
        }
    )
    result = MathEngine().compute(inputs)["ratio_probe"]
    assert result.validity_state is ValidityState.INVALID
    from src.analysis.math.reason_codes import MATH_COMPUTE_BASIS_MISSING

    assert result.reason_code == MATH_COMPUTE_BASIS_MISSING
    assert result.reason_codes == [MATH_COMPUTE_BASIS_MISSING]
    details = result.trace.get("input_invalidity_details")
    assert isinstance(details, list) and len(details) == 1
    assert details[0]["upstream_reason"] == "Z_UNDECLARED_ENGINE_GOVERNANCE_PROBE"
    assert details[0]["outward_reason"] == "Z_UNDECLARED_ENGINE_GOVERNANCE_PROBE"


def test_refusal_merge_drops_undeclared_input_reason_strings(
    monkeypatch: pytest.MonkeyPatch,
):
    """Merged refusal outward list must be subset of declared registry codes."""
    definition = MetricDefinition(
        metric_id="suppressed_metric_governance",
        formula_id="suppressed_metric_governance",
        formula_version="v1",
        required_inputs=("input_a",),
        averaging_policy=AveragingPolicy.NONE,
        suppression_policy=SuppressionPolicy.NEVER,
        compute=_forbidden_compute,
        coverage_class=MetricCoverageClass.INTENTIONALLY_SUPPRESSED,
    )
    _patch_registry(monkeypatch, {"suppressed_metric_governance": definition})
    result = MathEngine().compute(
        normalize_inputs(
            {
                "input_a": MetricInputRef(
                    metric_key="input_a",
                    value=10.0,
                    reason_codes=["Z_UNDECLARED_MERGE_PROBE"],
                ),
            }
        )
    )["suppressed_metric_governance"]

    assert result.validity_state is ValidityState.SUPPRESSED
    assert result.reason_code == MATH_COVERAGE_INTENTIONALLY_SUPPRESSED
    assert result.reason_codes == [MATH_COVERAGE_INTENTIONALLY_SUPPRESSED]
