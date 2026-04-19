from __future__ import annotations

from dataclasses import fields
from decimal import Decimal

import pytest

from src.analysis.math.candidates import (
    CandidateState,
    build_derived_candidate,
    build_reported_candidate,
)
from src.analysis.math.compute_basis import (
    ComputeBasisStatus,
    materialize_compute_basis,
)
from src.analysis.math.contracts import (
    MetricComputationResult,
    MetricUnit,
    ValidityState,
)
from src.analysis.math.coverage import (
    CoverageComputeMode,
    CoverageEmitMode,
    enforce_coverage,
)
from src.analysis.math.eligibility import (
    EligibilityStatus,
    evaluate_eligibility,
    validate_average_balance_basis,
)
from src.analysis.math.precedence import PRECEDENCE_POLICIES, PrecedenceStatus
from src.analysis.math.refusals import (
    RefusalStage,
    make_ambiguity_refusal,
    make_missing_basis_refusal,
)
from src.analysis.math.registry import MetricCoverageClass, MetricDefinition
from src.analysis.math.resolver_reason_codes import (
    WAVE3_REASON_AMBIGUOUS_CANDIDATES,
    WAVE3_REASON_COVERAGE_SUPPRESSED,
    WAVE3_REASON_FORBIDDEN_APPROXIMATION,
    WAVE3_REASON_INCOMPATIBLE_OPENING_BASIS,
    WAVE3_REASON_MISSING_CLOSING_BALANCE,
    WAVE3_REASON_MISSING_OPENING_BALANCE,
    WAVE3_REASON_OUT_OF_SCOPE_OUTWARD_REFUSAL,
)
from src.analysis.math.trace_builders import (
    build_candidate_trace,
    build_coverage_trace,
    build_eligibility_trace,
    build_refusal_trace,
    build_resolver_trace,
)


def _dummy_compute(*_args, **_kwargs) -> MetricComputationResult:
    return MetricComputationResult(value=None, trace={})


def _make_definition(
    *,
    metric_id: str = "ebitda_margin",
    coverage_class: MetricCoverageClass = MetricCoverageClass.FULLY_SUPPORTED,
    average_balance_policy_ref: str | None = None,
) -> MetricDefinition:
    return MetricDefinition(
        metric_id=metric_id,
        formula_id=metric_id,
        formula_version="v2",
        required_inputs=("input_a", "input_b"),
        averaging_policy=None,  # type: ignore[arg-type]
        suppression_policy=None,  # type: ignore[arg-type]
        compute=_dummy_compute,
        coverage_class=coverage_class,
        average_balance_policy_ref=average_balance_policy_ref,
    )


def _make_reported_candidate(metric_key: str = "ebitda_margin"):
    return build_reported_candidate(
        metric_key=metric_key,
        formula_id=metric_key,
        canonical_value=Decimal("12.5"),
        unit=MetricUnit.CURRENCY,
        producer="reported.extractor",
        source_inputs=("ebitda",),
        source_metric_keys=("ebitda",),
        source_refs=("table:1",),
        period_ref="2025-12-31",
        extractor_source_ref="table:1",
    )


def _make_derived_candidate(metric_key: str = "ebitda_margin"):
    return build_derived_candidate(
        metric_key=metric_key,
        formula_id=metric_key,
        canonical_value=Decimal("11.1"),
        unit=MetricUnit.CURRENCY,
        producer="resolver.ebitda",
        source_inputs=("revenue", "operating_profit"),
        source_metric_keys=("revenue", "operating_profit"),
        source_refs=("derived:1",),
        period_ref="2025-12-31",
        derivation_mode="approximation",
    )


def _make_opening_candidate(
    *,
    unit: MetricUnit = MetricUnit.CURRENCY,
    state: CandidateState = CandidateState.READY,
):
    return build_reported_candidate(
        metric_key="average_total_assets",
        formula_id="roa",
        canonical_value=Decimal("100.0"),
        unit=unit,
        producer="reported.extractor",
        source_inputs=("opening_total_assets",),
        source_metric_keys=("total_assets",),
        source_refs=("opening:1",),
        period_ref="2024-12-31",
        extractor_source_ref="opening:1",
        candidate_state=state,
    )


def _make_closing_candidate(
    *,
    unit: MetricUnit = MetricUnit.CURRENCY,
    state: CandidateState = CandidateState.READY,
):
    return build_reported_candidate(
        metric_key="average_total_assets",
        formula_id="roa",
        canonical_value=Decimal("110.0"),
        unit=unit,
        producer="reported.extractor",
        source_inputs=("closing_total_assets",),
        source_metric_keys=("total_assets",),
        source_refs=("closing:1",),
        period_ref="2025-12-31",
        extractor_source_ref="closing:1",
        candidate_state=state,
    )


def test_precedence_policy_deterministic():
    policy = PRECEDENCE_POLICIES["reported_over_derived_default"]
    reported = _make_reported_candidate()
    derived = _make_derived_candidate()

    choice_a = policy.choose((reported, derived))
    choice_b = policy.choose((derived, reported))

    assert choice_a.status is PrecedenceStatus.SELECTED
    assert choice_b.status is PrecedenceStatus.SELECTED
    assert choice_a.selected_candidate_id == reported.candidate_id
    assert choice_b.selected_candidate_id == reported.candidate_id
    assert choice_a.loser_candidate_ids == choice_b.loser_candidate_ids


def test_precedence_policy_does_not_emit_refusal():
    policy = PRECEDENCE_POLICIES["reported_over_derived_default"]
    choice = policy.choose((_make_reported_candidate(),))
    field_names = {field.name for field in fields(type(choice))}

    assert "refusal" not in field_names
    assert getattr(choice, "refusal", None) is None


def test_refusal_helpers_preserve_stage_and_reasons():
    ambiguity = make_ambiguity_refusal(
        metric_key="ebitda_margin",
        candidate_ids=("reported:1", "derived:1"),
    )
    missing_basis = make_missing_basis_refusal(
        metric_key="roa",
        reason_code=WAVE3_REASON_MISSING_OPENING_BALANCE,
        missing_basis="opening_balance",
    )

    assert ambiguity.stage is RefusalStage.RESOLVER
    assert ambiguity.reason_codes == (WAVE3_REASON_AMBIGUOUS_CANDIDATES,)
    assert missing_basis.stage is RefusalStage.ELIGIBILITY
    assert missing_basis.reason_codes == (WAVE3_REASON_MISSING_OPENING_BALANCE,)


@pytest.mark.parametrize(
    (
        "coverage_class",
        "candidate",
        "approximation_semantics",
        "compute_mode",
        "emit_mode",
        "has_refusal",
    ),
    [
        (
            MetricCoverageClass.FULLY_SUPPORTED,
            _make_derived_candidate("current_ratio"),
            False,
            CoverageComputeMode.ALLOW,
            CoverageEmitMode.ALLOW,
            False,
        ),
        (
            MetricCoverageClass.REPORTED_ONLY,
            _make_reported_candidate("interest_coverage"),
            False,
            CoverageComputeMode.ALLOW,
            CoverageEmitMode.ALLOW,
            False,
        ),
        (
            MetricCoverageClass.DERIVED_FORMULA,
            _make_derived_candidate("ros"),
            False,
            CoverageComputeMode.ALLOW,
            CoverageEmitMode.ALLOW,
            False,
        ),
        (
            MetricCoverageClass.APPROXIMATE_ONLY,
            _make_derived_candidate("ebitda_margin"),
            True,
            CoverageComputeMode.ALLOW,
            CoverageEmitMode.ALLOW,
            False,
        ),
        (
            MetricCoverageClass.INTENTIONALLY_SUPPRESSED,
            _make_reported_candidate("inventory_turnover"),
            False,
            CoverageComputeMode.BLOCK,
            CoverageEmitMode.FORBID,
            True,
        ),
        (
            MetricCoverageClass.OUT_OF_SCOPE,
            _make_reported_candidate("receivables_turnover"),
            False,
            CoverageComputeMode.BLOCK,
            CoverageEmitMode.FORBID,
            True,
        ),
    ],
)
def test_coverage_gate_behavior_for_each_coverage_class(
    coverage_class: MetricCoverageClass,
    candidate,
    approximation_semantics: bool,
    compute_mode: CoverageComputeMode,
    emit_mode: CoverageEmitMode,
    has_refusal: bool,
):
    definition = _make_definition(
        metric_id=candidate.metric_key, coverage_class=coverage_class
    )
    result = enforce_coverage(
        definition,
        selected_candidate=candidate,
        approximation_semantics=approximation_semantics,
    )

    assert result.compute_mode is compute_mode
    assert result.emit_mode is emit_mode
    assert (result.refusal is not None) is has_refusal


def test_out_of_scope_refusal_works():
    definition = _make_definition(
        metric_id="receivables_turnover",
        coverage_class=MetricCoverageClass.OUT_OF_SCOPE,
    )

    result = enforce_coverage(
        definition, selected_candidate=_make_reported_candidate("receivables_turnover")
    )

    assert result.refusal is not None
    assert result.refusal.reason_codes == (WAVE3_REASON_OUT_OF_SCOPE_OUTWARD_REFUSAL,)
    assert result.final_validity_state is ValidityState.NOT_APPLICABLE


def test_suppressed_outward_refusal_works():
    definition = _make_definition(
        metric_id="inventory_turnover",
        coverage_class=MetricCoverageClass.INTENTIONALLY_SUPPRESSED,
    )

    result = enforce_coverage(
        definition, selected_candidate=_make_reported_candidate("inventory_turnover")
    )

    assert result.refusal is not None
    assert result.refusal.reason_codes == (WAVE3_REASON_COVERAGE_SUPPRESSED,)
    assert result.final_validity_state is ValidityState.SUPPRESSED


def test_missing_opening_basis_refusal_works():
    definition = _make_definition(
        metric_id="roa",
        average_balance_policy_ref="opening_and_closing_required",
    )

    result = evaluate_eligibility(
        definition,
        opening_candidate=None,
        closing_candidate=_make_closing_candidate(),
    )

    assert result.status is EligibilityStatus.REFUSED
    assert result.refusal is not None
    assert WAVE3_REASON_MISSING_OPENING_BALANCE in result.refusal.reason_codes


def test_both_balance_candidates_absent_prefers_opening_refusal():
    definition = _make_definition(
        metric_id="roa",
        average_balance_policy_ref="opening_and_closing_required",
    )

    result = validate_average_balance_basis(
        definition,
        opening_candidate=None,
        closing_candidate=None,
    )

    assert result.refusal is not None
    assert WAVE3_REASON_MISSING_OPENING_BALANCE in result.refusal.reason_codes
    assert WAVE3_REASON_MISSING_CLOSING_BALANCE not in result.refusal.reason_codes


def test_incompatible_opening_basis_refusal_works():
    definition = _make_definition(
        metric_id="roa",
        average_balance_policy_ref="opening_and_closing_required",
    )

    result = validate_average_balance_basis(
        definition,
        opening_candidate=_make_opening_candidate(unit=MetricUnit.DAYS),
        closing_candidate=_make_closing_candidate(unit=MetricUnit.CURRENCY),
    )

    assert result.status is EligibilityStatus.REFUSED
    assert result.refusal is not None
    assert result.refusal.reason_codes == (WAVE3_REASON_INCOMPATIBLE_OPENING_BASIS,)


def test_closing_only_approximation_blocked():
    definition = _make_definition(
        metric_id="roa",
        average_balance_policy_ref="opening_and_closing_required",
    )

    result = validate_average_balance_basis(
        definition,
        opening_candidate=None,
        closing_candidate=_make_closing_candidate(),
    )

    assert result.status is EligibilityStatus.REFUSED
    assert result.refusal is not None
    assert WAVE3_REASON_FORBIDDEN_APPROXIMATION in result.refusal.reason_codes


def test_compute_basis_materialization_works_for_success_and_refusal_path():
    definition = _make_definition(
        metric_id="roa",
        average_balance_policy_ref="opening_and_closing_required",
    )
    eligibility_success = validate_average_balance_basis(
        definition,
        opening_candidate=_make_opening_candidate(),
        closing_candidate=_make_closing_candidate(),
    )
    success_basis = materialize_compute_basis(
        definition,
        eligibility_result=eligibility_success,
    )

    eligibility_failure = validate_average_balance_basis(
        definition,
        opening_candidate=None,
        closing_candidate=_make_closing_candidate(),
    )
    refused_basis = materialize_compute_basis(
        definition,
        eligibility_result=eligibility_failure,
    )

    assert success_basis.status is ComputeBasisStatus.READY
    assert len(success_basis.selected_candidates) == 2
    assert refused_basis.status is ComputeBasisStatus.REFUSED
    assert refused_basis.refusal is not None


def test_trace_builders_produce_structured_trace_fragments():
    candidate = _make_reported_candidate("current_ratio")
    definition = _make_definition(
        metric_id="roa", average_balance_policy_ref="opening_and_closing_required"
    )
    eligibility = validate_average_balance_basis(
        definition,
        opening_candidate=_make_opening_candidate(),
        closing_candidate=_make_closing_candidate(),
    )
    coverage = enforce_coverage(
        _make_definition(metric_id="ros"),
        selected_candidate=_make_derived_candidate("ros"),
    )
    refusal = make_ambiguity_refusal(
        metric_key="ebitda_margin",
        candidate_ids=("reported:1", "derived:1"),
    )

    candidate_trace = build_candidate_trace(candidate)
    eligibility_trace = build_eligibility_trace(eligibility)
    resolver_trace = build_resolver_trace(
        metric_key="ebitda_margin",
        resolver_slot="ebitda_variants",
        precedence_policy_ref="reported_over_derived_default",
        selected_candidate_id="reported:1",
        loser_candidate_ids=("derived:1",),
        status="RESOLVED",
        reason_codes=(),
    )
    coverage_trace = build_coverage_trace(
        _make_definition(metric_id="ros"),
        coverage,
    )
    refusal_trace = build_refusal_trace(refusal)

    for fragment in (
        candidate_trace,
        eligibility_trace,
        resolver_trace,
        coverage_trace,
        refusal_trace,
    ):
        assert isinstance(fragment, dict)
        assert fragment
