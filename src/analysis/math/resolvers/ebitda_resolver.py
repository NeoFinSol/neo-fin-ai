from __future__ import annotations

from src.analysis.math.candidates import CandidateSourceKind, MetricCandidate
from src.analysis.math.resolver_engine import ResolverContext, ResolverDecision
from src.analysis.math.resolvers.common import (
    choose_by_precedence,
    decision_from_choice,
)


class EbitdaResolver:
    def resolve(self, context: ResolverContext) -> ResolverDecision:
        choice = choose_by_precedence(context)
        selected = _selected_candidate(context, choice.selected_candidate_id)
        selected_basis = _selected_basis(selected)
        extra_trace = {
            "approximation_semantics": selected_basis == "approximated",
            "canonical_outward_target": _canonical_outward_target(selected_basis),
        }
        return decision_from_choice(
            context=context,
            choice=choice,
            resolver_family="ebitda",
            selected_basis=selected_basis,
            extra_trace=extra_trace,
        )


def _selected_candidate(
    context: ResolverContext,
    candidate_id: str | None,
) -> MetricCandidate | None:
    if candidate_id is None:
        return None
    for candidate in context.candidates:
        if candidate.candidate_id == candidate_id:
            return candidate
    raise ValueError(f"candidate '{candidate_id}' missing in resolver context")


def _selected_basis(candidate: MetricCandidate | None) -> str:
    if candidate is None:
        return "none"
    if candidate.source_kind is CandidateSourceKind.REPORTED:
        return "reported"
    if candidate.precedence_group == "reported":
        return "reported"
    if candidate.synthetic_key == "ebitda_reported":
        return "reported"
    return "approximated"


def _canonical_outward_target(selected_basis: str) -> str | None:
    if selected_basis == "reported":
        return "ebitda_reported"
    if selected_basis == "approximated":
        return "ebitda_approximated"
    return None


EBITDA_RESOLVER = EbitdaResolver()
