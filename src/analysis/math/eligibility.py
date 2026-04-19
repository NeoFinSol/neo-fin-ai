from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType
from typing import Mapping

from src.analysis.math import reason_codes as rc
from src.analysis.math.candidates import CandidateState, MetricCandidate
from src.analysis.math.refusals import (
    MetricRefusal,
    make_invalid_basis_refusal,
    make_missing_basis_refusal,
)
from src.analysis.math.registry import MetricDefinition

OPENING_AND_CLOSING_REQUIRED_POLICY_REF = "opening_and_closing_required"


class EligibilityStatus(str, Enum):
    ELIGIBLE = "ELIGIBLE"
    REFUSED = "REFUSED"


@dataclass(frozen=True, slots=True)
class EligibilityResult:
    status: EligibilityStatus
    policy_ref: str | None
    basis_candidates: tuple[MetricCandidate, ...]
    refusal: MetricRefusal | None
    trace_payload: Mapping[str, object]


def evaluate_eligibility(
    metric_definition: MetricDefinition,
    *,
    opening_candidate: MetricCandidate | None,
    closing_candidate: MetricCandidate | None,
) -> EligibilityResult:
    return validate_average_balance_basis(
        metric_definition,
        opening_candidate=opening_candidate,
        closing_candidate=closing_candidate,
    )


def validate_average_balance_basis(
    metric_definition: MetricDefinition,
    *,
    opening_candidate: MetricCandidate | None,
    closing_candidate: MetricCandidate | None,
) -> EligibilityResult:
    policy_ref = metric_definition.average_balance_policy_ref
    if policy_ref != OPENING_AND_CLOSING_REQUIRED_POLICY_REF:
        refusal = make_invalid_basis_refusal(
            metric_key=metric_definition.metric_id,
            reason_code=rc.COMPARATIVE_UNKNOWN_AVERAGE_BALANCE_POLICY,
            basis_detail=str(policy_ref),
        )
        return _refused_result(policy_ref=policy_ref, refusal=refusal)
    opening_refusal = _validate_opening_candidate(metric_definition, opening_candidate)
    if opening_refusal is not None:
        return _refused_result(policy_ref=policy_ref, refusal=opening_refusal)
    if closing_candidate is None:
        refusal = make_missing_basis_refusal(
            metric_key=metric_definition.metric_id,
            reason_code=rc.COMPARATIVE_MISSING_CLOSING_BALANCE,
            missing_basis="closing_balance",
        )
        return _refused_result(policy_ref=policy_ref, refusal=refusal)
    closing_refusal = _validate_closing_candidate(metric_definition, closing_candidate)
    if closing_refusal is not None:
        return _refused_result(policy_ref=policy_ref, refusal=closing_refusal)
    if opening_candidate.unit != closing_candidate.unit:
        refusal = make_invalid_basis_refusal(
            metric_key=metric_definition.metric_id,
            reason_code=rc.COMPARATIVE_INCOMPATIBLE_OPENING_BASIS,
            basis_detail="unit_mismatch",
        )
        return _refused_result(policy_ref=policy_ref, refusal=refusal)
    return _eligible_result(
        policy_ref=policy_ref,
        basis_candidates=(opening_candidate, closing_candidate),
    )


def _validate_opening_candidate(
    metric_definition: MetricDefinition,
    opening_candidate: MetricCandidate | None,
) -> MetricRefusal | None:
    if opening_candidate is None:
        return _missing_opening_refusal(metric_definition)
    if opening_candidate.candidate_state is CandidateState.READY:
        return None
    if opening_candidate.candidate_state is CandidateState.MISSING:
        return _missing_opening_refusal(metric_definition)
    return make_invalid_basis_refusal(
        metric_key=metric_definition.metric_id,
        reason_code=rc.COMPARATIVE_INCOMPATIBLE_OPENING_BASIS,
        basis_detail=opening_candidate.candidate_state.value,
    )


def _validate_closing_candidate(
    metric_definition: MetricDefinition,
    closing_candidate: MetricCandidate,
) -> MetricRefusal | None:
    if closing_candidate.candidate_state is CandidateState.READY:
        return None
    if closing_candidate.candidate_state is CandidateState.MISSING:
        return make_missing_basis_refusal(
            metric_key=metric_definition.metric_id,
            reason_code=rc.COMPARATIVE_MISSING_CLOSING_BALANCE,
            missing_basis="closing_balance",
        )
    return make_invalid_basis_refusal(
        metric_key=metric_definition.metric_id,
        reason_code=rc.COMPARATIVE_INCOMPATIBLE_CLOSING_BASIS,
        basis_detail=closing_candidate.candidate_state.value,
    )


def _missing_opening_refusal(
    metric_definition: MetricDefinition,
) -> MetricRefusal:
    return make_missing_basis_refusal(
        metric_key=metric_definition.metric_id,
        reason_code=rc.COMPARATIVE_MISSING_OPENING_BALANCE,
        missing_basis="opening_balance",
        extra_reason_codes=(rc.COMPARATIVE_FORBIDDEN_APPROXIMATION,),
    )


def _eligible_result(
    *,
    policy_ref: str | None,
    basis_candidates: tuple[MetricCandidate, ...],
) -> EligibilityResult:
    return EligibilityResult(
        status=EligibilityStatus.ELIGIBLE,
        policy_ref=policy_ref,
        basis_candidates=basis_candidates,
        refusal=None,
        trace_payload=MappingProxyType(
            {
                "status": EligibilityStatus.ELIGIBLE.value,
                "policy_ref": policy_ref,
                "basis_candidate_ids": tuple(
                    candidate.candidate_id for candidate in basis_candidates
                ),
            }
        ),
    )


def _refused_result(
    *,
    policy_ref: str | None,
    refusal: MetricRefusal,
) -> EligibilityResult:
    return EligibilityResult(
        status=EligibilityStatus.REFUSED,
        policy_ref=policy_ref,
        basis_candidates=(),
        refusal=refusal,
        trace_payload=MappingProxyType(
            {
                "status": EligibilityStatus.REFUSED.value,
                "policy_ref": policy_ref,
                "eligibility_refusal_candidate_reason_codes": refusal.reason_codes,
            }
        ),
    )
