from __future__ import annotations

from src.analysis.math import reason_codes as rc
from src.analysis.math.candidates import CandidateState, MetricCandidate
from src.analysis.math.precedence import PrecedenceChoice, PrecedenceStatus
from src.analysis.math.refusals import make_resolver_refusal
from src.analysis.math.resolver_engine import ResolverContext, ResolverDecision
from src.analysis.math.resolvers.common import (
    ambiguous_decision,
    choose_by_precedence,
    no_candidate_decision,
    refused_decision,
    resolved_decision,
)

_DEBT_ONLY = "debt_only"
_LIABILITIES_TOTAL = "liabilities_total"
_LEASE_LIABILITIES = "lease_liabilities"
_BASIS_KINDS = (_DEBT_ONLY, _LIABILITIES_TOTAL, _LEASE_LIABILITIES)


class DebtBasisResolver:
    def resolve(self, context: ResolverContext) -> ResolverDecision:
        grouped = _group_by_basis(context.candidates)
        lease_bucket = grouped.get(_LEASE_LIABILITIES, ())
        if lease_bucket and any(
            c.candidate_state is CandidateState.READY for c in lease_bucket
        ):
            return _lease_refusal(context, grouped)
        winners = _basis_winners(context, grouped)
        if winners is None:
            return no_candidate_decision(context=context, resolver_family="debt_basis")
        if isinstance(winners, ResolverDecision):
            return winners
        return _resolve_winner(context, winners)


def _group_by_basis(
    candidates: tuple[MetricCandidate, ...],
) -> dict[str, tuple[MetricCandidate, ...]]:
    grouped = {basis: [] for basis in _BASIS_KINDS}
    for candidate in candidates:
        basis_kind = _basis_kind(candidate)
        if basis_kind is None:
            continue
        grouped[basis_kind].append(candidate)
    return {basis: tuple(items) for basis, items in grouped.items() if items}


def _basis_kind(candidate: MetricCandidate) -> str | None:
    if candidate.precedence_group in _BASIS_KINDS:
        return candidate.precedence_group
    tokens = set(
        candidate.provenance.source_metric_keys + candidate.provenance.source_inputs
    )
    if candidate.synthetic_key == "total_debt" or "total_debt" in tokens:
        return _DEBT_ONLY
    if "lease_liabilities" in tokens:
        return _LEASE_LIABILITIES
    if any("liabilit" in token for token in tokens):
        return _LIABILITIES_TOTAL
    return None


def _basis_winners(
    context: ResolverContext,
    grouped: dict[str, tuple[MetricCandidate, ...]],
) -> dict[str, tuple[MetricCandidate, PrecedenceChoice]] | ResolverDecision | None:
    winners: dict[str, tuple[MetricCandidate, PrecedenceChoice]] = {}
    for basis_kind in (_DEBT_ONLY, _LIABILITIES_TOTAL):
        choice = _choose_basis(context, grouped.get(basis_kind, ()))
        if choice is None:
            continue
        if isinstance(choice, ResolverDecision):
            return choice
        selected = _find_candidate(
            grouped[basis_kind], choice.selected_candidate_id or ""
        )
        winners[basis_kind] = (selected, choice)
    if not winners:
        return None
    return winners


def _choose_basis(
    context: ResolverContext,
    candidates: tuple[MetricCandidate, ...],
) -> PrecedenceChoice | ResolverDecision | None:
    if not candidates:
        return None
    choice = choose_by_precedence(_basis_context(context, candidates))
    if choice.status is PrecedenceStatus.AMBIGUOUS:
        return ambiguous_decision(
            context=context,
            candidate_ids=choice.loser_candidate_ids,
            resolver_family="debt_basis",
            extra_trace={"basis_kinds": _basis_names(candidates)},
        )
    if choice.status is PrecedenceStatus.NO_CANDIDATE:
        return None
    return choice


def _basis_context(
    context: ResolverContext,
    candidates: tuple[MetricCandidate, ...],
) -> ResolverContext:
    return ResolverContext(
        metric_definition=context.metric_definition,
        resolver_slot=context.resolver_slot,
        candidates=candidates,
        precedence_policy_ref=context.precedence_policy_ref,
        precedence_policy=context.precedence_policy,
    )


def _resolve_winner(
    context: ResolverContext,
    winners: dict[str, tuple[MetricCandidate, PrecedenceChoice]],
) -> ResolverDecision:
    expected = _expected_basis(context.metric_definition.metric_id)
    winner_kinds = tuple(sorted(winners))
    if len(winner_kinds) > 1:
        return _mixed_basis_ambiguity(context, winner_kinds, winners)
    selected_basis = winner_kinds[0]
    if selected_basis not in expected:
        return _invalid_basis_refusal(context, winner_kinds, winners)
    selected, choice = winners[selected_basis]
    return resolved_decision(
        context=context,
        selected=selected,
        loser_ids=choice.loser_candidate_ids,
        resolver_family="debt_basis",
        selected_basis=selected_basis,
        extra_trace={"expected_basis_kinds": expected},
    )


def _expected_basis(metric_id: str) -> tuple[str, ...]:
    if metric_id == "financial_leverage_debt_only":
        return (_DEBT_ONLY,)
    if metric_id == "financial_leverage_total":
        return (_LIABILITIES_TOTAL,)
    return (_DEBT_ONLY, _LIABILITIES_TOTAL)


def _mixed_basis_ambiguity(
    context: ResolverContext,
    winner_kinds: tuple[str, ...],
    winners: dict[str, tuple[MetricCandidate, PrecedenceChoice]],
) -> ResolverDecision:
    refusal = make_resolver_refusal(
        metric_key=context.metric_definition.metric_id,
        reason_code=rc.MATH_DEBT_MIXED_BASIS,
        details={"basis_kinds": winner_kinds},
    )
    candidate_ids = tuple(
        candidate.candidate_id for candidate, _choice in winners.values()
    )
    return ambiguous_decision(
        context=context,
        candidate_ids=candidate_ids,
        resolver_family="debt_basis",
        refusal=refusal,
        extra_trace={"basis_kinds": winner_kinds},
    )


def _invalid_basis_refusal(
    context: ResolverContext,
    winner_kinds: tuple[str, ...],
    winners: dict[str, tuple[MetricCandidate, PrecedenceChoice]],
) -> ResolverDecision:
    refusal = make_resolver_refusal(
        metric_key=context.metric_definition.metric_id,
        reason_code=rc.MATH_INVALID_BASIS,
        details={"basis_kinds": winner_kinds},
    )
    candidate_ids = tuple(
        candidate.candidate_id for candidate, _choice in winners.values()
    )
    return refused_decision(
        context=context,
        refusal=refusal,
        resolver_family="debt_basis",
        loser_candidate_ids=candidate_ids,
        extra_trace={"basis_kinds": winner_kinds},
    )


def _lease_refusal(
    context: ResolverContext,
    grouped: dict[str, tuple[MetricCandidate, ...]],
) -> ResolverDecision:
    refusal = make_resolver_refusal(
        metric_key=context.metric_definition.metric_id,
        reason_code=rc.MATH_DEBT_LEASE_LIABILITY_MIXING_FORBIDDEN,
        details={"basis_kinds": tuple(sorted(grouped))},
    )
    candidate_ids = tuple(
        candidate.candidate_id for family in grouped.values() for candidate in family
    )
    return refused_decision(
        context=context,
        refusal=refusal,
        resolver_family="debt_basis",
        loser_candidate_ids=candidate_ids,
        extra_trace={"basis_kinds": tuple(sorted(grouped))},
    )


def _find_candidate(
    candidates: tuple[MetricCandidate, ...],
    candidate_id: str,
) -> MetricCandidate:
    for candidate in candidates:
        if candidate.candidate_id == candidate_id:
            return candidate
    raise ValueError(f"candidate '{candidate_id}' missing in basis group")


def _basis_names(candidates: tuple[MetricCandidate, ...]) -> tuple[str, ...]:
    return tuple(
        basis_kind
        for basis_kind in sorted({_basis_kind(candidate) for candidate in candidates})
        if basis_kind is not None
    )


DEBT_BASIS_RESOLVER = DebtBasisResolver()
