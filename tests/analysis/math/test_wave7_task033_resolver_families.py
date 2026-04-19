"""Wave 3 Phase 7 — TASK-033 resolver family suite completion."""

from __future__ import annotations

from decimal import Decimal

import pytest

from src.analysis.math.candidates import (
    build_candidate_set,
    build_derived_candidate,
    build_reported_candidate,
    build_synthetic_candidate,
)
from src.analysis.math.contracts import MetricUnit
from src.analysis.math.registry import REGISTRY
from src.analysis.math.resolver_engine import ResolverStatus, resolve_metric_family
from src.analysis.math.resolver_reason_codes import WAVE3_REASON_MIXED_DEBT_BASIS


@pytest.mark.wave3_phase7
def test_reported_vs_derived_resolves_single_reported_candidate():
    definition = REGISTRY["interest_coverage"]
    c = build_reported_candidate(
        metric_key="interest_coverage",
        formula_id="interest_coverage",
        canonical_value=Decimal("4"),
        unit=MetricUnit.CURRENCY,
        producer="reported.extractor",
        source_inputs=("interest_coverage",),
        source_metric_keys=("interest_coverage",),
        source_refs=("t:1",),
        period_ref=None,
        extractor_source_ref="t:1",
    )
    cs = build_candidate_set((c,))
    decision = resolve_metric_family(definition, cs)
    assert decision.status is ResolverStatus.RESOLVED
    assert decision.selected_candidate_id == c.candidate_id


@pytest.mark.wave3_phase7
def test_ebitda_resolver_prefers_reported_when_both_candidates_exist():
    definition = REGISTRY["ebitda_margin"]
    reported = build_reported_candidate(
        metric_key="ebitda_margin",
        formula_id="ebitda_margin",
        canonical_value=Decimal("50"),
        unit=MetricUnit.CURRENCY,
        producer="precompute.ebitda_variants",
        source_inputs=("ebitda",),
        source_metric_keys=("ebitda_reported",),
        source_refs=("r",),
        period_ref=None,
        extractor_source_ref="r",
        precedence_group="reported",
        resolver_id="ebitda_variants",
    )
    approx = build_derived_candidate(
        metric_key="ebitda_margin",
        formula_id="ebitda_margin",
        canonical_value=Decimal("40"),
        unit=MetricUnit.CURRENCY,
        producer="precompute.ebitda_variants",
        source_inputs=("ebitda",),
        source_metric_keys=("ebitda_approximated",),
        source_refs=("a",),
        period_ref=None,
        derivation_mode="approximation",
        extractor_source_ref="a",
        precedence_group="approximated",
        resolver_id="ebitda_variants",
    )
    cs = build_candidate_set((approx, reported))
    decision = resolve_metric_family(definition, cs)
    assert decision.status is ResolverStatus.RESOLVED
    assert decision.trace_payload.get("approximation_semantics") is False


@pytest.mark.wave3_phase7
def test_debt_basis_resolver_rejects_mixed_debt_and_liabilities_winners():
    definition = REGISTRY["financial_leverage"]
    debt = build_synthetic_candidate(
        metric_key="financial_leverage",
        formula_id="financial_leverage",
        synthetic_key="total_debt",
        canonical_value=Decimal("100"),
        unit=MetricUnit.CURRENCY,
        producer="precompute.total_debt",
        source_inputs=("short_term_borrowings", "long_term_borrowings"),
        source_metric_keys=("short_term_borrowings", "long_term_borrowings"),
        source_refs=("d", "d"),
        period_ref=None,
        precedence_group="debt_only",
    )
    liabilities = build_reported_candidate(
        metric_key="financial_leverage",
        formula_id="financial_leverage",
        canonical_value=Decimal("500"),
        unit=MetricUnit.CURRENCY,
        producer="reported.extractor",
        source_inputs=("total_liabilities",),
        source_metric_keys=("total_liabilities",),
        source_refs=("t",),
        period_ref=None,
        extractor_source_ref="t",
        precedence_group="liabilities_total",
    )
    cs = build_candidate_set((debt, liabilities))
    decision = resolve_metric_family(definition, cs)
    assert decision.status is ResolverStatus.AMBIGUOUS
    assert decision.refusal is not None
    assert WAVE3_REASON_MIXED_DEBT_BASIS in decision.refusal.reason_codes
