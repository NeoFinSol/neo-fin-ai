from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType
from typing import Protocol

from src.analysis.math import reason_codes as rc
from src.analysis.math.candidates import (
    CandidateSourceKind,
    CandidateState,
    MetricCandidate,
)


class PrecedenceStatus(str, Enum):
    SELECTED = "SELECTED"
    NO_CANDIDATE = "NO_CANDIDATE"
    AMBIGUOUS = "AMBIGUOUS"


@dataclass(frozen=True, slots=True)
class PrecedenceChoice:
    status: PrecedenceStatus
    selected_candidate_id: str | None
    loser_candidate_ids: tuple[str, ...]
    reason_codes: tuple[str, ...]


class PrecedencePolicy(Protocol):
    def choose(
        self,
        candidates: tuple[MetricCandidate, ...],
    ) -> PrecedenceChoice: ...


class ReportedOverDerivedDefaultPolicy:
    def choose(self, candidates: tuple[MetricCandidate, ...]) -> PrecedenceChoice:
        ready_candidates = _ordered_ready_candidates(candidates)
        if not ready_candidates:
            return _no_candidate_choice()
        best_candidates = _best_priority_candidates(ready_candidates)
        if len(best_candidates) != 1:
            return _ambiguous_choice(best_candidates)
        winner = best_candidates[0]
        losers = tuple(
            candidate.candidate_id
            for candidate in ready_candidates
            if candidate.candidate_id != winner.candidate_id
        )
        return PrecedenceChoice(
            status=PrecedenceStatus.SELECTED,
            selected_candidate_id=winner.candidate_id,
            loser_candidate_ids=losers,
            reason_codes=(),
        )


PRECEDENCE_POLICIES = MappingProxyType(
    {
        "reported_over_derived_default": ReportedOverDerivedDefaultPolicy(),
        "reported_over_derived": ReportedOverDerivedDefaultPolicy(),
    }
)


def _ordered_ready_candidates(
    candidates: tuple[MetricCandidate, ...],
) -> tuple[MetricCandidate, ...]:
    ready = [
        candidate
        for candidate in candidates
        if candidate.candidate_state is CandidateState.READY
    ]
    return tuple(sorted(ready, key=_precedence_sort_key))


def _best_priority_candidates(
    candidates: tuple[MetricCandidate, ...],
) -> tuple[MetricCandidate, ...]:
    top_priority = _source_priority(candidates[0].source_kind)
    return tuple(
        candidate
        for candidate in candidates
        if _source_priority(candidate.source_kind) == top_priority
    )


def _precedence_sort_key(candidate: MetricCandidate) -> tuple[int, str]:
    return (_source_priority(candidate.source_kind), candidate.candidate_id)


def _source_priority(source_kind: CandidateSourceKind) -> int:
    priority_map = {
        CandidateSourceKind.REPORTED: 0,
        CandidateSourceKind.DERIVED: 1,
        CandidateSourceKind.SYNTHETIC: 2,
    }
    return priority_map[source_kind]


def _no_candidate_choice() -> PrecedenceChoice:
    return PrecedenceChoice(
        status=PrecedenceStatus.NO_CANDIDATE,
        selected_candidate_id=None,
        loser_candidate_ids=(),
        reason_codes=(rc.MATH_RESOLVER_NO_CANDIDATE,),
    )


def _ambiguous_choice(
    candidates: tuple[MetricCandidate, ...],
) -> PrecedenceChoice:
    return PrecedenceChoice(
        status=PrecedenceStatus.AMBIGUOUS,
        selected_candidate_id=None,
        loser_candidate_ids=tuple(candidate.candidate_id for candidate in candidates),
        reason_codes=(rc.MATH_RESOLVER_AMBIGUOUS_CANDIDATES,),
    )
