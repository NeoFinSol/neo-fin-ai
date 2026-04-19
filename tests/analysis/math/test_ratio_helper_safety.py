"""
Task F: Canonical Ratio Helper Fail-Safe Hardening Tests (Section 14, F1-F11)

Tests for _ratio() helper local no-crash barrier:
- Direct unsafe invocation cannot crash
- All guard conditions reject appropriately
- No raw divide before guards pass
- Structured refusal instead of exceptions

Reference: .agent/math_layer_v2_wave2_spec.md Section 14
"""

from __future__ import annotations

import math

import pytest

from src.analysis.math.contracts import MetricInputRef, TypedInputs
from src.analysis.math.reason_codes import (
    MATH_FORMULA_DENOMINATOR_NEAR_ZERO,
    MATH_FORMULA_DENOMINATOR_ZERO,
    MATH_FORMULA_INPUT_NON_FINITE,
    MATH_FORMULA_INPUTS_MISSING,
)
from src.analysis.math.registry import _ratio


class TestHelperMissingInputGuards:
    """F2: Test missing numerator/denominator guards."""

    def test_f2_missing_numerator_returns_refusal(self):
        """F2: Missing numerator → structured refusal, no exception."""
        ratio_fn = _ratio("num", "den")
        inputs: TypedInputs = {
            "den": MetricInputRef(metric_key="den", value=5.0),
        }

        result = ratio_fn(inputs)
        assert result.value is None
        assert MATH_FORMULA_INPUTS_MISSING in result.extra_reason_codes
        assert result.trace.get("guard_failure") == "missing_numerator"

    def test_f2_missing_denominator_returns_refusal(self):
        """F2: Missing denominator → structured refusal, no exception."""
        ratio_fn = _ratio("num", "den")
        inputs: TypedInputs = {
            "num": MetricInputRef(metric_key="num", value=10.0),
        }

        result = ratio_fn(inputs)
        assert result.value is None
        assert MATH_FORMULA_INPUTS_MISSING in result.extra_reason_codes
        assert result.trace.get("guard_failure") == "missing_denominator"

    def test_f2_both_missing_returns_refusal(self):
        """F2: Both missing → structured refusal."""
        ratio_fn = _ratio("num", "den")
        inputs: TypedInputs = {}

        result = ratio_fn(inputs)
        assert result.value is None
        assert MATH_FORMULA_INPUTS_MISSING in result.extra_reason_codes


class TestHelperNonFiniteGuards:
    """F3: Test non-finite input guards."""

    def test_f3_nan_numerator_returns_refusal(self):
        """F3: NaN numerator → structured refusal."""
        ratio_fn = _ratio("num", "den")
        inputs: TypedInputs = {
            "num": MetricInputRef(metric_key="num", value=float("nan")),
            "den": MetricInputRef(metric_key="den", value=5.0),
        }

        result = ratio_fn(inputs)
        assert result.value is None
        assert MATH_FORMULA_INPUT_NON_FINITE in result.extra_reason_codes
        assert result.trace.get("guard_failure") == "non_finite_numerator"

    def test_f3_nan_denominator_returns_refusal(self):
        """F3: NaN denominator → structured refusal."""
        ratio_fn = _ratio("num", "den")
        inputs: TypedInputs = {
            "num": MetricInputRef(metric_key="num", value=10.0),
            "den": MetricInputRef(metric_key="den", value=float("nan")),
        }

        result = ratio_fn(inputs)
        assert result.value is None
        assert MATH_FORMULA_INPUT_NON_FINITE in result.extra_reason_codes

    def test_f3_inf_numerator_returns_refusal(self):
        """F3: +Inf numerator → structured refusal."""
        ratio_fn = _ratio("num", "den")
        inputs: TypedInputs = {
            "num": MetricInputRef(metric_key="num", value=float("inf")),
            "den": MetricInputRef(metric_key="den", value=5.0),
        }

        result = ratio_fn(inputs)
        assert result.value is None
        assert MATH_FORMULA_INPUT_NON_FINITE in result.extra_reason_codes

    def test_f3_inf_denominator_returns_refusal(self):
        """F3: -Inf denominator → structured refusal."""
        ratio_fn = _ratio("num", "den")
        inputs: TypedInputs = {
            "num": MetricInputRef(metric_key="num", value=10.0),
            "den": MetricInputRef(metric_key="den", value=float("-inf")),
        }

        result = ratio_fn(inputs)
        assert result.value is None
        assert MATH_FORMULA_INPUT_NON_FINITE in result.extra_reason_codes


class TestHelperZeroDenominatorGuards:
    """F4: Test zero/signed-zero denominator guards."""

    def test_f4_zero_denominator_returns_refusal(self):
        """F4: Zero denominator → structured refusal."""
        ratio_fn = _ratio("num", "den")
        inputs: TypedInputs = {
            "num": MetricInputRef(metric_key="num", value=10.0),
            "den": MetricInputRef(metric_key="den", value=0.0),
        }

        result = ratio_fn(inputs)
        assert result.value is None
        assert MATH_FORMULA_DENOMINATOR_ZERO in result.extra_reason_codes
        assert result.trace.get("guard_failure") == "zero_denominator"

    def test_f4_signed_zero_denominator_returns_refusal(self):
        """F4: Signed-zero (-0.0) denominator → structured refusal."""
        ratio_fn = _ratio("num", "den")
        inputs: TypedInputs = {
            "num": MetricInputRef(metric_key="num", value=10.0),
            "den": MetricInputRef(metric_key="den", value=-0.0),
        }

        result = ratio_fn(inputs)
        assert result.value is None
        assert MATH_FORMULA_DENOMINATOR_ZERO in result.extra_reason_codes


class TestHelperNearZeroDenominatorGuards:
    """F5: Test forbidden near-zero denominator guard."""

    def test_f5_near_zero_positive_denominator_returns_refusal(self):
        """F5: Near-zero positive denominator → structured refusal."""
        ratio_fn = _ratio("num", "den")
        inputs: TypedInputs = {
            "num": MetricInputRef(metric_key="num", value=10.0),
            "den": MetricInputRef(metric_key="den", value=1e-10),  # Below 1e-9 epsilon
        }

        result = ratio_fn(inputs)
        assert result.value is None
        assert MATH_FORMULA_DENOMINATOR_NEAR_ZERO in result.extra_reason_codes
        assert result.trace.get("guard_failure") == "near_zero_denominator"

    def test_f5_near_zero_negative_denominator_returns_refusal(self):
        """F5: Near-zero negative denominator → structured refusal."""
        ratio_fn = _ratio("num", "den")
        inputs: TypedInputs = {
            "num": MetricInputRef(metric_key="num", value=10.0),
            "den": MetricInputRef(metric_key="den", value=-1e-10),
        }

        result = ratio_fn(inputs)
        assert result.value is None
        assert MATH_FORMULA_DENOMINATOR_NEAR_ZERO in result.extra_reason_codes


class TestHelperValidDivision:
    """Test that valid inputs still work after hardening."""

    def test_valid_positive_division_succeeds(self):
        """Valid positive inputs → successful division."""
        ratio_fn = _ratio("num", "den")
        inputs: TypedInputs = {
            "num": MetricInputRef(metric_key="num", value=10.0),
            "den": MetricInputRef(metric_key="den", value=5.0),
        }

        result = ratio_fn(inputs)
        assert result.value == 2.0
        assert result.trace.get("guard_status") == "passed"

    def test_valid_negative_denominator_succeeds(self):
        """Valid negative denominator → successful division."""
        ratio_fn = _ratio("num", "den")
        inputs: TypedInputs = {
            "num": MetricInputRef(metric_key="num", value=10.0),
            "den": MetricInputRef(metric_key="den", value=-5.0),
        }

        result = ratio_fn(inputs)
        assert result.value == -2.0
        assert result.trace.get("guard_status") == "passed"

    def test_numerator_zero_with_valid_denominator_succeeds(self):
        """R7: Numerator zero with valid denominator → valid success (result is 0)."""
        ratio_fn = _ratio("num", "den")
        inputs: TypedInputs = {
            "num": MetricInputRef(metric_key="num", value=0.0),
            "den": MetricInputRef(metric_key="den", value=-5.0),
        }

        result = ratio_fn(inputs)
        assert result.value == 0.0
        assert result.trace.get("guard_status") == "passed"


class TestHelperNoCrashGuarantee:
    """F10-F11: Direct helper no-crash regression tests."""

    def test_r1_direct_call_zero_denominator_no_crash(self):
        """R1: Direct helper call with zero denominator → no exception."""
        ratio_fn = _ratio("num", "den")
        inputs: TypedInputs = {
            "num": MetricInputRef(metric_key="num", value=10.0),
            "den": MetricInputRef(metric_key="den", value=0.0),
        }

        # Should not raise ZeroDivisionError
        result = ratio_fn(inputs)
        assert result.value is None

    def test_r2_direct_call_signed_zero_no_crash(self):
        """R2: Direct helper call with signed-zero → no exception."""
        ratio_fn = _ratio("num", "den")
        inputs: TypedInputs = {
            "num": MetricInputRef(metric_key="num", value=10.0),
            "den": MetricInputRef(metric_key="den", value=-0.0),
        }

        result = ratio_fn(inputs)
        assert result.value is None

    def test_r3_direct_call_missing_denominator_no_crash(self):
        """R3: Direct helper call with missing denominator → no exception."""
        ratio_fn = _ratio("num", "den")
        inputs: TypedInputs = {
            "num": MetricInputRef(metric_key="num", value=10.0),
        }

        result = ratio_fn(inputs)
        assert result.value is None

    def test_r4_direct_call_non_finite_no_crash(self):
        """R4: Direct helper call with non-finite → no exception."""
        ratio_fn = _ratio("num", "den")

        for bad_value in [float("nan"), float("inf"), float("-inf")]:
            inputs: TypedInputs = {
                "num": MetricInputRef(metric_key="num", value=10.0),
                "den": MetricInputRef(metric_key="den", value=bad_value),
            }

            result = ratio_fn(inputs)
            assert result.value is None

    def test_r5_direct_call_near_zero_no_crash(self):
        """R5: Direct helper call with near-zero → no exception."""
        ratio_fn = _ratio("num", "den")
        inputs: TypedInputs = {
            "num": MetricInputRef(metric_key="num", value=10.0),
            "den": MetricInputRef(metric_key="den", value=1e-15),
        }

        result = ratio_fn(inputs)
        assert result.value is None

    def test_r6_direct_call_valid_negative_succeeds(self):
        """R6: Direct helper call with valid negative denominator → success."""
        ratio_fn = _ratio("num", "den")
        inputs: TypedInputs = {
            "num": MetricInputRef(metric_key="num", value=10.0),
            "den": MetricInputRef(metric_key="den", value=-5.0),
        }

        result = ratio_fn(inputs)
        assert result.value == -2.0

    def test_f6_no_raw_divide_before_guards(self):
        """F6: Verify division only happens after all guards pass."""
        ratio_fn = _ratio("num", "den")

        # These should ALL return refusal without attempting division
        dangerous_inputs = [
            {"num": 10.0, "den": 0.0},
            {"num": 10.0, "den": float("nan")},
            {"num": 10.0, "den": float("inf")},
            {"num": float("nan"), "den": 5.0},
        ]

        for values in dangerous_inputs:
            inputs: TypedInputs = {
                key: MetricInputRef(metric_key=key, value=val)
                for key, val in values.items()
            }

            # Should complete without exception
            result = ratio_fn(inputs)
            # Should refuse (not attempt division)
            assert result.value is None or result.trace.get("guard_failure") is not None
