from __future__ import annotations

import json
from decimal import Decimal
from types import MappingProxyType

import pytest

from src.analysis.math import reason_codes as rc
from src.analysis.math.candidates import MetricCandidate, build_reported_candidate
from src.analysis.math.contracts import (
    MetricComputationResult,
    MetricInputRef,
    MetricUnit,
    ValidityState,
)
from src.analysis.math.engine import MathEngine
from src.analysis.math.policies import (
    AveragingPolicy,
    DenominatorPolicy,
    SuppressionPolicy,
)
from src.analysis.math.precompute import build_precomputed_candidates
from src.analysis.math.registry import REGISTRY, MetricCoverageClass, MetricDefinition
from src.analysis.math.validators import (
    normalize_inputs,
    validate_metric_inputs_unit_compatibility,
)


def _placeholder_compute(_values) -> MetricComputationResult:
    return MetricComputationResult(value=None, trace={"placeholder": True})


def _ratio_compute(values) -> MetricComputationResult:
    numerator = values["ebitda_reported"].value
    denominator = values["revenue"].value
    if numerator is None or denominator is None:
        return MetricComputationResult(value=None, trace={"missing": True})
    return MetricComputationResult(
        value=numerator / denominator,
        trace={"numerator": numerator, "denominator": denominator},
    )


def _make_definition(
    *,
    metric_id: str,
    required_inputs: tuple[str, ...] = (),
    coverage_class: MetricCoverageClass = MetricCoverageClass.FULLY_SUPPORTED,
    resolver_slot: str | None = None,
    precedence_policy_ref: str | None = None,
    average_balance_policy_ref: str | None = None,
    denominator_key: str | None = None,
    denominator_policy: DenominatorPolicy | None = None,
    synthetic_dependencies: frozenset[str] | None = None,
    resolver_required_input_prefix: str | None = None,
    resolver_bridge_input_key: str | None = None,
    compute=_placeholder_compute,
) -> MetricDefinition:
    return MetricDefinition(
        metric_id=metric_id,
        formula_id=metric_id,
        formula_version="v3",
        required_inputs=required_inputs,
        averaging_policy=AveragingPolicy.NONE,
        suppression_policy=SuppressionPolicy.NEVER,
        compute=compute,
        coverage_class=coverage_class,
        denominator_key=denominator_key,
        denominator_policy=denominator_policy,
        resolver_slot=resolver_slot,
        precedence_policy_ref=precedence_policy_ref,
        average_balance_policy_ref=average_balance_policy_ref,
        synthetic_dependencies=synthetic_dependencies or frozenset(),
        resolver_required_input_prefix=resolver_required_input_prefix,
        resolver_bridge_input_key=resolver_bridge_input_key,
    )


def _patch_registry(
    monkeypatch: pytest.MonkeyPatch,
    definitions: dict[str, MetricDefinition],
) -> None:
    monkeypatch.setattr(
        "src.analysis.math.engine.REGISTRY",
        MappingProxyType(definitions),
    )


def _make_reported_family_candidate(
    metric_key: str,
    *,
    value: str,
    source_ref: str,
) -> MetricCandidate:
    return build_reported_candidate(
        metric_key=metric_key,
        formula_id=metric_key,
        canonical_value=Decimal(value),
        unit=MetricUnit.CURRENCY,
        producer="reported.extractor",
        source_inputs=(metric_key,),
        source_metric_keys=(metric_key,),
        source_refs=(source_ref,),
        period_ref="2025-12-31",
        extractor_source_ref=source_ref,
    )


def test_precompute_emits_typed_candidates_only():
    candidates = build_precomputed_candidates(
        normalize_inputs(
            {
                "current_assets": {"value": 200.0},
                "short_term_liabilities": {"value": 100.0},
                "revenue": {"value": 500.0},
            }
        )
    )

    assert candidates
    assert all(isinstance(candidate, MetricCandidate) for candidate in candidates)
    assert all(not isinstance(candidate, dict) for candidate in candidates)


def test_no_shadow_regression_in_precompute_path():
    candidates = build_precomputed_candidates(
        normalize_inputs(
            {
                "opening_total_assets": {"value": 100.0},
                "closing_total_assets": {"value": 140.0},
                "average_total_assets": {"value": 120.0},
                "liabilities": {"value": 300.0},
                "lease_liabilities": {"value": 40.0},
            }
        )
    )
    candidate_ids = [candidate.candidate_id for candidate in candidates]

    assert len(candidate_ids) == len(set(candidate_ids))


def test_engine_builds_candidate_set_deterministically():
    engine = MathEngine()
    first = engine.compute(
        normalize_inputs(
            {
                "net_profit": {"value": 12.0},
                "opening_total_assets": {"value": 100.0},
                "closing_total_assets": {"value": 140.0},
            }
        )
    )
    second = engine.compute(
        normalize_inputs(
            {
                "closing_total_assets": {"value": 140.0},
                "opening_total_assets": {"value": 100.0},
                "net_profit": {"value": 12.0},
            }
        )
    )

    assert json.dumps(
        first["roa"].trace["candidate_fragment"], sort_keys=True
    ) == json.dumps(
        second["roa"].trace["candidate_fragment"],
        sort_keys=True,
    )


def test_missing_opening_short_circuits_path():
    engine = MathEngine()
    result = engine.compute(
        normalize_inputs(
            {
                "net_profit": {"value": 12.0},
                "closing_total_assets": {"value": 140.0},
            }
        )
    )["roa"]

    assert result.validity_state is ValidityState.INVALID
    assert rc.COMPARATIVE_MISSING_OPENING_BALANCE in result.reason_codes
    assert result.trace["refusal_fragment"]["stage"] == "eligibility"
    assert result.trace["compute_basis_fragment"]["status"] == "REFUSED"
    assert (
        rc.COMPARATIVE_MISSING_OPENING_BALANCE
        in result.trace["compute_basis_fragment"]["refusal_candidate_reason_codes"]
    )


def test_incompatible_opening_short_circuits_path():
    engine = MathEngine()
    result = engine.compute(
        normalize_inputs(
            {
                "net_profit": {"value": 12.0},
                "opening_total_assets": MetricInputRef(
                    metric_key="opening_total_assets",
                    value=100.0,
                    reason_codes=["incompatible_basis"],
                ),
                "closing_total_assets": {"value": 140.0},
            }
        )
    )["roa"]

    assert result.validity_state is ValidityState.INVALID
    assert rc.COMPARATIVE_INCOMPATIBLE_OPENING_BASIS in result.reason_codes
    assert result.trace["refusal_fragment"]["stage"] == "eligibility"


def test_layer_c_unit_compatibility_rejects_distinct_units():
    definition = REGISTRY["equity_ratio"]
    inputs = {
        "equity": MetricInputRef(metric_key="equity", value=1.0, unit="currency"),
        "total_assets": MetricInputRef(
            metric_key="total_assets", value=2.0, unit="days"
        ),
    }
    assert (
        validate_metric_inputs_unit_compatibility(definition, inputs)
        == rc.MATH_UNIT_INCOMPATIBLE
    )


def test_resolver_capable_family_goes_through_resolver(
    monkeypatch: pytest.MonkeyPatch,
):
    calls: list[str] = []
    actual = __import__(
        "src.analysis.math.engine",
        fromlist=["resolve_metric_family"],
    ).resolve_metric_family

    def _spy(definition, candidate_set):
        calls.append(definition.metric_id)
        return actual(definition, candidate_set)

    monkeypatch.setattr("src.analysis.math.engine.resolve_metric_family", _spy)
    probe = MetricDefinition(
        metric_id="resolver_probe",
        formula_id="resolver_probe",
        formula_version="v3",
        required_inputs=("ebitda_reported", "revenue"),
        averaging_policy=AveragingPolicy.NONE,
        suppression_policy=SuppressionPolicy.NEVER,
        compute=_placeholder_compute,
        coverage_class=MetricCoverageClass.FULLY_SUPPORTED,
        denominator_key="revenue",
        denominator_policy=DenominatorPolicy.STRICT_POSITIVE,
        resolver_slot="ebitda_variants",
        precedence_policy_ref="reported_over_derived",
        synthetic_dependencies=frozenset({"ebitda_reported"}),
        resolver_required_input_prefix="ebitda",
        resolver_bridge_input_key="ebitda_reported",
    )
    _patch_registry(monkeypatch, {"resolver_probe": probe})
    MathEngine().compute(
        normalize_inputs(
            {
                "revenue": {"value": 500.0},
                "ebitda": {"value": 80.0, "source": "reported"},
            }
        )
    )

    assert "resolver_probe" in calls


def test_intentionally_suppressed_metric_skips_resolver_family(
    monkeypatch: pytest.MonkeyPatch,
):
    calls: list[str] = []

    def _spy(definition, candidate_set):
        calls.append(definition.metric_id)
        from src.analysis.math.resolver_engine import resolve_metric_family as real

        return real(definition, candidate_set)

    monkeypatch.setattr("src.analysis.math.engine.resolve_metric_family", _spy)
    MathEngine().compute(
        normalize_inputs(
            {
                "revenue": {"value": 500.0},
                "ebitda": {"value": 80.0, "source": "reported"},
            }
        )
    )

    assert "ebitda_margin" not in calls


def test_non_resolver_family_skips_resolver_cleanly(
    monkeypatch: pytest.MonkeyPatch,
):
    calls: list[str] = []

    def _spy(*_args, **_kwargs):
        calls.append("called")
        raise AssertionError("resolver should not run")

    _patch_registry(monkeypatch, {"current_ratio": REGISTRY["current_ratio"]})
    monkeypatch.setattr("src.analysis.math.engine.resolve_metric_family", _spy)
    result = MathEngine().compute(
        normalize_inputs(
            {
                "current_assets": {"value": 200.0},
                "short_term_liabilities": {"value": 100.0},
            }
        )
    )["current_ratio"]

    assert result.validity_state is ValidityState.VALID
    assert calls == []


def test_out_of_scope_coverage_refusal_blocks_compute(
    monkeypatch: pytest.MonkeyPatch,
):
    compute_called = False

    def _forbidden_compute(_values):
        nonlocal compute_called
        compute_called = True
        raise AssertionError("compute must not run")

    definition = _make_definition(
        metric_id="out_of_scope_metric",
        required_inputs=("input_a",),
        coverage_class=MetricCoverageClass.OUT_OF_SCOPE,
        compute=_forbidden_compute,
    )
    _patch_registry(monkeypatch, {"out_of_scope_metric": definition})
    result = MathEngine().compute(normalize_inputs({"input_a": {"value": 10.0}}))[
        "out_of_scope_metric"
    ]

    assert compute_called is False
    assert result.validity_state is ValidityState.NOT_APPLICABLE
    assert result.reason_codes == [rc.MATH_COVERAGE_OUT_OF_SCOPE]


def test_suppressed_coverage_refusal_blocks_outward_path(
    monkeypatch: pytest.MonkeyPatch,
):
    compute_called = False

    def _forbidden_compute(_values):
        nonlocal compute_called
        compute_called = True
        raise AssertionError("compute must not run")

    definition = _make_definition(
        metric_id="suppressed_metric",
        required_inputs=("input_a",),
        coverage_class=MetricCoverageClass.INTENTIONALLY_SUPPRESSED,
        compute=_forbidden_compute,
    )
    _patch_registry(monkeypatch, {"suppressed_metric": definition})
    result = MathEngine().compute(normalize_inputs({"input_a": {"value": 10.0}}))[
        "suppressed_metric"
    ]

    assert compute_called is False
    assert result.validity_state is ValidityState.SUPPRESSED
    assert result.reason_codes == [rc.MATH_COVERAGE_INTENTIONALLY_SUPPRESSED]
    assert result.trace["compute_basis_fragment"]["status"] == "REFUSED"
    assert result.trace["compute_basis_fragment"]["refusal_candidate_reason_codes"] == (
        rc.MATH_COVERAGE_INTENTIONALLY_SUPPRESSED,
    )


def test_resolved_candidate_becomes_compute_basis(
    monkeypatch: pytest.MonkeyPatch,
):
    definition = _make_definition(
        metric_id="ebitda_margin",
        required_inputs=("ebitda_reported", "revenue"),
        coverage_class=MetricCoverageClass.FULLY_SUPPORTED,
        resolver_slot="ebitda_variants",
        precedence_policy_ref="reported_over_derived",
        compute=_ratio_compute,
        denominator_key="revenue",
        denominator_policy=DenominatorPolicy.STRICT_POSITIVE,
        synthetic_dependencies=frozenset({"ebitda_reported"}),
        resolver_required_input_prefix="ebitda",
        resolver_bridge_input_key="ebitda_reported",
    )
    _patch_registry(monkeypatch, {"ebitda_margin": definition})
    result = MathEngine().compute(
        normalize_inputs(
            {
                "revenue": {"value": 100.0},
                "ebitda": {"value": 25.0, "source": "reported"},
            }
        )
    )["ebitda_margin"]

    assert result.validity_state is ValidityState.VALID
    assert result.value == 0.25
    assert len(result.trace["compute_basis_fragment"]["candidate_ids"]) == 2


def test_ambiguity_refusal_becomes_explicit_non_success_derived_metric(
    monkeypatch: pytest.MonkeyPatch,
):
    definition = _make_definition(
        metric_id="interest_coverage",
        resolver_slot="reported_vs_derived",
        precedence_policy_ref="reported_over_derived",
    )
    _patch_registry(monkeypatch, {"interest_coverage": definition})
    candidates = (
        _make_reported_family_candidate(
            "interest_coverage",
            value="10.0",
            source_ref="table:1",
        ),
        _make_reported_family_candidate(
            "interest_coverage",
            value="11.0",
            source_ref="table:2",
        ),
    )
    monkeypatch.setattr(
        "src.analysis.math.engine.build_precomputed_candidates",
        lambda _inputs: candidates,
    )
    result = MathEngine().compute({})["interest_coverage"]

    assert result.validity_state is ValidityState.INVALID
    assert result.reason_codes == [rc.MATH_RESOLVER_AMBIGUOUS_CANDIDATES]
    assert result.trace["refusal_fragment"]["stage"] == "resolver"


def test_trace_contains_candidate_resolver_coverage_and_refusal_fragments(
    monkeypatch: pytest.MonkeyPatch,
):
    definition = _make_definition(
        metric_id="interest_coverage",
        resolver_slot="reported_vs_derived",
        precedence_policy_ref="reported_over_derived",
    )
    _patch_registry(monkeypatch, {"interest_coverage": definition})
    candidates = (
        _make_reported_family_candidate(
            "interest_coverage",
            value="10.0",
            source_ref="table:1",
        ),
        _make_reported_family_candidate(
            "interest_coverage",
            value="11.0",
            source_ref="table:2",
        ),
    )
    monkeypatch.setattr(
        "src.analysis.math.engine.build_precomputed_candidates",
        lambda _inputs: candidates,
    )
    result = MathEngine().compute({})["interest_coverage"]

    assert "candidate_fragment" in result.trace
    assert "resolver_fragment" in result.trace
    assert "coverage_fragment" in result.trace
    assert "refusal_fragment" in result.trace
