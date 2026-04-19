from __future__ import annotations

from dataclasses import FrozenInstanceError, fields
from decimal import Decimal

import pytest

from src.analysis.math.candidates import (
    CandidateSourceKind,
    CandidateState,
    MetricCandidate,
    build_candidate_set,
    build_reported_candidate,
    build_synthetic_candidate,
)
from src.analysis.math.contracts import MetricComputationResult, MetricUnit
from src.analysis.math.provenance import CandidateProvenance
from src.analysis.math.registry import MetricCoverageClass, MetricDefinition
from src.analysis.math.synthetic_contract import (
    is_declared_synthetic_key,
    validate_synthetic_key,
    validate_synthetic_producer,
)
from src.analysis.math.trace_models import TraceSeed


def _dummy_compute(*_args, **_kwargs) -> MetricComputationResult:
    return MetricComputationResult(value=None, trace={})


def test_declared_synthetic_key_accepted():
    assert is_declared_synthetic_key("total_debt") is True
    validate_synthetic_key("average_equity")


def test_undeclared_synthetic_key_rejected():
    with pytest.raises(ValueError, match="undeclared synthetic key"):
        validate_synthetic_key("unknown_synthetic_metric")


def test_forbidden_producer_rejected():
    with pytest.raises(ValueError, match="forbidden synthetic producer"):
        validate_synthetic_producer("frontend.payload_builder")


def test_metric_candidate_immutable():
    candidate = MetricCandidate(
        candidate_id="metric:reported:source",
        metric_key="current_ratio",
        source_kind=CandidateSourceKind.REPORTED,
        canonical_value=Decimal("1.25"),
        unit=MetricUnit.RATIO,
        candidate_state=CandidateState.READY,
        provenance=CandidateProvenance(
            producer="reported.extractor",
            source_inputs=("current_assets", "short_term_liabilities"),
            derivation_mode=None,
            source_metric_keys=("current_assets", "short_term_liabilities"),
            source_period_ref="2025-12-31",
            extractor_source_ref="table:1",
            resolver_id=None,
        ),
        synthetic_key=None,
        precedence_group=None,
        trace_seed=TraceSeed(
            metric_key="current_ratio",
            formula_id="current_ratio",
            source_refs=("table:1",),
            period_ref="2025-12-31",
        ),
    )

    with pytest.raises(FrozenInstanceError):
        candidate.metric_key = "ros"  # type: ignore[misc]


def test_metric_candidate_has_no_outward_numeric_fields():
    field_names = {field.name for field in fields(MetricCandidate)}
    assert "projected_value" not in field_names
    assert "value" not in field_names
    assert "legacy_label" not in field_names
    assert "coverage_class" not in field_names


def test_candidate_set_deterministic():
    reported = build_reported_candidate(
        metric_key="current_ratio",
        formula_id="current_ratio",
        canonical_value=Decimal("1.25"),
        unit=MetricUnit.RATIO,
        producer="reported.extractor",
        source_inputs=("current_assets", "short_term_liabilities"),
        source_metric_keys=("current_assets", "short_term_liabilities"),
        source_refs=("table:1",),
        period_ref="2025-12-31",
    )
    synthetic = build_synthetic_candidate(
        metric_key="roa",
        formula_id="roa",
        synthetic_key="average_total_assets",
        canonical_value=Decimal("105.0"),
        unit=MetricUnit.CURRENCY,
        producer="comparative.average_balance",
        source_inputs=("opening_total_assets", "closing_total_assets"),
        source_metric_keys=("total_assets",),
        source_refs=("comparative:avg_assets",),
        period_ref="2025-12-31",
    )

    set_a = build_candidate_set((reported, synthetic))
    set_b = build_candidate_set((synthetic, reported))

    assert set_a == set_b
    assert tuple(set_a.candidates_by_metric) == ("current_ratio", "roa")


def test_candidate_builder_attaches_provenance_correctly():
    candidate = build_synthetic_candidate(
        metric_key="roa",
        formula_id="roa",
        synthetic_key="average_total_assets",
        canonical_value=Decimal("205.0"),
        unit=MetricUnit.CURRENCY,
        producer="comparative.average_balance",
        source_inputs=("opening_total_assets", "closing_total_assets"),
        source_metric_keys=("total_assets",),
        source_refs=("comparative:avg_assets",),
        period_ref="2025-12-31",
        derivation_mode="average_balance",
        extractor_source_ref="comparative:window",
        resolver_id=None,
    )

    assert candidate.synthetic_key == "average_total_assets"
    assert candidate.provenance.producer == "comparative.average_balance"
    assert candidate.provenance.source_inputs == (
        "opening_total_assets",
        "closing_total_assets",
    )
    assert candidate.trace_seed.metric_key == "roa"
    assert candidate.trace_seed.formula_id == "roa"
    assert candidate.trace_seed.source_refs == ("comparative:avg_assets",)
    assert candidate.trace_seed.period_ref == "2025-12-31"


def test_metric_definition_accepts_wave3_declarative_refs():
    definition = MetricDefinition(
        metric_id="roa",
        formula_id="roa",
        formula_version="v2",
        required_inputs=("net_profit", "average_total_assets"),
        averaging_policy=None,  # type: ignore[arg-type]
        suppression_policy=None,  # type: ignore[arg-type]
        compute=_dummy_compute,
        coverage_class=MetricCoverageClass.FULLY_SUPPORTED,
        resolver_slot=None,
        precedence_policy_ref=None,
        average_balance_policy_ref="opening_and_closing_required",
        synthetic_dependencies=frozenset({"average_total_assets"}),
    )

    assert definition.coverage_class is MetricCoverageClass.FULLY_SUPPORTED
    assert definition.average_balance_policy_ref == "opening_and_closing_required"
    assert definition.synthetic_dependencies == frozenset({"average_total_assets"})
    assert not hasattr(definition, "resolver")
    assert not hasattr(definition, "precedence_policy")
