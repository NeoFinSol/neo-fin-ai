"""
Math engine orchestration layer for Math Layer v2.
"""

from __future__ import annotations

import logging
from decimal import Decimal

from src.analysis.math.candidates import (
    CandidateSet,
    MetricCandidate,
    build_candidate_set,
)
from src.analysis.math.compute_basis import (
    ComputeBasis,
    ComputeBasisStatus,
    materialize_compute_basis,
)
from src.analysis.math.contracts import (
    DerivedMetric,
    MetricComputationResult,
    MetricInputRef,
    MetricUnit,
    TypedInputs,
    ValidityState,
)
from src.analysis.math.coverage import CoverageGateResult, enforce_coverage
from src.analysis.math.eligibility import EligibilityResult, evaluate_eligibility
from src.analysis.math.finalization import finalize_numeric_result
from src.analysis.math.numeric_errors import (
    NonFiniteNumberError,
    NumericCoercionError,
    NumericNormalizationError,
    NumericRoundingError,
    ProjectionSafetyError,
)
from src.analysis.math.precompute import build_precomputed_candidates
from src.analysis.math.projections import project_number
from src.analysis.math.refusals import MetricRefusal
from src.analysis.math.registry import REGISTRY, MetricCoverageClass, MetricDefinition
from src.analysis.math.resolver_engine import ResolverDecision, resolve_metric_family
from src.analysis.math.resolver_reason_codes import WAVE3_REASON_COMPUTE_BASIS_MISSING
from src.analysis.math.rounding import ROUNDING_POLICY_RATIO_STANDARD
from src.analysis.math.trace_builders import (
    build_candidate_trace,
    build_coverage_trace,
    build_eligibility_trace,
    build_refusal_trace,
)
from src.analysis.math.validators import (
    DenominatorClass,
    classify_denominator,
    validate_metric_inputs_unit_compatibility,
)

logger = logging.getLogger(__name__)

_NUMERIC_FAILURE_TYPES = (
    NumericCoercionError,
    NonFiniteNumberError,
    NumericNormalizationError,
    NumericRoundingError,
    ProjectionSafetyError,
)
_DEFAULT_REASON_CODE = WAVE3_REASON_COMPUTE_BASIS_MISSING


class MathEngine:
    def compute(self, inputs: TypedInputs) -> dict[str, DerivedMetric]:
        _assert_typed_inputs(inputs)
        precomputed_candidates = build_precomputed_candidates(inputs)
        candidate_set = build_candidate_set(precomputed_candidates)
        return {
            metric_id: _compute_metric(definition, inputs, candidate_set)
            for metric_id, definition in REGISTRY.items()
        }


def _assert_typed_inputs(inputs: TypedInputs) -> None:
    if not isinstance(inputs, dict):
        raise TypeError("MathEngine.compute accepts TypedInputs only")
    if any(not isinstance(value, MetricInputRef) for value in inputs.values()):
        raise TypeError("MathEngine.compute accepts TypedInputs only")


def _compute_metric(
    definition: MetricDefinition,
    inputs: TypedInputs,
    candidate_set: CandidateSet,
) -> DerivedMetric:
    eligibility_result = _maybe_evaluate_eligibility(definition, candidate_set)
    resolver_decision = _maybe_resolve_metric(definition, candidate_set)
    coverage_result = _evaluate_coverage(definition, candidate_set, resolver_decision)
    trace_fragments = _trace_fragments(
        definition,
        candidate_set,
        eligibility_result,
        resolver_decision,
        coverage_result,
    )
    eligibility_refusal = _refusal_from_eligibility(eligibility_result)
    if eligibility_refusal is not None:
        return _build_refusal_metric(
            definition,
            inputs,
            eligibility_refusal,
            ValidityState.INVALID,
            trace_fragments,
        )
    resolver_refusal = _refusal_from_resolver(resolver_decision)
    if resolver_refusal is not None:
        return _build_refusal_metric(
            definition,
            inputs,
            resolver_refusal,
            ValidityState.INVALID,
            trace_fragments,
        )
    coverage_refusal = coverage_result.refusal
    if coverage_refusal is not None:
        return _build_refusal_metric(
            definition,
            inputs,
            coverage_refusal,
            coverage_result.final_validity_state or ValidityState.INVALID,
            trace_fragments,
        )
    selected_candidates = _select_compute_candidates(
        definition,
        candidate_set,
        resolver_decision,
    )
    compute_basis = materialize_compute_basis(
        definition,
        selected_candidates=selected_candidates,
        eligibility_result=eligibility_result,
        approximation_semantics=_approximation_semantics(resolver_decision),
    )
    trace_fragments["compute_basis_fragment"] = dict(compute_basis.trace_payload)
    if compute_basis.status is ComputeBasisStatus.REFUSED:
        return _build_refusal_metric(
            definition,
            inputs,
            compute_basis.refusal,
            ValidityState.INVALID,
            trace_fragments,
        )
    compute_inputs = _build_compute_inputs(definition, inputs, compute_basis)
    trace_inputs = _collect_trace_inputs(definition, compute_inputs)
    invalid_reasons = _collect_invalid_input_reasons(trace_inputs)
    if invalid_reasons:
        return _build_invalid_metric(
            definition,
            invalid_reasons,
            trace_inputs,
            trace_fragments,
        )
    missing_inputs = _collect_missing_inputs(trace_inputs)
    denominator_reason: str | None = None
    if _has_denominator_policy(definition):
        denominator_reason = _validate_denominator_policy(definition, compute_inputs)
        missing_inputs = [
            metric_key
            for metric_key in missing_inputs
            if metric_key != definition.denominator_key
        ]
    if denominator_reason is not None or missing_inputs:
        reason_codes: list[str] = []
        if denominator_reason is not None:
            reason_codes.append(denominator_reason)
        reason_codes.extend(
            f"missing_required_input:{metric_key}" for metric_key in missing_inputs
        )
        return _build_invalid_metric(
            definition,
            reason_codes,
            trace_inputs,
            trace_fragments,
        )
    unit_reason = validate_metric_inputs_unit_compatibility(definition, compute_inputs)
    if unit_reason is not None:
        return _build_invalid_metric(
            definition,
            [unit_reason],
            trace_inputs,
            trace_fragments,
        )
    computation = definition.compute(compute_inputs)
    return _build_computed_metric(
        definition,
        trace_inputs,
        compute_inputs,
        computation,
        trace_fragments,
    )


def _maybe_evaluate_eligibility(
    definition: MetricDefinition,
    candidate_set: CandidateSet,
) -> EligibilityResult | None:
    if definition.average_balance_policy_ref is None:
        return None
    opening = _first_matching_candidate(
        candidate_set,
        definition.denominator_key,
        "opening_balance",
    )
    closing = _first_matching_candidate(
        candidate_set,
        definition.denominator_key,
        "closing_balance",
    )
    return evaluate_eligibility(
        definition,
        opening_candidate=opening,
        closing_candidate=closing,
    )


def _maybe_resolve_metric(
    definition: MetricDefinition,
    candidate_set: CandidateSet,
) -> ResolverDecision | None:
    if definition.resolver_slot is None:
        return None
    if definition.coverage_class in (
        MetricCoverageClass.INTENTIONALLY_SUPPRESSED,
        MetricCoverageClass.OUT_OF_SCOPE,
    ):
        return None
    return resolve_metric_family(definition, candidate_set)


def _evaluate_coverage(
    definition: MetricDefinition,
    candidate_set: CandidateSet,
    resolver_decision: ResolverDecision | None,
) -> CoverageGateResult:
    return enforce_coverage(
        definition,
        selected_candidate=_selected_resolver_candidate(
            candidate_set, resolver_decision
        ),
        approximation_semantics=_approximation_semantics(resolver_decision),
    )


def _trace_fragments(
    definition: MetricDefinition,
    candidate_set: CandidateSet,
    eligibility_result: EligibilityResult | None,
    resolver_decision: ResolverDecision | None,
    coverage_result: CoverageGateResult,
) -> dict[str, object]:
    fragments = {
        "candidate_fragment": [
            build_candidate_trace(candidate)
            for candidate in _relevant_candidates(definition, candidate_set)
        ],
        "coverage_fragment": build_coverage_trace(definition, coverage_result),
    }
    if eligibility_result is not None:
        fragments["eligibility_fragment"] = build_eligibility_trace(eligibility_result)
    if resolver_decision is not None:
        fragments["resolver_fragment"] = dict(resolver_decision.trace_payload)
    return fragments


def _relevant_candidates(
    definition: MetricDefinition,
    candidate_set: CandidateSet,
) -> tuple[MetricCandidate, ...]:
    metric_keys = {definition.metric_id, *definition.required_inputs}
    if definition.denominator_key is not None:
        metric_keys.add(definition.denominator_key)
    candidates = [
        candidate
        for metric_key in sorted(metric_keys)
        for candidate in candidate_set.candidates_by_metric.get(metric_key, ())
    ]
    return tuple(candidates)


def _refusal_from_eligibility(
    eligibility_result: EligibilityResult | None,
) -> MetricRefusal | None:
    if eligibility_result is None:
        return None
    return eligibility_result.refusal


def _refusal_from_resolver(
    resolver_decision: ResolverDecision | None,
) -> MetricRefusal | None:
    if resolver_decision is None:
        return None
    return resolver_decision.refusal


def _select_compute_candidates(
    definition: MetricDefinition,
    candidate_set: CandidateSet,
    resolver_decision: ResolverDecision | None,
) -> tuple[MetricCandidate, ...]:
    return tuple(
        candidate
        for required_input in definition.required_inputs
        for candidate in [
            _candidate_for_required_input(
                definition, candidate_set, resolver_decision, required_input
            )
        ]
        if candidate is not None
    )


def _candidate_for_required_input(
    definition: MetricDefinition,
    candidate_set: CandidateSet,
    resolver_decision: ResolverDecision | None,
    required_input: str,
) -> MetricCandidate | None:
    if _is_average_balance_input(definition, required_input):
        return _average_balance_candidate(candidate_set, required_input)
    if _uses_resolver_candidate(definition, required_input):
        return _selected_resolver_candidate(candidate_set, resolver_decision)
    return _first_ready_candidate(candidate_set, required_input)


def _is_average_balance_input(
    definition: MetricDefinition,
    required_input: str,
) -> bool:
    return (
        definition.average_balance_policy_ref is not None
        and definition.denominator_key == required_input
    )


def _average_balance_candidate(
    candidate_set: CandidateSet,
    required_input: str,
) -> MetricCandidate | None:
    candidates = candidate_set.candidates_by_metric.get(required_input, ())
    for candidate in candidates:
        if candidate.synthetic_key == required_input:
            return candidate
    return _first_ready_candidate(candidate_set, required_input)


def _uses_resolver_candidate(
    definition: MetricDefinition,
    required_input: str,
) -> bool:
    if definition.resolver_slot is None:
        return False
    prefix = definition.resolver_required_input_prefix
    if prefix is None:
        return False
    return required_input.startswith(prefix)


def _build_compute_inputs(
    definition: MetricDefinition,
    inputs: TypedInputs,
    compute_basis: ComputeBasis,
) -> TypedInputs:
    compute_inputs = {key: value.model_copy(deep=True) for key, value in inputs.items()}
    for required_input in definition.required_inputs:
        compute_inputs.setdefault(
            required_input, MetricInputRef(metric_key=required_input)
        )
    for candidate in compute_basis.selected_candidates:
        target_key = _target_input_key(definition, candidate)
        compute_inputs[target_key] = _metric_input_ref(
            target_key,
            candidate,
            baseline=compute_inputs.get(target_key),
        )
    return compute_inputs


def _target_input_key(
    definition: MetricDefinition,
    candidate: MetricCandidate,
) -> str:
    if candidate.metric_key in definition.required_inputs:
        return candidate.metric_key
    bridge = definition.resolver_bridge_input_key
    if bridge is not None:
        return bridge
    return candidate.metric_key


def _metric_input_ref(
    metric_key: str,
    candidate: MetricCandidate,
    *,
    baseline: MetricInputRef | None,
) -> MetricInputRef:
    return MetricInputRef(
        metric_key=metric_key,
        value=_candidate_value(candidate),
        confidence=None if baseline is None else baseline.confidence,
        unit=candidate.unit.value,
        source=candidate.provenance.producer if baseline is None else baseline.source,
    )


def _candidate_value(candidate: MetricCandidate) -> float | None:
    if candidate.canonical_value is None:
        return None
    return candidate.canonical_value.__float__()


def _selected_resolver_candidate(
    candidate_set: CandidateSet,
    resolver_decision: ResolverDecision | None,
) -> MetricCandidate | None:
    if resolver_decision is None or resolver_decision.selected_candidate_id is None:
        return None
    return _candidate_by_id(candidate_set, resolver_decision.selected_candidate_id)


def _candidate_by_id(
    candidate_set: CandidateSet,
    candidate_id: str,
) -> MetricCandidate | None:
    for candidates in candidate_set.candidates_by_metric.values():
        for candidate in candidates:
            if candidate.candidate_id == candidate_id:
                return candidate
    return None


def _approximation_semantics(
    resolver_decision: ResolverDecision | None,
) -> bool:
    if resolver_decision is None:
        return False
    return bool(resolver_decision.trace_payload.get("approximation_semantics"))


def _first_ready_candidate(
    candidate_set: CandidateSet,
    metric_key: str | None,
) -> MetricCandidate | None:
    if metric_key is None:
        return None
    for candidate in candidate_set.candidates_by_metric.get(metric_key, ()):
        if candidate.candidate_state.value == "READY":
            return candidate
    return None


def _first_matching_candidate(
    candidate_set: CandidateSet,
    metric_key: str | None,
    precedence_group: str,
) -> MetricCandidate | None:
    if metric_key is None:
        return None
    for candidate in candidate_set.candidates_by_metric.get(metric_key, ()):
        if candidate.precedence_group == precedence_group:
            return candidate
    return None


def _collect_trace_inputs(
    definition: MetricDefinition,
    compute_inputs: TypedInputs,
) -> list[MetricInputRef]:
    return [
        compute_inputs.get(key, MetricInputRef(metric_key=key))
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


def _build_invalid_metric(
    definition: MetricDefinition,
    reason_codes: list[str],
    trace_inputs: list[MetricInputRef],
    trace_fragments: dict[str, object],
) -> DerivedMetric:
    metric = DerivedMetric.invalid(
        metric_id=definition.metric_id,
        formula_id=definition.formula_id,
        formula_version=definition.formula_version,
        reason_codes=reason_codes,
        inputs_snapshot={item.metric_key: item.value for item in trace_inputs},
    )
    trace = metric.trace | trace_fragments
    return metric.model_copy(update={"trace": trace})


def _build_refusal_metric(
    definition: MetricDefinition,
    inputs: TypedInputs,
    refusal: MetricRefusal | None,
    validity_state: ValidityState,
    trace_fragments: dict[str, object],
) -> DerivedMetric:
    actual_refusal = refusal or _default_refusal()
    if "compute_basis_fragment" not in trace_fragments:
        trace_fragments = {
            **trace_fragments,
            "compute_basis_fragment": {
                "status": "REFUSED",
                "reason_codes": actual_refusal.reason_codes,
            },
        }
    reason_codes = _merged_refusal_reason_codes(definition, inputs, actual_refusal)
    trace = {
        "status": validity_state.value,
        "formula_id": definition.formula_id,
        "formula_version": definition.formula_version,
        "inputs": {
            key: inputs.get(key, MetricInputRef(metric_key=key)).model_dump()
            for key in definition.required_inputs
        },
        **trace_fragments,
        "refusal_fragment": build_refusal_trace(actual_refusal),
    }
    return DerivedMetric(
        metric_id=definition.metric_id,
        canonical_value=None,
        projected_value=None,
        unit=MetricUnit.RATIO,
        formula_id=definition.formula_id,
        formula_version=definition.formula_version,
        validity_state=validity_state,
        inputs_used=_collect_trace_inputs(definition, inputs),
        reason_codes=reason_codes,
        trace=trace,
    )


def _merged_refusal_reason_codes(
    definition: MetricDefinition,
    inputs: TypedInputs,
    refusal: MetricRefusal,
) -> list[str]:
    input_reasons = [
        reason
        for key in definition.required_inputs
        for reason in inputs.get(key, MetricInputRef(metric_key=key)).reason_codes
    ]
    return list(dict.fromkeys((*refusal.reason_codes, *input_reasons)))


def _default_refusal() -> MetricRefusal:
    from src.analysis.math.refusals import make_resolver_refusal

    return make_resolver_refusal(
        metric_key="unknown_metric",
        reason_code=_DEFAULT_REASON_CODE,
        details={},
    )


def _has_denominator_policy(definition: MetricDefinition) -> bool:
    return (
        definition.denominator_key is not None
        and definition.denominator_policy is not None
    )


def _map_denominator_class_to_reason_status(
    denominator_class: DenominatorClass,
) -> str:
    """Deterministic refusal mapping per Section 13.

    Maps denominator classification to the reason-code status segment.
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
    from src.analysis.math.policies import evaluate_denominator_policy

    denominator_ref = prepared_inputs.get(
        definition.denominator_key,
        MetricInputRef(metric_key=definition.denominator_key),
    )
    denominator_class = classify_denominator(denominator_ref.value)
    if denominator_class == DenominatorClass.MISSING:
        return f"denominator:{definition.denominator_key}:missing:unavailable"
    decision = evaluate_denominator_policy(
        definition.denominator_policy,
        denominator_class,
    )
    if not decision.allowed:
        validity = _map_denominator_class_to_reason_status(denominator_class)
        return (
            f"denominator:{definition.denominator_key}:"
            f"{denominator_class.value}:{validity}:"
            f"{decision.refusal_reason}"
        )
    return None


def _build_computed_metric(
    definition: MetricDefinition,
    trace_inputs: list[MetricInputRef],
    compute_inputs: TypedInputs,
    computation: MetricComputationResult,
    trace_fragments: dict[str, object],
) -> DerivedMetric:
    confidence, confidence_components = _derive_confidence(trace_inputs)
    canonical_decimal, projected_float, finalization_trace = _finalize_and_project(
        definition,
        computation,
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
                key: compute_inputs.get(
                    key, MetricInputRef(metric_key=key)
                ).model_dump()
                for key in definition.required_inputs
            },
            "formula_id": definition.formula_id,
            "formula_version": definition.formula_version,
            "numeric_finalization": finalization_trace,
        }
        | trace_fragments,
    )


def _finalize_and_project(
    definition: MetricDefinition,
    computation: MetricComputationResult,
) -> tuple[Decimal | None, float | None, dict]:
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
        return projection_ready.value, projected.value, evidence
    except _NUMERIC_FAILURE_TYPES as exc:
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
    from src.analysis.math.policies import MISSING_CONFIDENCE_PENALTY_FACTOR

    confidences = [
        item.confidence for item in trace_inputs if item.confidence is not None
    ]
    if not confidences:
        return None, {"missing_confidence_penalty_applied": False}
    derived_confidence = min(confidences)
    penalty_applied = len(confidences) < len(trace_inputs)
    if penalty_applied:
        derived_confidence = round(
            derived_confidence * MISSING_CONFIDENCE_PENALTY_FACTOR,
            4,
        )
    return derived_confidence, {
        "inputs_min": min(confidences),
        "missing_confidence_penalty_applied": penalty_applied,
        "missing_confidence_penalty_factor": (
            MISSING_CONFIDENCE_PENALTY_FACTOR if penalty_applied else 1.0
        ),
    }
