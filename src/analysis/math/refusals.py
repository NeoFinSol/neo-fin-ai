from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType
from typing import Mapping

from src.analysis.math import reason_codes as rc


class RefusalStage(str, Enum):
    PRECOMPUTE = "precompute"
    RESOLVER = "resolver"
    COVERAGE = "coverage"
    ELIGIBILITY = "eligibility"
    COMPUTE = "compute"
    VALIDATION = "validation"


@dataclass(frozen=True, slots=True)
class MetricRefusal:
    stage: RefusalStage
    reason_codes: tuple[str, ...]
    details: Mapping[str, object]


def make_ambiguity_refusal(
    *, metric_key: str, candidate_ids: tuple[str, ...]
) -> MetricRefusal:
    return _build_refusal(
        stage=RefusalStage.RESOLVER,
        reason_codes=(rc.MATH_RESOLVER_AMBIGUOUS_CANDIDATES,),
        details={"metric_key": metric_key, "candidate_ids": candidate_ids},
    )


def make_no_candidate_refusal(*, metric_key: str) -> MetricRefusal:
    return _build_refusal(
        stage=RefusalStage.RESOLVER,
        reason_codes=(rc.MATH_RESOLVER_NO_CANDIDATE,),
        details={"metric_key": metric_key},
    )


def make_missing_basis_refusal(
    *,
    metric_key: str,
    reason_code: str,
    missing_basis: str,
    extra_reason_codes: tuple[str, ...] = (),
) -> MetricRefusal:
    return _build_refusal(
        stage=RefusalStage.ELIGIBILITY,
        reason_codes=(reason_code,) + extra_reason_codes,
        details={"metric_key": metric_key, "missing_basis": missing_basis},
    )


def make_invalid_basis_refusal(
    *,
    metric_key: str,
    reason_code: str,
    basis_detail: str,
) -> MetricRefusal:
    return _build_refusal(
        stage=RefusalStage.ELIGIBILITY,
        reason_codes=(reason_code,),
        details={"metric_key": metric_key, "basis_detail": basis_detail},
    )


def make_coverage_refusal(
    *,
    metric_key: str,
    reason_code: str,
    coverage_class: str,
) -> MetricRefusal:
    return _build_refusal(
        stage=RefusalStage.COVERAGE,
        reason_codes=(reason_code,),
        details={"metric_key": metric_key, "coverage_class": coverage_class},
    )


def make_resolver_refusal(
    *,
    metric_key: str,
    reason_code: str,
    details: dict[str, object],
) -> MetricRefusal:
    refusal_details = {"metric_key": metric_key} | details
    return _build_refusal(
        stage=RefusalStage.RESOLVER,
        reason_codes=(reason_code,),
        details=refusal_details,
    )


def _build_refusal(
    *,
    stage: RefusalStage,
    reason_codes: tuple[str, ...],
    details: dict[str, object],
) -> MetricRefusal:
    return MetricRefusal(
        stage=stage,
        reason_codes=reason_codes,
        details=MappingProxyType(dict(details)),
    )
