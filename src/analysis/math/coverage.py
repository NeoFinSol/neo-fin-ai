from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from src.analysis.math.candidates import CandidateSourceKind, MetricCandidate
from src.analysis.math.contracts import ValidityState
from src.analysis.math.refusals import MetricRefusal, make_coverage_refusal
from src.analysis.math.registry import MetricCoverageClass, MetricDefinition
from src.analysis.math.resolver_reason_codes import (
    WAVE3_REASON_APPROXIMATION_SEMANTICS_REQUIRED,
    WAVE3_REASON_COVERAGE_SUPPRESSED,
    WAVE3_REASON_OUT_OF_SCOPE_OUTWARD_REFUSAL,
    WAVE3_REASON_REPORTED_CANDIDATE_REQUIRED,
)


class CoverageComputeMode(str, Enum):
    ALLOW = "ALLOW"
    BLOCK = "BLOCK"


class CoverageEmitMode(str, Enum):
    ALLOW = "ALLOW"
    FORBID = "FORBID"


@dataclass(frozen=True, slots=True)
class CoverageGateResult:
    compute_mode: CoverageComputeMode
    emit_mode: CoverageEmitMode
    refusal: MetricRefusal | None
    final_validity_state: ValidityState | None
    approximation_required: bool


def enforce_coverage(
    metric_definition: MetricDefinition,
    *,
    selected_candidate: MetricCandidate | None = None,
    approximation_semantics: bool = False,
) -> CoverageGateResult:
    coverage_class = metric_definition.coverage_class
    if coverage_class is MetricCoverageClass.FULLY_SUPPORTED:
        return _allow_result(approximation_required=False)
    if coverage_class is MetricCoverageClass.REPORTED_ONLY:
        return _handle_reported_only(metric_definition, selected_candidate)
    if coverage_class is MetricCoverageClass.DERIVED_FORMULA:
        return _handle_derived_formula(metric_definition, selected_candidate)
    if coverage_class is MetricCoverageClass.APPROXIMATE_ONLY:
        return _handle_approximate_only(metric_definition, approximation_semantics)
    if coverage_class is MetricCoverageClass.INTENTIONALLY_SUPPRESSED:
        return _blocked_result(
            metric_definition,
            WAVE3_REASON_COVERAGE_SUPPRESSED,
            ValidityState.SUPPRESSED,
        )
    return _blocked_result(
        metric_definition,
        WAVE3_REASON_OUT_OF_SCOPE_OUTWARD_REFUSAL,
        ValidityState.NOT_APPLICABLE,
    )


def _handle_reported_only(
    metric_definition: MetricDefinition,
    selected_candidate: MetricCandidate | None,
) -> CoverageGateResult:
    if selected_candidate is None:
        return _allow_result(approximation_required=False)
    if selected_candidate.source_kind is CandidateSourceKind.REPORTED:
        return _allow_result(approximation_required=False)
    return _blocked_result(
        metric_definition,
        WAVE3_REASON_REPORTED_CANDIDATE_REQUIRED,
        ValidityState.INVALID,
    )


def _handle_derived_formula(
    metric_definition: MetricDefinition,
    selected_candidate: MetricCandidate | None,
) -> CoverageGateResult:
    if selected_candidate is None:
        return _allow_result(approximation_required=False)
    if selected_candidate.source_kind is CandidateSourceKind.REPORTED:
        return _blocked_result(
            metric_definition,
            WAVE3_REASON_REPORTED_CANDIDATE_REQUIRED,
            ValidityState.INVALID,
        )
    return _allow_result(approximation_required=False)


def _handle_approximate_only(
    metric_definition: MetricDefinition,
    approximation_semantics: bool,
) -> CoverageGateResult:
    if approximation_semantics:
        return _allow_result(approximation_required=True)
    return _blocked_result(
        metric_definition,
        WAVE3_REASON_APPROXIMATION_SEMANTICS_REQUIRED,
        ValidityState.INVALID,
    )


def _allow_result(*, approximation_required: bool) -> CoverageGateResult:
    return CoverageGateResult(
        compute_mode=CoverageComputeMode.ALLOW,
        emit_mode=CoverageEmitMode.ALLOW,
        refusal=None,
        final_validity_state=ValidityState.VALID,
        approximation_required=approximation_required,
    )


def _blocked_result(
    metric_definition: MetricDefinition,
    reason_code: str,
    validity_state: ValidityState,
) -> CoverageGateResult:
    return CoverageGateResult(
        compute_mode=CoverageComputeMode.BLOCK,
        emit_mode=CoverageEmitMode.FORBID,
        refusal=make_coverage_refusal(
            metric_key=metric_definition.metric_id,
            reason_code=reason_code,
            coverage_class=metric_definition.coverage_class.value,
        ),
        final_validity_state=validity_state,
        approximation_required=False,
    )
