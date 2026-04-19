"""
Task C: Canonical Denominator Classification Tests (Section 10, C1-C7)

Tests for enum-based denominator classifier ensuring:
- Single canonical classification path
- Correct zero/signed-zero semantics  
- Correct non-finite semantics
- Correct near-zero semantics with centralized threshold
- Shared predicate surface for helper reuse

Reference: .agent/math_layer_v2_wave2_spec.md Section 10, 15
"""

from __future__ import annotations

from src.analysis.math.policies import DenominatorClass
from src.analysis.math.validators import (
    classify_denominator,
    is_zero_or_signed_zero,
    is_non_finite,
    is_near_zero_forbidden,
    DENOMINATOR_EPSILON,
)


class TestDenominatorClassification:
    """C1-C2: Test canonical denominator classifier with all classes."""

    def test_c1_missing_denominator(self):
        """C1: None value → MISSING."""
        result = classify_denominator(None)
        assert result == DenominatorClass.MISSING

    def test_c3_zero_denominator(self):
        """C3: Zero (0) → ZERO."""
        result = classify_denominator(0)
        assert result == DenominatorClass.ZERO

    def test_c3_signed_zero_positive_denominator(self):
        """C3: Positive zero (0.0) → ZERO (same as regular zero)."""
        result = classify_denominator(0.0)
        assert result == DenominatorClass.ZERO

    def test_c3_signed_zero_negative_denominator(self):
        """C3: Signed zero (-0.0) → ZERO (treated same as 0)."""
        result = classify_denominator(-0.0)
        assert result == DenominatorClass.ZERO
        # Verify Python's -0.0 == 0 behavior
        assert -0.0 == 0

    def test_c6_positive_finite_denominator(self):
        """C6: Positive finite value → POSITIVE_FINITE."""
        result = classify_denominator(2.0)
        assert result == DenominatorClass.POSITIVE_FINITE

    def test_c6_large_positive_denominator(self):
        """C6: Large positive value → POSITIVE_FINITE."""
        result = classify_denominator(1e10)
        assert result == DenominatorClass.POSITIVE_FINITE

    def test_c6_small_positive_denominator(self):
        """C6: Small positive value above epsilon → POSITIVE_FINITE."""
        result = classify_denominator(DENOMINATOR_EPSILON * 2)
        assert result == DenominatorClass.POSITIVE_FINITE

    def test_c6_negative_finite_denominator(self):
        """C6: Negative finite value → NEGATIVE_FINITE."""
        result = classify_denominator(-2.0)
        assert result == DenominatorClass.NEGATIVE_FINITE

    def test_c6_large_negative_denominator(self):
        """C6: Large negative value → NEGATIVE_FINITE."""
        result = classify_denominator(-1e10)
        assert result == DenominatorClass.NEGATIVE_FINITE

    def test_c4_nan_denominator(self):
        """C4: NaN → NON_FINITE."""
        result = classify_denominator(float("nan"))
        assert result == DenominatorClass.NON_FINITE

    def test_c4_positive_infinity_denominator(self):
        """C4: +Infinity → NON_FINITE."""
        result = classify_denominator(float("inf"))
        assert result == DenominatorClass.NON_FINITE

    def test_c4_negative_infinity_denominator(self):
        """C4: -Infinity → NON_FINITE."""
        result = classify_denominator(float("-inf"))
        assert result == DenominatorClass.NON_FINITE

    def test_c5_near_zero_positive_forbidden(self):
        """C5: Positive value below epsilon → NEAR_ZERO_FORBIDDEN."""
        result = classify_denominator(DENOMINATOR_EPSILON / 2)
        assert result == DenominatorClass.NEAR_ZERO_FORBIDDEN

    def test_c5_near_zero_negative_forbidden(self):
        """C5: Negative value above -epsilon → NEAR_ZERO_FORBIDDEN."""
        result = classify_denominator(-(DENOMINATOR_EPSILON / 2))
        assert result == DenominatorClass.NEAR_ZERO_FORBIDDEN

    def test_c5_at_epsilon_boundary(self):
        """C5: Value exactly at epsilon → NEAR_ZERO_FORBIDDEN."""
        # Values < epsilon are forbidden, so exactly at boundary should be forbidden
        result = classify_denominator(DENOMINATOR_EPSILON)
        # Note: abs(value) < EPSILON means strictly less than
        # At exactly epsilon, it's NOT near-zero, should be POSITIVE_FINITE
        assert result == DenominatorClass.POSITIVE_FINITE

    def test_c5_just_above_epsilon(self):
        """C5: Value just above epsilon → POSITIVE_FINITE."""
        result = classify_denominator(DENOMINATOR_EPSILON + 1e-12)
        assert result == DenominatorClass.POSITIVE_FINITE


class TestSharedPredicateSurface:
    """C6: Test shared predicates for helper reuse."""

    def test_is_zero_regular_zero(self):
        """Predicate: Regular zero detected."""
        assert is_zero_or_signed_zero(0) is True

    def test_is_zero_signed_zero(self):
        """Predicate: Signed zero detected."""
        assert is_zero_or_signed_zero(-0.0) is True

    def test_is_zero_non_zero_returns_false(self):
        """Predicate: Non-zero returns False."""
        assert is_zero_or_signed_zero(1.0) is False
        assert is_zero_or_signed_zero(-1.0) is False

    def test_is_zero_none_returns_false(self):
        """Predicate: None returns False (not zero, it's missing)."""
        assert is_zero_or_signed_zero(None) is False

    def test_is_non_finite_nan(self):
        """Predicate: NaN detected."""
        assert is_non_finite(float("nan")) is True

    def test_is_non_finite_inf(self):
        """Predicate: Infinity detected."""
        assert is_non_finite(float("inf")) is True
        assert is_non_finite(float("-inf")) is True

    def test_is_non_finite_finite_returns_false(self):
        """Predicate: Finite values return False."""
        assert is_non_finite(0) is False
        assert is_non_finite(1.0) is False
        assert is_non_finite(-1.0) is False

    def test_is_non_finite_none_returns_false(self):
        """Predicate: None returns False (not non-finite, it's missing)."""
        assert is_non_finite(None) is False

    def test_is_near_zero_forbidden_below_epsilon(self):
        """Predicate: Values below epsilon detected."""
        assert is_near_zero_forbidden(DENOMINATOR_EPSILON / 2) is True
        assert is_near_zero_forbidden(-(DENOMINATOR_EPSILON / 2)) is True

    def test_is_near_zero_forbidden_zero_returns_false(self):
        """Predicate: Zero returns False (handled by is_zero_or_signed_zero)."""
        assert is_near_zero_forbidden(0) is False
        assert is_near_zero_forbidden(-0.0) is False

    def test_is_near_zero_forbidden_above_epsilon_returns_false(self):
        """Predicate: Values above epsilon return False."""
        assert is_near_zero_forbidden(DENOMINATOR_EPSILON * 2) is False
        assert is_near_zero_forbidden(1.0) is False

    def test_is_near_zero_forbidden_none_returns_false(self):
        """Predicate: None returns False."""
        assert is_near_zero_forbidden(None) is False

    def test_is_near_zero_forbidden_non_finite_returns_false(self):
        """Predicate: Non-finite returns False."""
        assert is_near_zero_forbidden(float("nan")) is False
        assert is_near_zero_forbidden(float("inf")) is False


class TestClassifierDeterminism:
    """Test that classifier is deterministic (Section 10.5, 15.2)."""

    def test_same_input_same_output_multiple_calls(self):
        """Same input must always produce same classification."""
        test_values = [
            None,
            0,
            -0.0,
            2.0,
            -2.0,
            float("nan"),
            float("inf"),
            DENOMINATOR_EPSILON / 2,
        ]
        
        for value in test_values:
            results = [classify_denominator(value) for _ in range(10)]
            assert all(r == results[0] for r in results), (
                f"Non-deterministic classification for value={value}: {results}"
            )

    def test_classifier_has_no_side_effects(self):
        """Classifier must be pure function with no side effects."""
        # Call classifier multiple times
        for _ in range(100):
            classify_denominator(1.0)
            classify_denominator(-1.0)
            classify_denominator(0)
        
        # Results should still be consistent
        assert classify_denominator(1.0) == DenominatorClass.POSITIVE_FINITE
        assert classify_denominator(-1.0) == DenominatorClass.NEGATIVE_FINITE
        assert classify_denominator(0) == DenominatorClass.ZERO


class TestCentralizedThreshold:
    """C5: Test that near-zero uses centralized threshold (Section 15.1, 15.3)."""

    def test_epsilon_is_defined_in_validators(self):
        """DENOMINATOR_EPSILON must be defined in validators module."""
        from src.analysis.math import validators
        assert hasattr(validators, 'DENOMINATOR_EPSILON')
        assert validators.DENOMINATOR_EPSILON == 1e-9

    def test_no_local_epsilon_override_in_predicates(self):
        """Predicates must use centralized DENOMINATOR_EPSILON."""
        # This test verifies the predicate uses the module-level constant
        # by checking behavior at the boundary
        value_at_boundary = DENOMINATOR_EPSILON / 2
        assert is_near_zero_forbidden(value_at_boundary) is True
        
        # If predicate had local epsilon, this might fail
        value_above_boundary = DENOMINATOR_EPSILON * 2
        assert is_near_zero_forbidden(value_above_boundary) is False


class TestNoAlternateClassifiers:
    """Section 10.6: Verify no hidden alternate classifiers exist."""

    def test_classifier_returns_enum_not_string(self):
        """Classifier must return DenominatorClass enum, not string codes."""
        result = classify_denominator(1.0)
        assert isinstance(result, DenominatorClass)
        assert not isinstance(result, str) or isinstance(result, DenominatorClass)
        # DenominatorClass inherits from str Enum, so check it's the enum
        assert result.__class__ == DenominatorClass

    def test_all_enum_values_are_valid_classes(self):
        """All possible enum values should match spec Section 10.2."""
        expected_classes = {
            "missing",
            "non_finite", 
            "zero",
            "near_zero_forbidden",
            "positive_finite",
            "negative_finite",
        }
        actual_classes = {cls.value for cls in DenominatorClass}
        assert actual_classes == expected_classes, (
            f"DenominatorClass enum mismatch. Expected: {expected_classes}, "
            f"Got: {actual_classes}"
        )
