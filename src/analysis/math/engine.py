"""
Math engine orchestration layer for Math Layer v2 — Wave 1a.

Responsibilities:
- Resolve metric definitions from registry
- Orchestrate formula execution
- Route raw compute results through finalization + projection boundaries
- Map internal numeric failures to existing compatible invalid/refusal semantics
- Build existing outward-compatible DerivedMetric result objects
- Attach internal finalization evidence to trace

Ownership rules:
- Engine MUST NOT define its own coercion helper.
- Engine MUST NOT define its own rounding helper.
- Engine MUST NOT directly serialize raw floats from compute results.
- Engine MUST call finalize_numeric_result() then project_number() for every
  valid numeric compute result.
- Engine is the canonical mapper from internal numeric failures to outward semantics.
"""

from __future__ import annotations

import logging
from decimal import Decimal

from src.analysis.math.contracts import (
    DerivedMetric,
    MetricComputationResult,
    MetricInputRef,
    MetricUnit,
    TypedInputs,
    ValidityState,
)
from src.analysis.math.finalization import finalize_numeric_result
from src.analysis.math.numeric_errors import (
    NonFiniteNumberError,
    NumericCoercionError,
    NumericNormalizationError,
    NumericRoundingError,
    ProjectionSafetyError,
)
from src.analysis.math.policies import (
    MISSING_CONFIDENCE_PENALTY_FACTOR,
    DenominatorPolicy,
    SuppressionPolicy,
)
from src.analysis.math.precompute import build_precomputed_inputs
from src.analysis.math.projections import project_number
from src.analysis.math.registry import REGISTRY, MetricDefinition
from src.analysis.math.rounding import ROUNDING_POLICY_RATIO_STANDARD
from src.analysis.math.validators import DenominatorClass, classify_denominator

logger = logging.getLogger(__name__)

# Internal numeric exception types that engine maps to invalid/refusal semantics
_NUMERIC_FAILURE_TYPES = (
    NumericCoercionError,
    NonFiniteNumberError,
    NumericNormalizationError,
    NumericRoundingError,
    ProjectionSafetyError,
)


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

    # Only validate denominator policy for ratio-like metrics
    if (
        definition.denominator_key is not None
        and definition.denominator_policy is not None
    ):
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
        canonical_value=None,
        projected_value=None,
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


def _map_denominator_class_to_validity(
    denominator_class: DenominatorClass,
) -> str:
    """Deterministic refusal mapping per Section 13.

    Maps denominator classification to validity state for refusal messages.
    All invalid classes map to "invalid" except MISSING which maps to "unavailable".

    Reference: .agent/math_layer_v2_wave2_spec.md Section 13
    """
    if denominator_class == DenominatorClass.MISSING:
        return "unavailable"
    return "invalid"


def _validate_denominator_policy(
    definition: MetricDefinition,
    prepared_inputs: TypedInputs,
) -> str | None:
    """E1-E6: Engine denominator gate with canonical policy evaluation.

    Integrates classifier + evaluator for full denominator policy enforcement.
    Engine is sole owner of final refusal assembly (Section 8, 11.2).

    Deterministic refusal mapping (Section 13):
    - MISSING → UNAVAILABLE
    - ZERO/SIGNED_ZERO → INVALID
    - NON_FINITE → INVALID
    - NEAR_ZERO_FORBIDDEN → INVALID
    - NEGATIVE_FINITE under STRICT_POSITIVE → INVALID

    Returns:
        Error reason string if validation fails, None if passes

    Reference: .agent/math_layer_v2_wave2_spec.md Section 8, 11, 13
    """
    from src.analysis.math.policies import DenominatorClass, evaluate_denominator_policy

    # E2: Extract denominator from explicit declaration
    denominator_ref = prepared_inputs.get(
        definition.denominator_key,
        MetricInputRef(metric_key=definition.denominator_key),
    )

    # E3: Call canonical classifier
    denominator_class = classify_denominator(denominator_ref.value)

    # Handle missing denominator → UNAVAILABLE (Section 13.1)
    if denominator_class == DenominatorClass.MISSING:
        return f"denominator:{definition.denominator_key}:missing:unavailable"

    # E4: Apply canonical policy evaluator
    decision = evaluate_denominator_policy(
        definition.denominator_policy,
        denominator_class,
    )

    # E5-E6: Engine-owned refusal assembly with deterministic mapping
    if not decision.allowed:
        validity = _map_denominator_class_to_validity(denominator_class)
        return (
            f"denominator:{definition.denominator_key}:"
            f"{denominator_class.value}:{validity}:"
            f"{decision.refusal_reason}"
        )

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

    # W1A-008 / B1-006: Route raw compute result through finalization + projection.
    # Engine assigns canonical_value (Decimal) and projected_value (float).
    # value is computed automatically from projected_value.
    canonical_decimal, projected_float, finalization_trace = _finalize_and_project(
        definition, computation
    )

    trace_status = "valid" if projected_float is not None else "invalid"
    return DerivedMetric(
        metric_id=definition.metric_id,
        canonical_value=canonical_decimal,
        projected_value=projected_float,
        unit=MetricUnit.RATIO,
        formula_id=definition.formula_id,
        formula_version=definition.formula_version,
        validity_state=(
            ValidityState.VALID
            if projected_float is not None
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
            # W1A-010: machine-checkable finalization evidence in trace
            "numeric_finalization": finalization_trace,
        },
    )


def _finalize_and_project(
    definition: MetricDefinition,
    computation: MetricComputationResult,
) -> tuple[Decimal | None, float | None, dict]:
    """
    Route raw compute result through finalization + projection boundaries.

    Returns (canonical_decimal, projected_float, finalization_evidence_dict).

    W1A-008 / B1-006: Engine calls finalize_numeric_result() then project_number().
    W1A-009: Maps internal numeric failures to existing compatible invalid/refusal path.
    W1A-010: Returns machine-checkable evidence dict for trace attachment.
    B1-001: Returns canonical Decimal for canonical_value assignment.
    B1-002: Returns projected float for projected_value assignment.
    """
    if computation.value is None:
        return None, None, {"hardening": "skipped_none_value"}

    rounding_policy = getattr(
        definition, "rounding_policy", ROUNDING_POLICY_RATIO_STANDARD
    )

    try:
        projection_ready = finalize_numeric_result(
            computation.value,
            rounding_policy=rounding_policy,
        )
        projected = project_number(projection_ready.value)
        evidence = {
            "hardening": "applied",
            "normalization_policy": (
                projection_ready.evidence.normalization.normalization_policy
            ),
            "rounding_policy": projection_ready.evidence.rounding.rounding_policy,
            "precision_stage": projection_ready.evidence.rounding.precision_stage,
            "signed_zero_normalized": (
                projection_ready.evidence.normalization.signed_zero_normalized
            ),
            "projection_rounding_policy": projected.evidence.projection_rounding_policy,
        }
        # Return canonical Decimal truth + projected float + evidence
        return projection_ready.value, projected.value, evidence

    except _NUMERIC_FAILURE_TYPES as exc:
        # W1A-009: Map internal numeric failure to existing invalid/refusal semantics.
        logger.warning(
            "Numeric finalization failure for metric %s: %s",
            definition.metric_id,
            exc,
        )
        return (
            None,
            None,
            {
                "hardening": "failed",
                "failure_type": type(exc).__name__,
                "failure_detail": str(exc),
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
        "missing_confidence_penalty_factor": (
            MISSING_CONFIDENCE_PENALTY_FACTOR if penalty_applied else 1.0
        ),
    }
