from __future__ import annotations

from types import MappingProxyType

from src.analysis.math.candidates import MetricCandidate
from src.analysis.math.precedence import PrecedenceChoice, PrecedenceStatus
from src.analysis.math.refusals import (
    MetricRefusal,
    make_ambiguity_refusal,
    make_no_candidate_refusal,
)
from src.analysis.math.resolver_engine import (
    ResolverConfigurationError,
    ResolverContext,
    ResolverDecision,
    ResolverStatus,
)
from src.analysis.math.trace_builders import build_resolver_trace


def choose_by_precedence(context: ResolverContext) -> PrecedenceChoice:
    policy = context.precedence_policy
    if policy is None:
        raise ResolverConfigurationError(
            f"resolver '{context.resolver_slot}' requires precedence_policy_ref"
        )
    return policy.choose(context.candidates)


def find_candidate(context: ResolverContext, candidate_id: str) -> MetricCandidate:
    for candidate in context.candidates:
        if candidate.candidate_id == candidate_id:
            return candidate
    raise ResolverConfigurationError(f"candidate '{candidate_id}' not found")


def resolved_decision(
    *,
    context: ResolverContext,
    selected: MetricCandidate,
    loser_ids: tuple[str, ...],
    resolver_family: str,
    selected_basis: str,
    extra_trace: dict[str, object] | None = None,
) -> ResolverDecision:
    trace = _build_trace(
        context=context,
        status=ResolverStatus.RESOLVED,
        selected_candidate_id=selected.candidate_id,
        loser_candidate_ids=loser_ids,
        reason_codes=(),
        resolver_family=resolver_family,
        extra_trace={"selected_basis": selected_basis} | (extra_trace or {}),
    )
    return ResolverDecision(
        status=ResolverStatus.RESOLVED,
        selected_candidate_id=selected.candidate_id,
        loser_candidate_ids=loser_ids,
        refusal=None,
        trace_payload=MappingProxyType(trace),
    )


def no_candidate_decision(
    *,
    context: ResolverContext,
    resolver_family: str,
    extra_trace: dict[str, object] | None = None,
) -> ResolverDecision:
    refusal = make_no_candidate_refusal(metric_key=context.metric_definition.metric_id)
    return refused_decision(
        context=context,
        refusal=refusal,
        resolver_family=resolver_family,
        extra_trace=extra_trace,
    )


def ambiguous_decision(
    *,
    context: ResolverContext,
    candidate_ids: tuple[str, ...],
    resolver_family: str,
    refusal: MetricRefusal | None = None,
    extra_trace: dict[str, object] | None = None,
) -> ResolverDecision:
    actual_refusal = refusal or make_ambiguity_refusal(
        metric_key=context.metric_definition.metric_id,
        candidate_ids=candidate_ids,
    )
    trace = _build_trace(
        context=context,
        status=ResolverStatus.AMBIGUOUS,
        selected_candidate_id=None,
        loser_candidate_ids=candidate_ids,
        reason_codes=actual_refusal.reason_codes,
        resolver_family=resolver_family,
        extra_trace=extra_trace or {},
    )
    return ResolverDecision(
        status=ResolverStatus.AMBIGUOUS,
        selected_candidate_id=None,
        loser_candidate_ids=candidate_ids,
        refusal=actual_refusal,
        trace_payload=MappingProxyType(trace),
    )


def refused_decision(
    *,
    context: ResolverContext,
    refusal: MetricRefusal,
    resolver_family: str,
    loser_candidate_ids: tuple[str, ...] = (),
    extra_trace: dict[str, object] | None = None,
) -> ResolverDecision:
    trace = _build_trace(
        context=context,
        status=ResolverStatus.REFUSED,
        selected_candidate_id=None,
        loser_candidate_ids=loser_candidate_ids,
        reason_codes=refusal.reason_codes,
        resolver_family=resolver_family,
        extra_trace=extra_trace or {},
    )
    return ResolverDecision(
        status=ResolverStatus.REFUSED,
        selected_candidate_id=None,
        loser_candidate_ids=loser_candidate_ids,
        refusal=refusal,
        trace_payload=MappingProxyType(trace),
    )


def decision_from_choice(
    *,
    context: ResolverContext,
    choice: PrecedenceChoice,
    resolver_family: str,
    selected_basis: str,
    extra_trace: dict[str, object] | None = None,
) -> ResolverDecision:
    if choice.status is PrecedenceStatus.NO_CANDIDATE:
        return no_candidate_decision(
            context=context,
            resolver_family=resolver_family,
            extra_trace=extra_trace,
        )
    if choice.status is PrecedenceStatus.AMBIGUOUS:
        return ambiguous_decision(
            context=context,
            candidate_ids=choice.loser_candidate_ids,
            resolver_family=resolver_family,
            extra_trace=extra_trace,
        )
    selected = find_candidate(context, choice.selected_candidate_id or "")
    return resolved_decision(
        context=context,
        selected=selected,
        loser_ids=choice.loser_candidate_ids,
        resolver_family=resolver_family,
        selected_basis=selected_basis,
        extra_trace=extra_trace,
    )


def _build_trace(
    *,
    context: ResolverContext,
    status: ResolverStatus,
    selected_candidate_id: str | None,
    loser_candidate_ids: tuple[str, ...],
    reason_codes: tuple[str, ...],
    resolver_family: str,
    extra_trace: dict[str, object],
) -> dict[str, object]:
    base_trace = build_resolver_trace(
        metric_key=context.metric_definition.metric_id,
        resolver_slot=context.resolver_slot,
        precedence_policy_ref=context.precedence_policy_ref,
        selected_candidate_id=selected_candidate_id,
        loser_candidate_ids=loser_candidate_ids,
        status=status.value,
        candidate_reason_codes=reason_codes,
    )
    return base_trace | {"resolver_family": resolver_family} | extra_trace
