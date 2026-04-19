from __future__ import annotations

from decimal import Decimal
from types import MappingProxyType

import pytest

from src.analysis.math.candidates import (
    build_candidate_set,
    build_derived_candidate,
    build_reported_candidate,
)
from src.analysis.math.contracts import MetricComputationResult, MetricUnit
from src.analysis.math.refusals import make_ambiguity_refusal
from src.analysis.math.registry import MetricCoverageClass, MetricDefinition
from src.analysis.math.resolver_engine import (
    ResolverDecision,
    ResolverDecisionValidationError,
    ResolverStatus,
    collect_resolver_framework_errors,
    resolve_metric_family,
)
from src.analysis.math.resolver_registry import (
    ResolverRegistryLookupError,
    get_resolver_handler,
)


def _dummy_compute(*_args, **_kwargs) -> MetricComputationResult:
    return MetricComputationResult(value=None, trace={})


def _make_definition(
    *,
    metric_id: str = "ebitda_margin",
    resolver_slot: str | None = "ebitda_variants",
    precedence_policy_ref: str | None = "reported_over_derived",
) -> MetricDefinition:
    return MetricDefinition(
        metric_id=metric_id,
        formula_id=metric_id,
        formula_version="v2",
        required_inputs=("ebitda_reported", "revenue"),
        averaging_policy=None,  # type: ignore[arg-type]
        suppression_policy=None,  # type: ignore[arg-type]
        compute=_dummy_compute,
        coverage_class=MetricCoverageClass.INTENTIONALLY_SUPPRESSED,
        resolver_slot=resolver_slot,
        precedence_policy_ref=precedence_policy_ref,
    )


def _make_reported_candidate(metric_key: str = "ebitda_margin"):
    return build_reported_candidate(
        metric_key=metric_key,
        formula_id=metric_key,
        canonical_value=Decimal("12.5"),
        unit=MetricUnit.CURRENCY,
        producer="reported.extractor",
        source_inputs=("ebitda_reported",),
        source_metric_keys=("ebitda_reported",),
        source_refs=("table:1",),
        period_ref="2025-12-31",
        extractor_source_ref="table:1",
    )


def _make_derived_candidate(metric_key: str = "ebitda_margin"):
    return build_derived_candidate(
        metric_key=metric_key,
        formula_id=metric_key,
        canonical_value=Decimal("11.0"),
        unit=MetricUnit.CURRENCY,
        producer="resolver.ebitda",
        source_inputs=("operating_profit",),
        source_metric_keys=("operating_profit",),
        source_refs=("derived:1",),
        period_ref="2025-12-31",
        derivation_mode="approximation",
    )


class _ResolvedHandler:
    def resolve(self, context):
        choice = context.precedence_policy.choose(context.candidates)
        return ResolverDecision(
            status=ResolverStatus.RESOLVED,
            selected_candidate_id=choice.selected_candidate_id,
            loser_candidate_ids=choice.loser_candidate_ids,
            refusal=None,
        )


class _AmbiguousHandler:
    def resolve(self, context):
        candidate_ids = tuple(
            candidate.candidate_id for candidate in context.candidates
        )
        return ResolverDecision(
            status=ResolverStatus.AMBIGUOUS,
            selected_candidate_id=None,
            loser_candidate_ids=candidate_ids,
            refusal=make_ambiguity_refusal(
                metric_key=context.metric_definition.metric_id,
                candidate_ids=candidate_ids,
            ),
        )


class _InvalidOutputHandler:
    def resolve(self, _context):
        return "not-a-decision"


class _ResolvedWithoutSelectedHandler:
    def resolve(self, _context):
        return ResolverDecision(
            status=ResolverStatus.RESOLVED,
            selected_candidate_id=None,
            loser_candidate_ids=(),
            refusal=None,
        )


class _AmbiguousWithoutRefusalHandler:
    def resolve(self, context):
        candidate_ids = tuple(
            candidate.candidate_id for candidate in context.candidates
        )
        return ResolverDecision(
            status=ResolverStatus.AMBIGUOUS,
            selected_candidate_id=None,
            loser_candidate_ids=candidate_ids,
            refusal=None,
        )


class _OutsideFamilyHandler:
    def __init__(self, outsider_id: str) -> None:
        self._outsider_id = outsider_id

    def resolve(self, _context):
        return ResolverDecision(
            status=ResolverStatus.RESOLVED,
            selected_candidate_id=self._outsider_id,
            loser_candidate_ids=(),
            refusal=None,
        )


def _patch_registry(
    monkeypatch: pytest.MonkeyPatch, entries: dict[str, object]
) -> None:
    monkeypatch.setattr(
        "src.analysis.math.resolver_registry.RESOLVER_REGISTRY",
        MappingProxyType(dict(entries)),
    )


def test_registered_slot_lookup_works(monkeypatch: pytest.MonkeyPatch):
    handler = _ResolvedHandler()
    _patch_registry(monkeypatch, {"ebitda_variants": handler})

    assert get_resolver_handler("ebitda_variants") is handler


def test_missing_slot_fails_predictably(monkeypatch: pytest.MonkeyPatch):
    _patch_registry(monkeypatch, {})

    with pytest.raises(ResolverRegistryLookupError, match="unknown resolver slot"):
        get_resolver_handler("missing_slot")


def test_resolve_metric_family_handles_resolved_flow(monkeypatch: pytest.MonkeyPatch):
    reported = _make_reported_candidate()
    derived = _make_derived_candidate()
    _patch_registry(monkeypatch, {"ebitda_variants": _ResolvedHandler()})

    decision = resolve_metric_family(
        _make_definition(),
        build_candidate_set((derived, reported)),
    )

    assert decision.status is ResolverStatus.RESOLVED
    assert decision.selected_candidate_id == reported.candidate_id
    assert decision.loser_candidate_ids == (derived.candidate_id,)
    assert decision.refusal is None


def test_resolve_metric_family_handles_ambiguous_flow(monkeypatch: pytest.MonkeyPatch):
    reported = _make_reported_candidate()
    derived = _make_derived_candidate()
    candidate_set = build_candidate_set((reported, derived))
    _patch_registry(monkeypatch, {"ebitda_variants": _AmbiguousHandler()})

    decision = resolve_metric_family(
        _make_definition(),
        candidate_set,
    )

    assert decision.status is ResolverStatus.AMBIGUOUS
    assert decision.selected_candidate_id is None
    assert decision.refusal is not None
    assert decision.refusal.details["candidate_ids"] == tuple(
        candidate.candidate_id
        for candidate in candidate_set.candidates_by_metric["ebitda_margin"]
    )


def test_invalid_handler_output_rejected(monkeypatch: pytest.MonkeyPatch):
    _patch_registry(monkeypatch, {"ebitda_variants": _InvalidOutputHandler()})

    with pytest.raises(
        ResolverDecisionValidationError, match="Resolver handler returned"
    ):
        resolve_metric_family(
            _make_definition(),
            build_candidate_set((_make_reported_candidate(),)),
        )


def test_resolved_without_selected_candidate_rejected(
    monkeypatch: pytest.MonkeyPatch,
):
    _patch_registry(
        monkeypatch,
        {"ebitda_variants": _ResolvedWithoutSelectedHandler()},
    )

    with pytest.raises(
        ResolverDecisionValidationError,
        match="RESOLVED decision requires selected_candidate_id",
    ):
        resolve_metric_family(
            _make_definition(),
            build_candidate_set((_make_reported_candidate(),)),
        )


def test_ambiguous_without_refusal_rejected(monkeypatch: pytest.MonkeyPatch):
    _patch_registry(
        monkeypatch,
        {"ebitda_variants": _AmbiguousWithoutRefusalHandler()},
    )

    with pytest.raises(
        ResolverDecisionValidationError,
        match="AMBIGUOUS decision requires refusal",
    ):
        resolve_metric_family(
            _make_definition(),
            build_candidate_set(
                (_make_reported_candidate(), _make_derived_candidate())
            ),
        )


def test_selected_candidate_outside_family_rejected(monkeypatch: pytest.MonkeyPatch):
    outsider = _make_reported_candidate("other_metric")
    _patch_registry(
        monkeypatch,
        {"ebitda_variants": _OutsideFamilyHandler(outsider.candidate_id)},
    )

    with pytest.raises(
        ResolverDecisionValidationError,
        match="selected candidate must belong to metric family",
    ):
        resolve_metric_family(
            _make_definition(),
            build_candidate_set((_make_reported_candidate(), outsider)),
        )


def test_resolver_framework_expectations_flag_missing_refs():
    missing_slot = collect_resolver_framework_errors(
        _make_definition(
            resolver_slot=None, precedence_policy_ref="reported_over_derived"
        )
    )
    missing_precedence = collect_resolver_framework_errors(
        _make_definition(resolver_slot="ebitda_variants", precedence_policy_ref=None)
    )

    assert "precedence_policy_ref requires resolver_slot" in missing_slot
    assert "resolver_slot requires precedence_policy_ref" in missing_precedence
