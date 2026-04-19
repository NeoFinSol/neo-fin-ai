from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from types import MappingProxyType
from typing import Mapping, Sequence

from src.analysis.math.contracts import MetricUnit
from src.analysis.math.provenance import CandidateProvenance
from src.analysis.math.synthetic_contract import (
    validate_synthetic_key,
    validate_synthetic_producer,
)
from src.analysis.math.trace_models import TraceSeed


class CandidateSourceKind(str, Enum):
    REPORTED = "reported"
    DERIVED = "derived"
    SYNTHETIC = "synthetic"


class CandidateState(str, Enum):
    READY = "READY"
    MISSING = "MISSING"
    INVALID = "INVALID"
    INELIGIBLE = "INELIGIBLE"


@dataclass(frozen=True, slots=True)
class MetricCandidate:
    candidate_id: str
    metric_key: str
    source_kind: CandidateSourceKind
    canonical_value: Decimal | None
    unit: MetricUnit
    candidate_state: CandidateState
    provenance: CandidateProvenance
    synthetic_key: str | None
    precedence_group: str | None
    trace_seed: TraceSeed


@dataclass(frozen=True, slots=True)
class CandidateSet:
    candidates_by_metric: Mapping[str, tuple[MetricCandidate, ...]]


def build_candidate_set(candidates: Sequence[MetricCandidate]) -> CandidateSet:
    grouped: dict[str, list[MetricCandidate]] = defaultdict(list)
    for candidate in candidates:
        grouped[candidate.metric_key].append(candidate)

    ordered_groups = {
        metric_key: tuple(sorted(metric_candidates, key=_candidate_sort_key))
        for metric_key, metric_candidates in sorted(grouped.items())
    }
    return CandidateSet(candidates_by_metric=MappingProxyType(ordered_groups))


def build_synthetic_candidate(
    *,
    metric_key: str,
    formula_id: str | None,
    synthetic_key: str,
    canonical_value: Decimal | None,
    unit: MetricUnit,
    producer: str,
    source_inputs: tuple[str, ...] = (),
    source_metric_keys: tuple[str, ...] = (),
    source_refs: tuple[str, ...] = (),
    period_ref: str | None = None,
    derivation_mode: str | None = None,
    extractor_source_ref: str | None = None,
    resolver_id: str | None = None,
    precedence_group: str | None = None,
    candidate_state: CandidateState = CandidateState.READY,
    formula_version: str | None = None,
) -> MetricCandidate:
    validate_synthetic_key(synthetic_key)
    validate_synthetic_producer(producer)
    return MetricCandidate(
        candidate_id=_build_candidate_id(
            metric_key=metric_key,
            source_kind=CandidateSourceKind.SYNTHETIC,
            producer=producer,
            suffix=synthetic_key,
        ),
        metric_key=metric_key,
        source_kind=CandidateSourceKind.SYNTHETIC,
        canonical_value=canonical_value,
        unit=unit,
        candidate_state=candidate_state,
        provenance=_build_provenance(
            producer=producer,
            source_inputs=source_inputs,
            derivation_mode=derivation_mode,
            source_metric_keys=source_metric_keys,
            period_ref=period_ref,
            extractor_source_ref=extractor_source_ref,
            resolver_id=resolver_id,
        ),
        synthetic_key=synthetic_key,
        precedence_group=precedence_group,
        trace_seed=_build_trace_seed(
            metric_key=metric_key,
            formula_id=formula_id,
            source_refs=source_refs,
            period_ref=period_ref,
            formula_version=formula_version,
        ),
    )


def build_reported_candidate(
    *,
    metric_key: str,
    formula_id: str | None,
    canonical_value: Decimal | None,
    unit: MetricUnit,
    producer: str,
    source_inputs: tuple[str, ...] = (),
    source_metric_keys: tuple[str, ...] = (),
    source_refs: tuple[str, ...] = (),
    period_ref: str | None = None,
    derivation_mode: str | None = None,
    extractor_source_ref: str | None = None,
    resolver_id: str | None = None,
    precedence_group: str | None = None,
    candidate_state: CandidateState = CandidateState.READY,
    formula_version: str | None = None,
) -> MetricCandidate:
    return MetricCandidate(
        candidate_id=_build_candidate_id(
            metric_key=metric_key,
            source_kind=CandidateSourceKind.REPORTED,
            producer=producer,
            suffix=extractor_source_ref,
        ),
        metric_key=metric_key,
        source_kind=CandidateSourceKind.REPORTED,
        canonical_value=canonical_value,
        unit=unit,
        candidate_state=candidate_state,
        provenance=_build_provenance(
            producer=producer,
            source_inputs=source_inputs,
            derivation_mode=derivation_mode,
            source_metric_keys=source_metric_keys,
            period_ref=period_ref,
            extractor_source_ref=extractor_source_ref,
            resolver_id=resolver_id,
        ),
        synthetic_key=None,
        precedence_group=precedence_group,
        trace_seed=_build_trace_seed(
            metric_key=metric_key,
            formula_id=formula_id,
            source_refs=source_refs,
            period_ref=period_ref,
            formula_version=formula_version,
        ),
    )


def build_derived_candidate(
    *,
    metric_key: str,
    formula_id: str | None,
    canonical_value: Decimal | None,
    unit: MetricUnit,
    producer: str,
    source_inputs: tuple[str, ...] = (),
    source_metric_keys: tuple[str, ...] = (),
    source_refs: tuple[str, ...] = (),
    period_ref: str | None = None,
    derivation_mode: str | None = None,
    extractor_source_ref: str | None = None,
    resolver_id: str | None = None,
    precedence_group: str | None = None,
    candidate_state: CandidateState = CandidateState.READY,
    formula_version: str | None = None,
) -> MetricCandidate:
    return MetricCandidate(
        candidate_id=_build_candidate_id(
            metric_key=metric_key,
            source_kind=CandidateSourceKind.DERIVED,
            producer=producer,
            suffix=derivation_mode,
        ),
        metric_key=metric_key,
        source_kind=CandidateSourceKind.DERIVED,
        canonical_value=canonical_value,
        unit=unit,
        candidate_state=candidate_state,
        provenance=_build_provenance(
            producer=producer,
            source_inputs=source_inputs,
            derivation_mode=derivation_mode,
            source_metric_keys=source_metric_keys,
            period_ref=period_ref,
            extractor_source_ref=extractor_source_ref,
            resolver_id=resolver_id,
        ),
        synthetic_key=None,
        precedence_group=precedence_group,
        trace_seed=_build_trace_seed(
            metric_key=metric_key,
            formula_id=formula_id,
            source_refs=source_refs,
            period_ref=period_ref,
            formula_version=formula_version,
        ),
    )


def _build_candidate_id(
    *,
    metric_key: str,
    source_kind: CandidateSourceKind,
    producer: str,
    suffix: str | None,
) -> str:
    candidate_suffix = suffix or "default"
    return f"{metric_key}:{source_kind.value}:{producer}:{candidate_suffix}"


def _build_provenance(
    *,
    producer: str,
    source_inputs: tuple[str, ...],
    derivation_mode: str | None,
    source_metric_keys: tuple[str, ...],
    period_ref: str | None,
    extractor_source_ref: str | None,
    resolver_id: str | None,
) -> CandidateProvenance:
    return CandidateProvenance(
        producer=producer,
        source_inputs=source_inputs,
        derivation_mode=derivation_mode,
        source_metric_keys=source_metric_keys,
        source_period_ref=period_ref,
        extractor_source_ref=extractor_source_ref,
        resolver_id=resolver_id,
    )


def _build_trace_seed(
    *,
    metric_key: str,
    formula_id: str | None,
    source_refs: tuple[str, ...],
    period_ref: str | None,
    formula_version: str | None = None,
) -> TraceSeed:
    return TraceSeed(
        metric_key=metric_key,
        formula_id=formula_id,
        source_refs=source_refs,
        period_ref=period_ref,
        formula_version=formula_version,
    )


def _candidate_sort_key(candidate: MetricCandidate) -> tuple[str, str, str, str, str]:
    return (
        candidate.metric_key,
        candidate.source_kind.value,
        candidate.precedence_group or "",
        candidate.synthetic_key or "",
        candidate.candidate_id,
    )
