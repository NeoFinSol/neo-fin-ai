from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import Mapping, Protocol, runtime_checkable

from src.analysis.math.candidates import CandidateSet, MetricCandidate
from src.analysis.math.precedence import PRECEDENCE_POLICIES, PrecedencePolicy
from src.analysis.math.refusals import MetricRefusal
from src.analysis.math.registry import MetricDefinition


class ResolverConfigurationError(ValueError):
    """Raised when resolver framework configuration is incomplete."""


class ResolverDecisionValidationError(ValueError):
    """Raised when a resolver returns an invalid decision contract."""


class ResolverStatus(str, Enum):
    RESOLVED = "RESOLVED"
    AMBIGUOUS = "AMBIGUOUS"
    REFUSED = "REFUSED"


@dataclass(frozen=True, slots=True)
class ResolverContext:
    metric_definition: MetricDefinition
    resolver_slot: str
    candidates: tuple[MetricCandidate, ...]
    precedence_policy_ref: str | None
    precedence_policy: PrecedencePolicy | None


@dataclass(frozen=True, slots=True)
class ResolverDecision:
    status: ResolverStatus
    selected_candidate_id: str | None
    loser_candidate_ids: tuple[str, ...]
    refusal: MetricRefusal | None
    trace_payload: Mapping[str, object] = field(
        default_factory=lambda: MappingProxyType({})
    )


@runtime_checkable
class ResolverHandler(Protocol):
    def resolve(self, context: ResolverContext) -> ResolverDecision: ...


def resolve_metric_family(
    metric_definition: MetricDefinition,
    candidate_set: CandidateSet,
) -> ResolverDecision:
    resolver_slot = _require_resolver_slot(metric_definition)
    context = ResolverContext(
        metric_definition=metric_definition,
        resolver_slot=resolver_slot,
        candidates=_get_family_candidates(metric_definition, candidate_set),
        precedence_policy_ref=metric_definition.precedence_policy_ref,
        precedence_policy=_resolve_precedence_policy(metric_definition),
    )
    decision = _resolve_with_handler(resolver_slot, context)
    return _validate_resolver_decision(metric_definition, candidate_set, decision)


def collect_resolver_framework_errors(
    metric_definition: MetricDefinition,
) -> tuple[str, ...]:
    errors = []
    if (
        metric_definition.precedence_policy_ref
        and metric_definition.resolver_slot is None
    ):
        errors.append("precedence_policy_ref requires resolver_slot")
    if (
        metric_definition.resolver_slot
        and metric_definition.precedence_policy_ref is None
    ):
        errors.append("resolver_slot requires precedence_policy_ref")
    return tuple(errors)


def _require_resolver_slot(metric_definition: MetricDefinition) -> str:
    resolver_slot = metric_definition.resolver_slot
    if resolver_slot is None:
        raise ResolverConfigurationError(
            f"metric '{metric_definition.metric_id}' does not declare resolver_slot"
        )
    return resolver_slot


def _get_family_candidates(
    metric_definition: MetricDefinition,
    candidate_set: CandidateSet,
) -> tuple[MetricCandidate, ...]:
    return candidate_set.candidates_by_metric.get(metric_definition.metric_id, ())


def _resolve_precedence_policy(
    metric_definition: MetricDefinition,
) -> PrecedencePolicy | None:
    policy_ref = metric_definition.precedence_policy_ref
    if policy_ref is None:
        return None
    policy = PRECEDENCE_POLICIES.get(policy_ref)
    if policy is None:
        raise ResolverConfigurationError(f"unknown precedence policy: {policy_ref}")
    return policy


def _resolve_with_handler(
    resolver_slot: str,
    context: ResolverContext,
) -> ResolverDecision:
    from src.analysis.math.resolver_registry import get_resolver_handler

    handler = get_resolver_handler(resolver_slot)
    if not isinstance(handler, ResolverHandler):
        raise ResolverConfigurationError(
            f"resolver handler for slot '{resolver_slot}' does not implement resolve()"
        )
    decision = handler.resolve(context)
    if not isinstance(decision, ResolverDecision):
        raise ResolverDecisionValidationError(
            "Resolver handler returned non-ResolverDecision output"
        )
    return decision


def _validate_resolver_decision(
    metric_definition: MetricDefinition,
    candidate_set: CandidateSet,
    decision: ResolverDecision,
) -> ResolverDecision:
    candidate_index = _build_candidate_index(candidate_set)
    _validate_status_requirements(decision)
    _validate_selected_candidate(metric_definition, candidate_index, decision)
    _validate_loser_candidates(metric_definition, candidate_index, decision)
    return decision


def _build_candidate_index(
    candidate_set: CandidateSet,
) -> dict[str, MetricCandidate]:
    return {
        candidate.candidate_id: candidate
        for family in candidate_set.candidates_by_metric.values()
        for candidate in family
    }


def _validate_status_requirements(decision: ResolverDecision) -> None:
    if (
        decision.status is ResolverStatus.RESOLVED
        and decision.selected_candidate_id is None
    ):
        raise ResolverDecisionValidationError(
            "RESOLVED decision requires selected_candidate_id"
        )
    if decision.status is ResolverStatus.AMBIGUOUS and decision.refusal is None:
        raise ResolverDecisionValidationError("AMBIGUOUS decision requires refusal")
    if decision.status is ResolverStatus.REFUSED and decision.refusal is None:
        raise ResolverDecisionValidationError("REFUSED decision requires refusal")


def _validate_selected_candidate(
    metric_definition: MetricDefinition,
    candidate_index: dict[str, MetricCandidate],
    decision: ResolverDecision,
) -> None:
    selected_id = decision.selected_candidate_id
    if selected_id is None:
        return
    candidate = candidate_index.get(selected_id)
    if candidate is None:
        raise ResolverDecisionValidationError("selected candidate does not exist")
    if candidate.metric_key != metric_definition.metric_id:
        raise ResolverDecisionValidationError(
            "selected candidate must belong to metric family"
        )


def _validate_loser_candidates(
    metric_definition: MetricDefinition,
    candidate_index: dict[str, MetricCandidate],
    decision: ResolverDecision,
) -> None:
    for loser_id in decision.loser_candidate_ids:
        candidate = candidate_index.get(loser_id)
        if candidate is None:
            raise ResolverDecisionValidationError("loser candidate does not exist")
        if candidate.metric_key != metric_definition.metric_id:
            raise ResolverDecisionValidationError(
                "loser candidate must belong to metric family"
            )
