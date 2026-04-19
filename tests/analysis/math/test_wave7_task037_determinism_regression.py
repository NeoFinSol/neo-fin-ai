"""Wave 3 Phase 7 — TASK-037 determinism and anti-regression."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.analysis.math.candidates import build_candidate_set
from src.analysis.math.engine import MathEngine
from src.analysis.math.precompute import build_precomputed_candidates
from src.analysis.math.registry import REGISTRY
from src.analysis.math.startup_validation import audit_wave3_reason_literals_source
from src.analysis.math.validators import normalize_inputs


@pytest.mark.wave3_phase7
def test_engine_determinism_same_inputs_twice():
    inputs = normalize_inputs(
        {
            "current_assets": {"value": 200.0},
            "short_term_liabilities": {"value": 100.0},
        }
    )
    engine = MathEngine()
    first = engine.compute(inputs)
    second = engine.compute(inputs)

    def _snapshot(metrics: dict) -> dict[str, tuple[str, tuple[str, ...]]]:
        return {
            k: (metrics[k].validity_state.value, tuple(metrics[k].reason_codes))
            for k in sorted(metrics)
        }

    assert _snapshot(first) == _snapshot(second)


@pytest.mark.wave3_phase7
def test_precompute_module_has_no_resolver_import_string():
    path = (
        Path(__file__).resolve().parents[3]
        / "src"
        / "analysis"
        / "math"
        / "precompute.py"
    )
    text = path.read_text(encoding="utf-8")
    assert "resolve_metric_family" not in text
    assert "RESOLVER_REGISTRY" not in text


@pytest.mark.wave3_phase7
def test_candidate_set_order_deterministic_under_input_permutation():
    inputs_a = normalize_inputs(
        {
            "current_assets": {"value": 200.0},
            "short_term_liabilities": {"value": 100.0},
        }
    )
    inputs_b = normalize_inputs(
        {
            "short_term_liabilities": {"value": 100.0},
            "current_assets": {"value": 200.0},
        }
    )
    c1 = build_candidate_set(build_precomputed_candidates(inputs_a))
    c2 = build_candidate_set(build_precomputed_candidates(inputs_b))
    assert sorted(c1.candidates_by_metric.keys()) == sorted(
        c2.candidates_by_metric.keys()
    )
    for key in c1.candidates_by_metric:
        ids1 = [c.candidate_id for c in c1.candidates_by_metric[key]]
        ids2 = [c.candidate_id for c in c2.candidates_by_metric[key]]
        assert ids1 == ids2


@pytest.mark.wave3_phase7
def test_ebitda_reported_path_marks_approximation_false(
    monkeypatch: pytest.MonkeyPatch,
):
    from types import MappingProxyType

    from src.analysis.math.contracts import MetricComputationResult, MetricUnit
    from src.analysis.math.policies import (
        AveragingPolicy,
        DenominatorPolicy,
        SuppressionPolicy,
    )
    from src.analysis.math.registry import MetricCoverageClass, MetricDefinition

    def _ratio(_: object) -> MetricComputationResult:
        return MetricComputationResult(value=0.2, trace={})

    definition = MetricDefinition(
        metric_id="ebitda_margin",
        formula_id="ebitda_margin",
        formula_version="v1",
        required_inputs=("ebitda_reported", "revenue"),
        averaging_policy=AveragingPolicy.NONE,
        suppression_policy=SuppressionPolicy.NEVER,
        compute=_ratio,
        coverage_class=MetricCoverageClass.FULLY_SUPPORTED,
        denominator_key="revenue",
        denominator_policy=DenominatorPolicy.STRICT_POSITIVE,
        resolver_slot="ebitda_variants",
        precedence_policy_ref="reported_over_derived",
        synthetic_dependencies=frozenset({"ebitda_reported"}),
    )
    monkeypatch.setattr(
        "src.analysis.math.engine.REGISTRY",
        MappingProxyType({"ebitda_margin": definition}),
    )
    out = MathEngine().compute(
        normalize_inputs(
            {
                "revenue": {"value": 100.0},
                "ebitda": {"value": 25.0, "source": "reported"},
            }
        )
    )["ebitda_margin"]
    assert (
        out.trace.get("resolver_fragment", {}).get("approximation_semantics") is False
    )


@pytest.mark.wave3_phase7
def test_missing_opening_for_average_balance_not_silent_valid():
    inputs = normalize_inputs(
        {
            "net_profit": {"value": 10.0},
            "closing_total_assets": {"value": 200.0},
        }
    )
    out = MathEngine().compute(inputs)["roa"]
    assert out.validity_state.value == "invalid"


@pytest.mark.wave3_phase7
def test_precompute_source_has_no_undeclared_wave3_reason_literals():
    path = (
        Path(__file__).resolve().parents[3]
        / "src"
        / "analysis"
        / "math"
        / "precompute.py"
    )
    hits = audit_wave3_reason_literals_source(
        path.read_text(encoding="utf-8"), filename="precompute.py"
    )
    assert hits == ()
