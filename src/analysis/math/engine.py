from __future__ import annotations

from src.analysis.math.contracts import (
    DerivedMetric,
    MetricComputationResult,
    MetricInputRef,
    MetricUnit,
    TypedInputs,
    ValidityState,
)
from src.analysis.math.policies import (
    MISSING_CONFIDENCE_PENALTY_FACTOR,
    DenominatorPolicy,
    SuppressionPolicy,
)
from src.analysis.math.precompute import build_precomputed_inputs
from src.analysis.math.registry import REGISTRY, MetricDefinition
from src.analysis.math.validators import classify_denominator


class MathEngine:
    def compute(self, inputs: TypedInputs) -> dict[str, DerivedMetric]:
        """Compute all registered metrics from validated typed inputs."""
        _assert_typed_inputs(inputs)
        prepared_inputs = build_precomputed_inputs(inputs)
        return {
            metric_id: _compute_metric(definition, prepared_inputs)
            for metric_id, definition in REGISTRY.items()
        }


def _assert_typed_inputs(inputs: TypedInputs) -> None:
    if not isinstance(inputs, dict):
        raise TypeError("MathEngine.compute accepts TypedInputs only")
    if any(not isinstance(value, MetricInputRef) for value in inputs.values()):
        raise TypeError("MathEngine.compute accepts TypedInputs only")


def _compute_metric(
    definition: MetricDefinition,
    prepared_inputs: TypedInputs,
) -> DerivedMetric:
    if definition.suppression_policy == SuppressionPolicy.SUPPRESS_UNSAFE:
        return _build_suppressed_metric(definition)
    trace_inputs = _collect_trace_inputs(definition, prepared_inputs)
    invalid_reasons = _collect_invalid_input_reasons(trace_inputs)
    if invalid_reasons:
        return _build_invalid_metric(definition, invalid_reasons, trace_inputs)
    missing_inputs = _collect_missing_inputs(trace_inputs)
    if missing_inputs:
        reason_codes = [
            f"missing_required_input:{metric_key}" for metric_key in missing_inputs
        ]
        return _build_invalid_metric(definition, reason_codes, trace_inputs)
    denominator_reason = _validate_denominator_policy(definition, prepared_inputs)
    if denominator_reason is not None:
        return _build_invalid_metric(definition, [denominator_reason], trace_inputs)
    computation = definition.compute(prepared_inputs)
    return _build_computed_metric(
        definition, trace_inputs, prepared_inputs, computation
    )


def _build_suppressed_metric(definition: MetricDefinition) -> DerivedMetric:
    return DerivedMetric(
        metric_id=definition.metric_id,
        value=None,
        unit=MetricUnit.RATIO,
        formula_id=definition.formula_id,
        formula_version=definition.formula_version,
        validity_state=ValidityState.SUPPRESSED,
        reason_codes=["unsafe_metric_disabled"],
        trace={
            "status": "suppressed",
            "formula_id": definition.formula_id,
            "formula_version": definition.formula_version,
        },
    )


def _collect_trace_inputs(
    definition: MetricDefinition,
    prepared_inputs: TypedInputs,
) -> list[MetricInputRef]:
    return [
        prepared_inputs.get(key, MetricInputRef(metric_key=key))
        for key in definition.required_inputs
    ]


def _collect_invalid_input_reasons(trace_inputs: list[MetricInputRef]) -> list[str]:
    return [
        f"{item.metric_key}:{reason}"
        for item in trace_inputs
        for reason in item.reason_codes
    ]


def _collect_missing_inputs(trace_inputs: list[MetricInputRef]) -> list[str]:
    return [item.metric_key for item in trace_inputs if item.value is None]


def _validate_denominator_policy(
    definition: MetricDefinition,
    prepared_inputs: TypedInputs,
) -> str | None:
    denominator_ref = prepared_inputs.get(
        definition.denominator_key,
        MetricInputRef(metric_key=definition.denominator_key),
    )
    denominator_state = classify_denominator(denominator_ref.value)
    if definition.denominator_policy == DenominatorPolicy.STRICT_POSITIVE:
        if denominator_state != "valid":
            return f"denominator:{definition.denominator_key}:{denominator_state}"
    return None


def _build_invalid_metric(
    definition: MetricDefinition,
    reason_codes: list[str],
    trace_inputs: list[MetricInputRef],
) -> DerivedMetric:
    return DerivedMetric.invalid(
        metric_id=definition.metric_id,
        formula_id=definition.formula_id,
        formula_version=definition.formula_version,
        reason_codes=reason_codes,
        inputs_snapshot={item.metric_key: item.value for item in trace_inputs},
    )


def _build_computed_metric(
    definition: MetricDefinition,
    trace_inputs: list[MetricInputRef],
    prepared_inputs: TypedInputs,
    computation: MetricComputationResult,
) -> DerivedMetric:
    confidence, confidence_components = _derive_confidence(trace_inputs)
    trace_status = "valid" if computation.value is not None else "invalid"
    return DerivedMetric(
        metric_id=definition.metric_id,
        value=computation.value,
        unit=MetricUnit.RATIO,
        formula_id=definition.formula_id,
        formula_version=definition.formula_version,
        validity_state=(
            ValidityState.VALID
            if computation.value is not None
            else ValidityState.INVALID
        ),
        inputs_used=trace_inputs,
        reason_codes=list(computation.extra_reason_codes),
        confidence=confidence,
        confidence_components=confidence_components,
        trace=computation.trace
        | {
            "status": trace_status,
            "inputs": {
                key: prepared_inputs.get(
                    key, MetricInputRef(metric_key=key)
                ).model_dump()
                for key in definition.required_inputs
            },
            "formula_id": definition.formula_id,
            "formula_version": definition.formula_version,
        },
    )


def _derive_confidence(
    trace_inputs: list[MetricInputRef],
) -> tuple[float | None, dict[str, float | bool]]:
    confidences = [
        item.confidence for item in trace_inputs if item.confidence is not None
    ]
    if not confidences:
        return None, {"missing_confidence_penalty_applied": False}
    derived_confidence = min(confidences)
    penalty_applied = len(confidences) < len(trace_inputs)
    if penalty_applied:
        derived_confidence = round(
            derived_confidence * MISSING_CONFIDENCE_PENALTY_FACTOR, 4
        )
    return derived_confidence, {
        "inputs_min": min(confidences),
        "missing_confidence_penalty_applied": penalty_applied,
        "missing_confidence_penalty_factor": MISSING_CONFIDENCE_PENALTY_FACTOR
        if penalty_applied
        else 1.0,
    }
