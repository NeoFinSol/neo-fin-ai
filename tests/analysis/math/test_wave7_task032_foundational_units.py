"""Wave 3 Phase 7 — TASK-032 foundational unit suite completion."""

from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from decimal import Decimal

import pytest

from src.analysis.math import reason_codes as rc
from src.analysis.math.candidates import (
    CandidateState,
    build_candidate_set,
    build_derived_candidate,
    build_reported_candidate,
)
from src.analysis.math.compute_basis import (
    ComputeBasisStatus,
    materialize_compute_basis,
)
from src.analysis.math.contracts import MetricComputationResult, MetricUnit
from src.analysis.math.coverage import enforce_coverage
from src.analysis.math.eligibility import EligibilityStatus, evaluate_eligibility
from src.analysis.math.policies import AveragingPolicy, SuppressionPolicy
from src.analysis.math.precedence import PRECEDENCE_POLICIES, PrecedenceStatus
from src.analysis.math.refusals import RefusalStage, make_coverage_refusal
from src.analysis.math.registry import REGISTRY, MetricCoverageClass, MetricDefinition
from src.analysis.math.synthetic_contract import (
    is_declared_synthetic_key,
    validate_synthetic_key,
)
from src.analysis.math.trace_models import TraceSeed


@pytest.mark.wave3_phase7
def test_synthetic_contract_whitespace_key_rejected():
    assert is_declared_synthetic_key("   ") is False
    with pytest.raises(ValueError, match="undeclared synthetic key"):
        validate_synthetic_key("   ")


@pytest.mark.wave3_phase7
def test_trace_seed_frozen():
    seed = TraceSeed(
        metric_key="m",
        formula_id="f",
        source_refs=("r",),
        period_ref=None,
    )
    with pytest.raises(FrozenInstanceError):
        seed.metric_key = "x"  # type: ignore[misc]


@pytest.mark.wave3_phase7
def test_provenance_roundtrip_via_candidate():
    c = build_reported_candidate(
        metric_key="k",
        formula_id="k",
        canonical_value=Decimal("1"),
        unit=MetricUnit.CURRENCY,
        producer="reported.extractor",
        source_inputs=("k",),
        source_metric_keys=("k",),
        source_refs=("s",),
        period_ref=None,
        extractor_source_ref="s",
    )
    assert c.provenance.extractor_source_ref == "s"
    assert c.provenance.resolver_id is None


@pytest.mark.wave3_phase7
def test_build_candidate_set_ordering_stable():
    a = build_reported_candidate(
        metric_key="z",
        formula_id="z",
        canonical_value=Decimal("1"),
        unit=MetricUnit.CURRENCY,
        producer="reported.extractor",
        source_inputs=("z",),
        source_metric_keys=("z",),
        source_refs=("a",),
        period_ref=None,
        extractor_source_ref="a",
    )
    b = build_reported_candidate(
        metric_key="z",
        formula_id="z",
        canonical_value=Decimal("2"),
        unit=MetricUnit.CURRENCY,
        producer="reported.extractor",
        source_inputs=("z",),
        source_metric_keys=("z",),
        source_refs=("b",),
        period_ref=None,
        extractor_source_ref="b",
    )
    first = build_candidate_set((b, a))
    second = build_candidate_set((a, b))
    ids1 = [x.candidate_id for x in first.candidates_by_metric["z"]]
    ids2 = [x.candidate_id for x in second.candidates_by_metric["z"]]
    assert ids1 == ids2


@pytest.mark.wave3_phase7
def test_precedence_policy_registry_contains_defaults():
    assert "reported_over_derived_default" in PRECEDENCE_POLICIES
    policy = PRECEDENCE_POLICIES["reported_over_derived_default"]
    c = build_reported_candidate(
        metric_key="m",
        formula_id="m",
        canonical_value=Decimal("3"),
        unit=MetricUnit.CURRENCY,
        producer="reported.extractor",
        source_inputs=("m",),
        source_metric_keys=("m",),
        source_refs=("t",),
        period_ref=None,
        extractor_source_ref="t",
        candidate_state=CandidateState.READY,
    )
    choice = policy.choose((c,))
    assert choice.status is PrecedenceStatus.SELECTED


@pytest.mark.wave3_phase7
def test_coverage_refusal_carries_coverage_stage():
    refusal = make_coverage_refusal(
        metric_key="m",
        reason_code=rc.MATH_COVERAGE_INTENTIONALLY_SUPPRESSED,
        coverage_class="INTENTIONALLY_SUPPRESSED",
    )
    assert refusal.stage is RefusalStage.COVERAGE


@pytest.mark.wave3_phase7
def test_eligibility_unknown_average_balance_policy_refused():
    definition = REGISTRY["roa"]
    opening = build_reported_candidate(
        metric_key=definition.denominator_key or "",
        formula_id=definition.metric_id,
        canonical_value=Decimal("1"),
        unit=MetricUnit.CURRENCY,
        producer="reported.extractor",
        source_inputs=("opening_total_assets",),
        source_metric_keys=("opening_total_assets",),
        source_refs=("o",),
        period_ref=None,
        extractor_source_ref="o",
        precedence_group="opening_balance",
    )
    closing = build_reported_candidate(
        metric_key=definition.denominator_key or "",
        formula_id=definition.metric_id,
        canonical_value=Decimal("2"),
        unit=MetricUnit.CURRENCY,
        producer="reported.extractor",
        source_inputs=("closing_total_assets",),
        source_metric_keys=("closing_total_assets",),
        source_refs=("c",),
        period_ref=None,
        extractor_source_ref="c",
        precedence_group="closing_balance",
    )
    broken = replace(definition, average_balance_policy_ref="unknown_policy_xyz")
    result = evaluate_eligibility(
        broken, opening_candidate=opening, closing_candidate=closing
    )
    assert result.status is EligibilityStatus.REFUSED


@pytest.mark.wave3_phase7
def test_compute_basis_refused_when_no_eligibility_basis():
    def _stub_compute(_: object) -> MetricComputationResult:
        return MetricComputationResult(value=None, trace={})

    definition = MetricDefinition(
        metric_id="x",
        formula_id="x",
        formula_version="v1",
        required_inputs=("a",),
        averaging_policy=AveragingPolicy.NONE,
        suppression_policy=SuppressionPolicy.NEVER,
        compute=_stub_compute,
        coverage_class=MetricCoverageClass.FULLY_SUPPORTED,
    )
    from types import MappingProxyType

    from src.analysis.math.eligibility import EligibilityResult, EligibilityStatus
    from src.analysis.math.refusals import make_missing_basis_refusal

    refusal = make_missing_basis_refusal(
        metric_key="x",
        reason_code=rc.COMPARATIVE_MISSING_OPENING_BALANCE,
        missing_basis="opening_balance",
    )
    elig = EligibilityResult(
        status=EligibilityStatus.REFUSED,
        policy_ref="opening_and_closing_required",
        basis_candidates=(),
        refusal=refusal,
        trace_payload=MappingProxyType({}),
    )
    basis = materialize_compute_basis(
        definition,
        eligibility_result=elig,
        selected_candidates=None,
    )
    assert basis.status is ComputeBasisStatus.REFUSED


@pytest.mark.wave3_phase7
def test_enforce_coverage_reported_only_with_derived_selected_blocks():
    def _stub_compute(_: object) -> MetricComputationResult:
        return MetricComputationResult(value=None, trace={})

    definition = MetricDefinition(
        metric_id="m",
        formula_id="m",
        formula_version="v1",
        required_inputs=("a",),
        averaging_policy=AveragingPolicy.NONE,
        suppression_policy=SuppressionPolicy.NEVER,
        compute=_stub_compute,
        coverage_class=MetricCoverageClass.REPORTED_ONLY,
    )
    derived = build_derived_candidate(
        metric_key="m",
        formula_id="m",
        canonical_value=Decimal("1"),
        unit=MetricUnit.CURRENCY,
        producer="resolver.derived",
        source_inputs=("a",),
        source_metric_keys=("a",),
        source_refs=("d",),
        period_ref=None,
        derivation_mode="formula",
        extractor_source_ref="d",
    )
    gate = enforce_coverage(definition, selected_candidate=derived)
    assert gate.refusal is not None
