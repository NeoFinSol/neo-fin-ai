"""Wave 3 Phase 7 — TASK-034 engine integration (full pipeline surface)."""

from __future__ import annotations

import pytest

from src.analysis.math.candidates import build_candidate_set
from src.analysis.math.engine import MathEngine
from src.analysis.math.precompute import build_precomputed_candidates
from src.analysis.math.registry import REGISTRY
from src.analysis.math.validators import normalize_inputs


@pytest.mark.wave3_phase7
def test_full_pipeline_surfaces_for_current_ratio():
    inputs = normalize_inputs(
        {
            "current_assets": {"value": 200.0},
            "short_term_liabilities": {"value": 100.0},
        }
    )
    candidates = build_precomputed_candidates(inputs)
    build_candidate_set(candidates)
    out = MathEngine().compute(inputs)["current_ratio"]
    assert out.trace.get("candidate_fragment")
    assert out.trace.get("coverage_fragment")
    assert out.value is not None


@pytest.mark.wave3_phase7
def test_refusal_propagation_roa_missing_opening():
    inputs = normalize_inputs(
        {
            "net_profit": {"value": 10.0},
            "closing_total_assets": {"value": 200.0},
        }
    )
    out = MathEngine().compute(inputs)["roa"]
    assert out.trace.get("refusal_fragment") is not None
    assert out.trace["refusal_fragment"]["stage"] == "eligibility"


@pytest.mark.wave3_phase7
def test_trace_propagation_includes_ordered_fragments_for_resolver_metric(
    monkeypatch: pytest.MonkeyPatch,
):
    """Resolver-backed metric carries resolver + coverage fragments in trace."""
    from decimal import Decimal
    from types import MappingProxyType

    from src.analysis.math.candidates import build_reported_candidate
    from src.analysis.math.contracts import MetricComputationResult, MetricUnit
    from src.analysis.math.policies import (
        AveragingPolicy,
        DenominatorPolicy,
        SuppressionPolicy,
    )
    from src.analysis.math.registry import MetricCoverageClass, MetricDefinition

    def _stub(_: object) -> MetricComputationResult:
        return MetricComputationResult(value=1.0, trace={})

    definition = MetricDefinition(
        metric_id="interest_coverage",
        formula_id="interest_coverage",
        formula_version="v1",
        required_inputs=("interest_coverage",),
        averaging_policy=AveragingPolicy.NONE,
        suppression_policy=SuppressionPolicy.NEVER,
        compute=_stub,
        coverage_class=MetricCoverageClass.FULLY_SUPPORTED,
        resolver_slot="reported_vs_derived",
        precedence_policy_ref="reported_over_derived",
    )
    monkeypatch.setattr(
        "src.analysis.math.engine.REGISTRY",
        MappingProxyType({"interest_coverage": definition}),
    )
    c1 = build_reported_candidate(
        metric_key="interest_coverage",
        formula_id="interest_coverage",
        canonical_value=Decimal("5"),
        unit=MetricUnit.CURRENCY,
        producer="reported.extractor",
        source_inputs=("interest_coverage",),
        source_metric_keys=("interest_coverage",),
        source_refs=("t:1",),
        period_ref=None,
        extractor_source_ref="t:1",
    )
    monkeypatch.setattr(
        "src.analysis.math.engine.build_precomputed_candidates",
        lambda _inputs: (c1,),
    )
    out = MathEngine().compute({})["interest_coverage"]
    assert "candidate_fragment" in out.trace
    assert "resolver_fragment" in out.trace
    assert "coverage_fragment" in out.trace


@pytest.mark.wave3_phase7
def test_engine_output_json_stable_keys():
    inputs = normalize_inputs(
        {
            "net_profit": {"value": 12.0},
            "opening_total_assets": {"value": 100.0},
            "closing_total_assets": {"value": 140.0},
        }
    )
    out = MathEngine().compute(inputs)["roa"]
    trace = out.trace
    assert set(trace.keys()) >= {
        "candidate_fragment",
        "coverage_fragment",
        "eligibility_fragment",
        "compute_basis_fragment",
    }
    assert isinstance(trace["candidate_fragment"], list)
