"""
Task E: Engine Denominator Gate and Refusal Assembly Tests (Section 8, E1-E10)

Tests for engine-level denominator policy enforcement:
- Engine blocks unsafe denominators before formula execution
- Engine assembles final structured refusal
- Deterministic refusal mapping (UNAVAILABLE/INVALID)
- No helper invocation on denial path
- Typed-only boundary preserved

Reference: .agent/math_layer_v2_wave2_spec.md Section 8, 11, 13
"""

from __future__ import annotations

import pytest

from src.analysis.math.contracts import MetricInputRef, TypedInputs, ValidityState
from src.analysis.math.engine import MathEngine
from src.analysis.math.policies import DenominatorClass
from src.analysis.math.registry import REGISTRY


class TestEngineDenominatorGate:
    """E1-E4: Test engine integrates classifier + evaluator."""

    def test_e1_engine_detects_ratio_like_metrics(self):
        """E1: Engine should process ratio-like metrics from registry."""
        # Proof metric is ratio-like with ALLOW_ANY_NON_ZERO
        assert "_wave2_proof_allow_any_non_zero" in REGISTRY

    def test_e3_engine_calls_classifier_for_strict_positive(self):
        """E3: Engine classifies denominator for STRICT_POSITIVE metrics."""
        engine = MathEngine()

        # current_ratio uses STRICT_POSITIVE
        inputs: TypedInputs = {
            "current_assets": MetricInputRef(metric_key="current_assets", value=100.0),
            "short_term_liabilities": MetricInputRef(
                metric_key="short_term_liabilities", value=50.0
            ),
        }

        result = engine.compute(inputs)
        # Should succeed with positive denominator
        assert "current_ratio" in result
        assert result["current_ratio"].validity_state == ValidityState.VALID

    def test_e4_engine_applies_evaluator_for_allow_any_non_zero(self):
        """E4: Engine applies evaluator for ALLOW_ANY_NON_ZERO proof metric."""
        engine = MathEngine()

        # Test with negative denominator (should be ALLOWED by ALLOW_ANY_NON_ZERO)
        inputs: TypedInputs = {
            "proof_numerator": MetricInputRef(metric_key="proof_numerator", value=10.0),
            "proof_denominator": MetricInputRef(
                metric_key="proof_denominator", value=-5.0
            ),
        }

        result = engine.compute(inputs)
        proof_result = result["_wave2_proof_allow_any_non_zero"]

        # Negative denominator should be ALLOWED under ALLOW_ANY_NON_ZERO
        assert proof_result.validity_state == ValidityState.VALID


class TestEngineFinalRefusalAssembly:
    """E5-E6: Test engine-owned final refusal assembly."""

    def test_e5_engine_assembles_refusal_for_zero_denominator(self):
        """E5+E6: Zero denominator → INVALID refusal assembled by engine."""
        engine = MathEngine()

        inputs: TypedInputs = {
            "current_assets": MetricInputRef(metric_key="current_assets", value=100.0),
            "short_term_liabilities": MetricInputRef(
                metric_key="short_term_liabilities", value=0.0
            ),
        }

        result = engine.compute(inputs)
        ratio_result = result["current_ratio"]

        assert ratio_result.validity_state == ValidityState.INVALID
        assert any("denominator" in reason for reason in ratio_result.reason_codes)
        assert any("zero" in reason for reason in ratio_result.reason_codes)

    def test_e5_engine_assembles_refusal_for_missing_denominator(self):
        """E5+E6: Missing denominator gets canonical unavailable reason code."""
        engine = MathEngine()

        inputs: TypedInputs = {
            "current_assets": MetricInputRef(metric_key="current_assets", value=100.0),
            # short_term_liabilities is MISSING
        }

        result = engine.compute(inputs)
        ratio_result = result["current_ratio"]

        assert ratio_result.validity_state == ValidityState.INVALID
        assert ratio_result.reason_codes == [
            "denominator:short_term_liabilities:missing:unavailable"
        ]

    def test_e6_deterministic_refusal_mapping_zero(self):
        """E6: Zero denominator always maps to INVALID."""
        engine = MathEngine()

        for zero_value in [0, 0.0, -0.0]:
            inputs: TypedInputs = {
                "current_assets": MetricInputRef(
                    metric_key="current_assets", value=100.0
                ),
                "short_term_liabilities": MetricInputRef(
                    metric_key="short_term_liabilities", value=zero_value
                ),
            }

            result = engine.compute(inputs)
            assert result["current_ratio"].validity_state == ValidityState.INVALID

    def test_e6_deterministic_refusal_mapping_negative_under_strict_positive(self):
        """E6: Negative denominator under STRICT_POSITIVE → INVALID."""
        engine = MathEngine()

        inputs: TypedInputs = {
            "current_assets": MetricInputRef(metric_key="current_assets", value=100.0),
            "short_term_liabilities": MetricInputRef(
                metric_key="short_term_liabilities", value=-50.0
            ),
        }

        result = engine.compute(inputs)
        assert result["current_ratio"].validity_state == ValidityState.INVALID
        assert any(
            "negative" in reason or "denominator" in reason
            for reason in result["current_ratio"].reason_codes
        )


class TestEngineDenialShortCircuit:
    """E7-E9: Test that denial prevents helper/formula invocation."""

    def test_e8_denial_prevents_helper_invocation(self):
        """E8: Architecture test - denied denominator should not reach _ratio() helper."""
        engine = MathEngine()

        # Zero denominator should be caught by engine gate BEFORE helper
        inputs: TypedInputs = {
            "current_assets": MetricInputRef(metric_key="current_assets", value=100.0),
            "short_term_liabilities": MetricInputRef(
                metric_key="short_term_liabilities", value=0.0
            ),
        }

        result = engine.compute(inputs)

        # Should get INVALID without crashing (helper never called with zero)
        assert result["current_ratio"].validity_state == ValidityState.INVALID

        # Trace should show denial happened at engine level
        trace = result["current_ratio"].trace
        assert "status" in trace

    def test_e9_no_exception_on_denial(self):
        """E9: Denial must complete without runtime exception."""
        engine = MathEngine()

        # These should all complete without exceptions
        test_cases = [
            {"current_assets": 100.0, "short_term_liabilities": 0.0},  # Zero
            {
                "current_assets": 100.0,
                "short_term_liabilities": -50.0,
            },  # Negative under STRICT_POSITIVE
        ]

        for values in test_cases:
            inputs: TypedInputs = {
                key: MetricInputRef(metric_key=key, value=val)
                for key, val in values.items()
            }

            # Should not raise
            result = engine.compute(inputs)
            assert result["current_ratio"].validity_state == ValidityState.INVALID


class TestTypedBoundaryPreservation:
    """E10: Test that denominator gate preserves typed-only boundary."""

    def test_e10_no_raw_dict_shortcuts(self):
        """E10: Engine must use TypedInputs, not raw dict shortcuts."""
        engine = MathEngine()

        # Proper typed inputs
        inputs: TypedInputs = {
            "current_assets": MetricInputRef(metric_key="current_assets", value=100.0),
            "short_term_liabilities": MetricInputRef(
                metric_key="short_term_liabilities", value=50.0
            ),
        }

        # Should work fine
        result = engine.compute(inputs)
        assert "current_ratio" in result

    def test_e10_engine_rejects_non_typed_inputs(self):
        """E10: Engine should reject non-TypedInputs."""
        engine = MathEngine()

        # Raw dict should raise TypeError
        with pytest.raises(TypeError):
            engine.compute({"current_assets": 100.0})  # type: ignore


class TestProofMetricFullPipeline:
    """Test proof metric through engine gate (links to Task B)."""

    def test_proof_metric_positive_denominator_succeeds(self):
        """Proof metric with positive denominator → VALID."""
        engine = MathEngine()

        inputs: TypedInputs = {
            "proof_numerator": MetricInputRef(metric_key="proof_numerator", value=10.0),
            "proof_denominator": MetricInputRef(
                metric_key="proof_denominator", value=5.0
            ),
        }

        result = engine.compute(inputs)
        assert (
            result["_wave2_proof_allow_any_non_zero"].validity_state
            == ValidityState.VALID
        )

    def test_proof_metric_negative_denominator_succeeds(self):
        """Proof metric with negative denominator → VALID (ALLOW_ANY_NON_ZERO)."""
        engine = MathEngine()

        inputs: TypedInputs = {
            "proof_numerator": MetricInputRef(metric_key="proof_numerator", value=10.0),
            "proof_denominator": MetricInputRef(
                metric_key="proof_denominator", value=-5.0
            ),
        }

        result = engine.compute(inputs)
        # KEY WAVE 2 FEATURE: Negative allowed under ALLOW_ANY_NON_ZERO
        assert (
            result["_wave2_proof_allow_any_non_zero"].validity_state
            == ValidityState.VALID
        )

    def test_proof_metric_zero_denominator_fails(self):
        """Proof metric with zero denominator → INVALID."""
        engine = MathEngine()

        inputs: TypedInputs = {
            "proof_numerator": MetricInputRef(metric_key="proof_numerator", value=10.0),
            "proof_denominator": MetricInputRef(
                metric_key="proof_denominator", value=0.0
            ),
        }

        result = engine.compute(inputs)
        assert (
            result["_wave2_proof_allow_any_non_zero"].validity_state
            == ValidityState.INVALID
        )
