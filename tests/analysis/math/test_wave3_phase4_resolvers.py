from __future__ import annotations

from decimal import Decimal

from src.analysis.math.candidates import (
    build_candidate_set,
    build_derived_candidate,
    build_reported_candidate,
    build_synthetic_candidate,
)
from src.analysis.math.contracts import MetricUnit
from src.analysis.math.registry import REGISTRY
from src.analysis.math.resolver_engine import ResolverStatus, resolve_metric_family
from src.analysis.math.resolver_reason_codes import (
    WAVE3_REASON_AMBIGUOUS_CANDIDATES,
    WAVE3_REASON_LEASE_LIABILITY_MIXING_FORBIDDEN,
    WAVE3_REASON_MIXED_DEBT_BASIS,
)
from src.analysis.math.resolver_registry import has_resolver_handler


def _reported_candidate(
    *,
    metric_key: str,
    value: str = "10.0",
    source_metric_keys: tuple[str, ...] = (),
    precedence_group: str | None = None,
    extractor_source_ref: str = "table:1",
):
    return build_reported_candidate(
        metric_key=metric_key,
        formula_id=metric_key,
        canonical_value=Decimal(value),
        unit=MetricUnit.CURRENCY,
        producer="reported.extractor",
        source_inputs=source_metric_keys,
        source_metric_keys=source_metric_keys,
        source_refs=(extractor_source_ref,),
        period_ref="2025-12-31",
        extractor_source_ref=extractor_source_ref,
        precedence_group=precedence_group,
    )


def _derived_candidate(
    *,
    metric_key: str,
    value: str = "9.0",
    source_metric_keys: tuple[str, ...] = (),
    precedence_group: str | None = None,
    derivation_mode: str = "formula",
):
    return build_derived_candidate(
        metric_key=metric_key,
        formula_id=metric_key,
        canonical_value=Decimal(value),
        unit=MetricUnit.CURRENCY,
        producer="resolver.derived",
        source_inputs=source_metric_keys,
        source_metric_keys=source_metric_keys,
        source_refs=("derived:1",),
        period_ref="2025-12-31",
        derivation_mode=derivation_mode,
        precedence_group=precedence_group,
    )


def _synthetic_candidate(
    *,
    metric_key: str,
    synthetic_key: str = "total_debt",
    value: str = "15.0",
    source_metric_keys: tuple[str, ...] = (),
    precedence_group: str | None = None,
):
    return build_synthetic_candidate(
        metric_key=metric_key,
        formula_id=metric_key,
        synthetic_key=synthetic_key,
        canonical_value=Decimal(value),
        unit=MetricUnit.CURRENCY,
        producer="precompute.total_debt",
        source_inputs=source_metric_keys,
        source_metric_keys=source_metric_keys,
        source_refs=("synthetic:1",),
        period_ref="2025-12-31",
        precedence_group=precedence_group,
    )


def test_reported_vs_derived_reported_wins_over_derived():
    definition = REGISTRY["interest_coverage"]
    reported = _reported_candidate(
        metric_key="interest_coverage",
        source_metric_keys=("interest_coverage_reported",),
    )
    derived = _derived_candidate(
        metric_key="interest_coverage",
        source_metric_keys=("ebit", "interest_expense"),
    )

    decision = resolve_metric_family(
        definition, build_candidate_set((derived, reported))
    )

    assert decision.status is ResolverStatus.RESOLVED
    assert decision.selected_candidate_id == reported.candidate_id
    assert decision.trace_payload["resolver_family"] == "reported_vs_derived"
    assert decision.trace_payload["selected_basis"] == "reported"


def test_ebitda_reported_beats_approximated():
    definition = REGISTRY["ebitda_margin"]
    reported = _reported_candidate(
        metric_key="ebitda_margin",
        value="30.0",
        source_metric_keys=("ebitda_reported",),
        precedence_group="reported",
    )
    approximated = _derived_candidate(
        metric_key="ebitda_margin",
        value="28.0",
        source_metric_keys=("operating_profit", "depreciation"),
        precedence_group="approximated",
        derivation_mode="approximation",
    )

    decision = resolve_metric_family(
        definition, build_candidate_set((approximated, reported))
    )

    assert decision.status is ResolverStatus.RESOLVED
    assert decision.selected_candidate_id == reported.candidate_id
    assert decision.trace_payload["resolver_family"] == "ebitda"
    assert decision.trace_payload["selected_basis"] == "reported"


def test_ebitda_approximated_path_stays_distinct():
    definition = REGISTRY["ebitda_margin"]
    approximated = _derived_candidate(
        metric_key="ebitda_margin",
        value="28.0",
        source_metric_keys=("operating_profit", "depreciation"),
        precedence_group="approximated",
        derivation_mode="approximation",
    )

    decision = resolve_metric_family(definition, build_candidate_set((approximated,)))

    assert decision.status is ResolverStatus.RESOLVED
    assert decision.selected_candidate_id == approximated.candidate_id
    assert decision.trace_payload["selected_basis"] == "approximated"
    assert decision.trace_payload["approximation_semantics"] is True


def test_ebitda_ambiguity_refusal():
    definition = REGISTRY["ebitda_margin"]
    first_reported = _reported_candidate(
        metric_key="ebitda_margin",
        value="30.0",
        source_metric_keys=("ebitda_reported",),
        precedence_group="reported",
        extractor_source_ref="table:1",
    )
    second_reported = _reported_candidate(
        metric_key="ebitda_margin",
        value="31.0",
        source_metric_keys=("ebitda_reported",),
        precedence_group="reported",
        extractor_source_ref="table:2",
    )

    decision = resolve_metric_family(
        definition,
        build_candidate_set((first_reported, second_reported)),
    )

    assert decision.status is ResolverStatus.AMBIGUOUS
    assert decision.refusal is not None
    assert decision.refusal.reason_codes == (WAVE3_REASON_AMBIGUOUS_CANDIDATES,)


def test_debt_only_path_works():
    definition = REGISTRY["financial_leverage_debt_only"]
    debt_candidate = _synthetic_candidate(
        metric_key="financial_leverage_debt_only",
        synthetic_key="total_debt",
        source_metric_keys=("total_debt",),
        precedence_group="debt_only",
    )

    decision = resolve_metric_family(definition, build_candidate_set((debt_candidate,)))

    assert decision.status is ResolverStatus.RESOLVED
    assert decision.selected_candidate_id == debt_candidate.candidate_id
    assert decision.trace_payload["selected_basis"] == "debt_only"


def test_liabilities_total_path_works():
    definition = REGISTRY["financial_leverage_total"]
    liabilities_candidate = _reported_candidate(
        metric_key="financial_leverage_total",
        source_metric_keys=("total_liabilities",),
        precedence_group="liabilities_total",
    )

    decision = resolve_metric_family(
        definition,
        build_candidate_set((liabilities_candidate,)),
    )

    assert decision.status is ResolverStatus.RESOLVED
    assert decision.selected_candidate_id == liabilities_candidate.candidate_id
    assert decision.trace_payload["selected_basis"] == "liabilities_total"


def test_forbidden_lease_liability_mixing_refusal():
    definition = REGISTRY["financial_leverage_total"]
    liabilities_candidate = _reported_candidate(
        metric_key="financial_leverage_total",
        source_metric_keys=("total_liabilities",),
        precedence_group="liabilities_total",
    )
    lease_candidate = _reported_candidate(
        metric_key="financial_leverage_total",
        source_metric_keys=("lease_liabilities",),
        precedence_group="lease_liabilities",
        extractor_source_ref="table:lease",
    )

    decision = resolve_metric_family(
        definition,
        build_candidate_set((liabilities_candidate, lease_candidate)),
    )

    assert decision.status is ResolverStatus.REFUSED
    assert decision.refusal is not None
    assert decision.refusal.reason_codes == (
        WAVE3_REASON_LEASE_LIABILITY_MIXING_FORBIDDEN,
    )


def test_ambiguous_mixed_basis_refusal():
    definition = REGISTRY["financial_leverage"]
    debt_candidate = _synthetic_candidate(
        metric_key="financial_leverage",
        synthetic_key="total_debt",
        source_metric_keys=("total_debt",),
        precedence_group="debt_only",
    )
    liabilities_candidate = _reported_candidate(
        metric_key="financial_leverage",
        source_metric_keys=("total_liabilities",),
        precedence_group="liabilities_total",
    )

    decision = resolve_metric_family(
        definition,
        build_candidate_set((debt_candidate, liabilities_candidate)),
    )

    assert decision.status is ResolverStatus.AMBIGUOUS
    assert decision.refusal is not None
    assert decision.refusal.reason_codes == (WAVE3_REASON_MIXED_DEBT_BASIS,)


def test_required_registry_slots_exist_for_implemented_families():
    assert REGISTRY["ebitda_margin"].resolver_slot == "ebitda_variants"
    assert REGISTRY["financial_leverage"].resolver_slot == "debt_basis"
    assert REGISTRY["financial_leverage_total"].resolver_slot == "debt_basis"
    assert REGISTRY["financial_leverage_debt_only"].resolver_slot == "debt_basis"
    assert REGISTRY["interest_coverage"].resolver_slot == "reported_vs_derived"
    assert REGISTRY["roa"].average_balance_policy_ref == "opening_and_closing_required"
    assert REGISTRY["roe"].average_balance_policy_ref == "opening_and_closing_required"
    assert REGISTRY["asset_turnover"].average_balance_policy_ref == (
        "opening_and_closing_required"
    )
    assert has_resolver_handler("ebitda_variants") is True
    assert has_resolver_handler("debt_basis") is True
    assert has_resolver_handler("reported_vs_derived") is True
