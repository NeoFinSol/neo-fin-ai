from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType
from typing import Mapping

from src.analysis.math.candidates import MetricCandidate
from src.analysis.math.eligibility import EligibilityResult, EligibilityStatus
from src.analysis.math.refusals import MetricRefusal, make_no_candidate_refusal
from src.analysis.math.registry import MetricDefinition


class ComputeBasisStatus(str, Enum):
    READY = "READY"
    REFUSED = "REFUSED"


@dataclass(frozen=True, slots=True)
class ComputeBasis:
    status: ComputeBasisStatus
    metric_key: str
    formula_id: str
    selected_candidates: tuple[MetricCandidate, ...]
    refusal: MetricRefusal | None
    approximation_semantics: bool
    trace_payload: Mapping[str, object]


def materialize_compute_basis(
    metric_definition: MetricDefinition,
    *,
    selected_candidate: MetricCandidate | None = None,
    selected_candidates: tuple[MetricCandidate, ...] | None = None,
    eligibility_result: EligibilityResult | None = None,
    approximation_semantics: bool = False,
) -> ComputeBasis:
    if eligibility_result is not None:
        return _from_eligibility(
            metric_definition,
            eligibility_result,
            selected_candidates=selected_candidates,
            approximation_semantics=approximation_semantics,
        )
    if selected_candidates is not None:
        return _ready_basis(
            metric_definition=metric_definition,
            selected_candidates=selected_candidates,
            approximation_semantics=approximation_semantics,
        )
    if selected_candidate is not None:
        return _ready_basis(
            metric_definition=metric_definition,
            selected_candidates=(selected_candidate,),
            approximation_semantics=approximation_semantics,
        )
    refusal = make_no_candidate_refusal(metric_key=metric_definition.metric_id)
    return _refused_basis(metric_definition=metric_definition, refusal=refusal)


def _from_eligibility(
    metric_definition: MetricDefinition,
    eligibility_result: EligibilityResult,
    *,
    selected_candidates: tuple[MetricCandidate, ...] | None,
    approximation_semantics: bool,
) -> ComputeBasis:
    if eligibility_result.status is EligibilityStatus.REFUSED:
        return _refused_basis(
            metric_definition=metric_definition,
            refusal=eligibility_result.refusal,
        )
    if selected_candidates is not None:
        return _ready_basis(
            metric_definition=metric_definition,
            selected_candidates=selected_candidates,
            approximation_semantics=approximation_semantics,
        )
    return _ready_basis(
        metric_definition=metric_definition,
        selected_candidates=eligibility_result.basis_candidates,
        approximation_semantics=approximation_semantics,
    )


def _ready_basis(
    *,
    metric_definition: MetricDefinition,
    selected_candidates: tuple[MetricCandidate, ...],
    approximation_semantics: bool,
) -> ComputeBasis:
    return ComputeBasis(
        status=ComputeBasisStatus.READY,
        metric_key=metric_definition.metric_id,
        formula_id=metric_definition.formula_id,
        selected_candidates=selected_candidates,
        refusal=None,
        approximation_semantics=approximation_semantics,
        trace_payload=MappingProxyType(
            {
                "status": ComputeBasisStatus.READY.value,
                "candidate_ids": tuple(
                    candidate.candidate_id for candidate in selected_candidates
                ),
            }
        ),
    )


def _refused_basis(
    *,
    metric_definition: MetricDefinition,
    refusal: MetricRefusal | None,
) -> ComputeBasis:
    refusal_reason_codes = () if refusal is None else refusal.reason_codes
    return ComputeBasis(
        status=ComputeBasisStatus.REFUSED,
        metric_key=metric_definition.metric_id,
        formula_id=metric_definition.formula_id,
        selected_candidates=(),
        refusal=refusal,
        approximation_semantics=False,
        trace_payload=MappingProxyType(
            {
                "status": ComputeBasisStatus.REFUSED.value,
                "refusal_candidate_reason_codes": refusal_reason_codes,
            }
        ),
    )
