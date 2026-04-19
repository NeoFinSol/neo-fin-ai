"""Wave 4 — trace reason semantics vs outward ``DerivedMetric`` fields."""

from __future__ import annotations

import pytest

from src.analysis.math import reason_codes as rc
from src.analysis.math.contracts import DerivedMetric, MetricUnit, ValidityState
from src.analysis.math.engine import MathEngine
from src.analysis.math.trace_reason_semantics import (
    COMPUTATION_EXTRA_REASON_CODES_RAW_KEY,
    FINAL_OUTWARD_KEY,
    MERGED_DECLARED_CANDIDATE_REASON_CODES_KEY,
    final_outward_snapshot,
)
from src.analysis.math.validators import normalize_inputs


def test_trace_final_outward_matches_model_primary_and_supporting() -> None:
    engine = MathEngine()
    out = engine.compute(
        normalize_inputs(
            {
                "current_assets": {"value": 100.0},
                "short_term_liabilities": {"value": 0.0},
            }
        )
    )["current_ratio"]
    fo = out.trace[FINAL_OUTWARD_KEY]
    assert fo["reason_code"] == out.reason_code
    assert fo["reason_codes"] == list(out.reason_codes)


def test_merged_candidates_distinct_from_final_outward_when_multiple() -> None:
    engine = MathEngine()
    out = engine.compute(normalize_inputs({"current_assets": {"value": 100.0}}))[
        "current_ratio"
    ]
    merged = out.trace.get(MERGED_DECLARED_CANDIDATE_REASON_CODES_KEY)
    assert isinstance(merged, list)
    assert set(merged) <= set(out.reason_codes)
    assert out.reason_code in out.reason_codes


def test_computed_path_preserves_raw_extra_reason_codes_bucket() -> None:
    engine = MathEngine()
    out = engine.compute(
        normalize_inputs(
            {
                "current_assets": {"value": 100.0},
                "short_term_liabilities": {"value": 50.0},
            }
        )
    )["current_ratio"]
    raw = out.trace.get(COMPUTATION_EXTRA_REASON_CODES_RAW_KEY)
    assert raw is not None
    assert isinstance(raw, list)


def test_refusal_fragment_uses_candidate_key_not_final_outward() -> None:
    engine = MathEngine()
    out = engine.compute(normalize_inputs({"net_profit": {"value": 12.0}}))["roa"]
    rf = out.trace["refusal_fragment"]
    assert "refusal_candidate_reason_codes" in rf
    assert "reason_codes" not in rf


def test_compute_basis_fragment_uses_refusal_candidate_key() -> None:
    engine = MathEngine()
    out = engine.compute(
        normalize_inputs(
            {
                "net_profit": {"value": 12.0},
                "closing_total_assets": {"value": 140.0},
            }
        )
    )["roa"]
    cbf = out.trace["compute_basis_fragment"]
    assert "refusal_candidate_reason_codes" in cbf
    assert "reason_codes" not in cbf


def test_trace_final_outward_mismatch_raises() -> None:
    from pydantic import ValidationError

    with pytest.raises(ValidationError, match="final_outward"):
        DerivedMetric(
            metric_id="x",
            canonical_value=None,
            projected_value=None,
            unit=MetricUnit.RATIO,
            formula_id="x",
            formula_version="v1",
            validity_state=ValidityState.INVALID,
            reason_code=rc.MATH_FORMULA_INPUTS_MISSING,
            reason_codes=[rc.MATH_FORMULA_INPUTS_MISSING],
            trace={
                FINAL_OUTWARD_KEY: final_outward_snapshot(
                    "WRONG",
                    [rc.MATH_FORMULA_INPUTS_MISSING],
                )
            },
        )


def test_assembly_paths_include_final_outward_block() -> None:
    """Engine and ``DerivedMetric.invalid`` populate ``trace['final_outward']``."""
    engine = MathEngine()
    out = engine.compute(
        normalize_inputs(
            {
                "current_assets": {"value": 100.0},
                "short_term_liabilities": {"value": 50.0},
            }
        )
    )["current_ratio"]
    assert FINAL_OUTWARD_KEY in out.trace
    inv = DerivedMetric.invalid(
        metric_id="z",
        formula_id="z",
        formula_version="v1",
        reason_codes=[rc.MATH_FORMULA_INPUTS_MISSING],
        inputs_snapshot={},
    )
    assert FINAL_OUTWARD_KEY in inv.trace


def test_candidate_fragment_provenance_not_merged_into_outward_reason_codes() -> None:
    """F. Lineage stays under ``candidate_fragment``; outward ``reason_codes`` stay canonical."""
    engine = MathEngine()
    out = engine.compute(
        normalize_inputs(
            {
                "current_assets": {"value": 100.0},
                "short_term_liabilities": {"value": 50.0},
            }
        )
    )["current_ratio"]
    frag = out.trace.get("candidate_fragment")
    assert isinstance(frag, list) and frag
    first = frag[0]
    assert "trace_seed" in first
    for token in out.reason_codes:
        assert "::" not in token and "input:" not in token


def test_input_invalidity_details_remain_diagnostics_not_outward_codes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Undeclared upstream tokens stay in diagnostics only (governance test)."""
    from types import MappingProxyType

    from src.analysis.math.contracts import MetricInputRef, TypedInputs
    from src.analysis.math.registry import (
        AveragingPolicy,
        DenominatorPolicy,
        MetricCoverageClass,
        MetricDefinition,
        SuppressionPolicy,
    )

    def _ratio(values):
        from src.analysis.math.registry import _ratio

        return _ratio("input_a", "input_b")(values)

    definition = MetricDefinition(
        metric_id="ratio_probe",
        formula_id="ratio_probe",
        formula_version="v1",
        required_inputs=("input_a", "input_b"),
        averaging_policy=AveragingPolicy.NONE,
        suppression_policy=SuppressionPolicy.NEVER,
        compute=_ratio,
        coverage_class=MetricCoverageClass.FULLY_SUPPORTED,
        denominator_key="input_b",
        denominator_policy=DenominatorPolicy.STRICT_POSITIVE,
    )
    monkeypatch.setattr(
        "src.analysis.math.engine.REGISTRY",
        MappingProxyType({"ratio_probe": definition}),
    )
    inputs: TypedInputs = {
        "input_a": MetricInputRef(
            metric_key="input_a",
            value=10.0,
            reason_codes=["Z_UNDECLARED_PROBE"],
        ),
        "input_b": MetricInputRef(metric_key="input_b", value=2.0),
    }
    result = MathEngine().compute(inputs)["ratio_probe"]
    details = result.trace.get("input_invalidity_details")
    assert isinstance(details, list) and details
    assert details[0]["upstream_reason"] == "Z_UNDECLARED_PROBE"
    assert "Z_UNDECLARED_PROBE" not in (result.reason_codes or [])
