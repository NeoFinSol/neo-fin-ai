"""Wave 3 Phase 7 — TASK-036 proof-of-usage for resolvers, coverage, average-balance."""

from __future__ import annotations

from decimal import Decimal

import pytest

from src.analysis.math.candidates import build_candidate_set
from src.analysis.math.contracts import ValidityState
from src.analysis.math.engine import MathEngine
from src.analysis.math.registry import REGISTRY, MetricCoverageClass
from src.analysis.math.resolver_engine import resolve_metric_family
from src.analysis.math.resolver_registry import RESOLVER_REGISTRY
from src.analysis.math.validators import normalize_inputs


def _metrics_using_resolver_slot(slot: str) -> tuple[str, ...]:
    return tuple(
        mid for mid, definition in REGISTRY.items() if definition.resolver_slot == slot
    )


@pytest.mark.wave3_phase7
@pytest.mark.parametrize("slot", sorted(RESOLVER_REGISTRY))
def test_each_registered_resolver_slot_used_by_registry_metric(slot: str):
    assert _metrics_using_resolver_slot(
        slot
    ), f"orphan resolver slot in registry: {slot!r}"


@pytest.mark.wave3_phase7
def test_reported_vs_derived_resolver_exercised_via_registry_metric():
    slot = "reported_vs_derived"
    metric_id = _metrics_using_resolver_slot(slot)[0]
    definition = REGISTRY[metric_id]
    from src.analysis.math.candidates import build_reported_candidate
    from src.analysis.math.contracts import MetricUnit

    c = build_reported_candidate(
        metric_key=metric_id,
        formula_id=metric_id,
        canonical_value=Decimal("3"),
        unit=MetricUnit.CURRENCY,
        producer="reported.extractor",
        source_inputs=(metric_id,),
        source_metric_keys=(metric_id,),
        source_refs=("t",),
        period_ref=None,
        extractor_source_ref="t",
    )
    cs = build_candidate_set((c,))
    resolve_metric_family(definition, cs)


@pytest.mark.wave3_phase7
def test_debt_basis_resolver_exercised_via_registry_metric():
    slot = "debt_basis"
    metric_id = _metrics_using_resolver_slot(slot)[0]
    definition = REGISTRY[metric_id]
    from src.analysis.math.precompute import build_precomputed_candidates

    inputs = normalize_inputs(
        {
            "short_term_borrowings": {"value": 10.0},
            "long_term_borrowings": {"value": 20.0},
            "liabilities": {"value": 100.0},
        }
    )
    candidates = build_precomputed_candidates(inputs)
    cs = build_candidate_set(candidates)
    resolve_metric_family(definition, cs)


@pytest.mark.wave3_phase7
def test_ebitda_resolver_exercised_via_registry_metric():
    slot = "ebitda_variants"
    metric_id = _metrics_using_resolver_slot(slot)[0]
    definition = REGISTRY[metric_id]
    from src.analysis.math.precompute import build_precomputed_candidates

    inputs = normalize_inputs(
        {
            "revenue": {"value": 200.0},
            "ebitda": {"value": 40.0, "source": "reported"},
        }
    )
    candidates = build_precomputed_candidates(inputs)
    cs = build_candidate_set(candidates)
    resolve_metric_family(definition, cs)


@pytest.mark.wave3_phase7
def test_each_coverage_class_used_in_registry_has_engine_path():
    used_classes = {definition.coverage_class for definition in REGISTRY.values()}
    exercised = set()
    if MetricCoverageClass.FULLY_SUPPORTED in used_classes:
        MathEngine().compute(
            normalize_inputs(
                {
                    "current_assets": {"value": 200.0},
                    "short_term_liabilities": {"value": 100.0},
                }
            )
        )
        exercised.add(MetricCoverageClass.FULLY_SUPPORTED)
    if MetricCoverageClass.INTENTIONALLY_SUPPRESSED in used_classes:
        suppressed_any = MathEngine().compute(normalize_inputs({}))
        assert any(
            m.validity_state is ValidityState.SUPPRESSED
            for m in suppressed_any.values()
        )
        exercised.add(MetricCoverageClass.INTENTIONALLY_SUPPRESSED)
    assert used_classes <= exercised


@pytest.mark.wave3_phase7
def test_average_balance_metrics_exercised_via_live_engine():
    for metric_id in ("roa", "roe", "asset_turnover"):
        definition = REGISTRY[metric_id]
        assert definition.average_balance_policy_ref == "opening_and_closing_required"
    inputs = normalize_inputs(
        {
            "net_profit": {"value": 12.0},
            "opening_total_assets": {"value": 100.0},
            "closing_total_assets": {"value": 140.0},
            "opening_equity": {"value": 50.0},
            "closing_equity": {"value": 60.0},
            "revenue": {"value": 500.0},
        }
    )
    out = MathEngine().compute(inputs)
    assert out["roa"].trace.get("eligibility_fragment")
    assert out["roe"].trace.get("eligibility_fragment")
    assert out["asset_turnover"].trace.get("eligibility_fragment")
