from __future__ import annotations

from src.analysis.math.candidates import CandidateSourceKind
from src.analysis.math.resolver_engine import ResolverContext, ResolverDecision
from src.analysis.math.resolvers.common import (
    choose_by_precedence,
    decision_from_choice,
    find_candidate,
)


class ReportedVsDerivedResolver:
    def resolve(self, context: ResolverContext) -> ResolverDecision:
        choice = choose_by_precedence(context)
        selected_basis = _selected_basis(context, choice.selected_candidate_id)
        return decision_from_choice(
            context=context,
            choice=choice,
            resolver_family="reported_vs_derived",
            selected_basis=selected_basis,
        )


def _selected_basis(
    context: ResolverContext,
    candidate_id: str | None,
) -> str:
    if candidate_id is None:
        return "none"
    candidate = find_candidate(context, candidate_id)
    if candidate.source_kind is CandidateSourceKind.REPORTED:
        return "reported"
    return "derived"


REPORTED_VS_DERIVED_RESOLVER = ReportedVsDerivedResolver()
