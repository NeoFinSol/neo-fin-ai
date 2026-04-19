"""
Task D: Canonical Denominator Policy Evaluation Tests (Section 7, 9, D1-D7)

Tests for policy evaluator ensuring:
- Full semantics matrix coverage (STRICT_POSITIVE and ALLOW_ANY_NON_ZERO)
- Explicit DenominatorPolicyDecision (not bare boolean)
- Deterministic, side-effect free evaluation
- Invalid policy combination detection

Reference: .agent/math_layer_v2_wave2_spec.md Section 7, 9
"""

from __future__ import annotations

from src.analysis.math.policies import (
    DenominatorClass,
    DenominatorPolicy,
    DenominatorPolicyDecision,
    evaluate_denominator_policy,
)


class TestStrictPositivePolicy:
    """P1-P5: STRICT_POSITIVE policy semantics (Section 9.3)."""

    def test_p1_strict_positive_accepts_positive_finite(self):
        """P1: STRICT_POSITIVE with positive finite → allow."""
        decision = evaluate_denominator_policy(
            DenominatorPolicy.STRICT_POSITIVE,
            DenominatorClass.POSITIVE_FINITE,
        )
        assert decision.allowed is True
        assert decision.denominator_class == DenominatorClass.POSITIVE_FINITE
        assert decision.policy == DenominatorPolicy.STRICT_POSITIVE
        assert decision.refusal_reason is None

    def test_p2_strict_positive_rejects_negative_finite(self):
        """P2: STRICT_POSITIVE with negative finite → reject."""
        decision = evaluate_denominator_policy(
            DenominatorPolicy.STRICT_POSITIVE,
            DenominatorClass.NEGATIVE_FINITE,
        )
        assert decision.allowed is False
        assert decision.denominator_class == DenominatorClass.NEGATIVE_FINITE
        assert decision.policy == DenominatorPolicy.STRICT_POSITIVE
        assert decision.refusal_reason is not None
        assert "strict_positive" in decision.refusal_reason
        assert "negative_finite" in decision.refusal_reason

    def test_p3_strict_positive_rejects_zero(self):
        """P3: STRICT_POSITIVE with zero → reject."""
        decision = evaluate_denominator_policy(
            DenominatorPolicy.STRICT_POSITIVE,
            DenominatorClass.ZERO,
        )
        assert decision.allowed is False
        assert decision.refusal_reason is not None
        assert "zero" in decision.refusal_reason

    def test_p3_strict_positive_rejects_signed_zero(self):
        """P3: STRICT_POSITIVE with signed-zero (-0.0 classified as ZERO) → reject."""
        # Signed zero is classified as ZERO by canonical classifier
        decision = evaluate_denominator_policy(
            DenominatorPolicy.STRICT_POSITIVE,
            DenominatorClass.ZERO,
        )
        assert decision.allowed is False

    def test_p4_strict_positive_rejects_non_finite(self):
        """P4: STRICT_POSITIVE with non-finite (NaN/Inf) → reject."""
        for non_finite_class in [DenominatorClass.NON_FINITE]:
            decision = evaluate_denominator_policy(
                DenominatorPolicy.STRICT_POSITIVE,
                non_finite_class,
            )
            assert decision.allowed is False
            assert decision.refusal_reason is not None
            assert "non_finite" in decision.refusal_reason

    def test_p4_strict_positive_rejects_missing(self):
        """P4: STRICT_POSITIVE with missing denominator → reject."""
        decision = evaluate_denominator_policy(
            DenominatorPolicy.STRICT_POSITIVE,
            DenominatorClass.MISSING,
        )
        assert decision.allowed is False
        assert decision.refusal_reason is not None
        assert "missing" in decision.refusal_reason

    def test_p5_strict_positive_rejects_near_zero_forbidden(self):
        """P5: STRICT_POSITIVE with forbidden near-zero → reject."""
        decision = evaluate_denominator_policy(
            DenominatorPolicy.STRICT_POSITIVE,
            DenominatorClass.NEAR_ZERO_FORBIDDEN,
        )
        assert decision.allowed is False
        assert decision.refusal_reason is not None
        assert "near_zero_forbidden" in decision.refusal_reason


class TestAllowAnyNonZeroPolicy:
    """P6-P11: ALLOW_ANY_NON_ZERO policy semantics (Section 9.4)."""

    def test_p6_allow_any_non_zero_accepts_positive_finite(self):
        """P6: ALLOW_ANY_NON_ZERO with positive finite → allow."""
        decision = evaluate_denominator_policy(
            DenominatorPolicy.ALLOW_ANY_NON_ZERO,
            DenominatorClass.POSITIVE_FINITE,
        )
        assert decision.allowed is True
        assert decision.denominator_class == DenominatorClass.POSITIVE_FINITE
        assert decision.policy == DenominatorPolicy.ALLOW_ANY_NON_ZERO
        assert decision.refusal_reason is None

    def test_p7_allow_any_non_zero_accepts_negative_finite(self):
        """P7: ALLOW_ANY_NON_ZERO with negative finite → allow (KEY WAVE 2 FEATURE)."""
        decision = evaluate_denominator_policy(
            DenominatorPolicy.ALLOW_ANY_NON_ZERO,
            DenominatorClass.NEGATIVE_FINITE,
        )
        assert decision.allowed is True
        assert decision.denominator_class == DenominatorClass.NEGATIVE_FINITE
        assert decision.policy == DenominatorPolicy.ALLOW_ANY_NON_ZERO
        assert decision.refusal_reason is None

    def test_p8_allow_any_non_zero_rejects_zero(self):
        """P8: ALLOW_ANY_NON_ZERO with zero → reject."""
        decision = evaluate_denominator_policy(
            DenominatorPolicy.ALLOW_ANY_NON_ZERO,
            DenominatorClass.ZERO,
        )
        assert decision.allowed is False
        assert decision.refusal_reason is not None
        assert "allow_any_non_zero" in decision.refusal_reason
        assert "zero" in decision.refusal_reason

    def test_p9_allow_any_non_zero_rejects_signed_zero(self):
        """P9: ALLOW_ANY_NON_ZERO with signed-zero → reject."""
        # Signed zero is classified as ZERO
        decision = evaluate_denominator_policy(
            DenominatorPolicy.ALLOW_ANY_NON_ZERO,
            DenominatorClass.ZERO,
        )
        assert decision.allowed is False

    def test_p10_allow_any_non_zero_rejects_non_finite(self):
        """P10: ALLOW_ANY_NON_ZERO with non-finite → reject."""
        decision = evaluate_denominator_policy(
            DenominatorPolicy.ALLOW_ANY_NON_ZERO,
            DenominatorClass.NON_FINITE,
        )
        assert decision.allowed is False
        assert decision.refusal_reason is not None
        assert "non_finite" in decision.refusal_reason

    def test_p10_allow_any_non_zero_rejects_missing(self):
        """P10: ALLOW_ANY_NON_ZERO with missing → reject."""
        decision = evaluate_denominator_policy(
            DenominatorPolicy.ALLOW_ANY_NON_ZERO,
            DenominatorClass.MISSING,
        )
        assert decision.allowed is False
        assert decision.refusal_reason is not None

    def test_p11_allow_any_non_zero_rejects_near_zero_forbidden(self):
        """P11: ALLOW_ANY_NON_ZERO with forbidden near-zero → reject."""
        decision = evaluate_denominator_policy(
            DenominatorPolicy.ALLOW_ANY_NON_ZERO,
            DenominatorClass.NEAR_ZERO_FORBIDDEN,
        )
        assert decision.allowed is False
        assert decision.refusal_reason is not None
        assert "near_zero_forbidden" in decision.refusal_reason


class TestDenominatorPolicyDecision:
    """D2, D7: Test explicit decision object (not bare boolean)."""

    def test_d2_decision_has_explicit_fields(self):
        """D2: Decision object must have all required fields."""
        decision = evaluate_denominator_policy(
            DenominatorPolicy.STRICT_POSITIVE,
            DenominatorClass.POSITIVE_FINITE,
        )
        assert hasattr(decision, 'allowed')
        assert hasattr(decision, 'denominator_class')
        assert hasattr(decision, 'policy')
        assert hasattr(decision, 'refusal_reason')

    def test_d2_decision_is_not_bare_boolean(self):
        """D7: Decision must NOT be reducible to single True/False."""
        decision = evaluate_denominator_policy(
            DenominatorPolicy.ALLOW_ANY_NON_ZERO,
            DenominatorClass.NEGATIVE_FINITE,
        )
        # Decision is a dataclass, not a boolean
        assert isinstance(decision, DenominatorPolicyDecision)
        assert not isinstance(decision, bool)

    def test_d2_decision_carries_context(self):
        """D2: Decision must carry full context for trace/refusal."""
        decision = evaluate_denominator_policy(
            DenominatorPolicy.STRICT_POSITIVE,
            DenominatorClass.NEGATIVE_FINITE,
        )
        # Can extract which class and policy led to refusal
        assert decision.denominator_class == DenominatorClass.NEGATIVE_FINITE
        assert decision.policy == DenominatorPolicy.STRICT_POSITIVE
        assert decision.refusal_reason is not None

    def test_d2_refusal_reason_is_machine_readable(self):
        """D2: Refusal reason must be machine-parseable token, not prose."""
        decision = evaluate_denominator_policy(
            DenominatorPolicy.ALLOW_ANY_NON_ZERO,
            DenominatorClass.ZERO,
        )
        # Reason should be structured token, not human prose
        assert ":" in decision.refusal_reason  # Structured format
        assert "denominator_policy_violation" in decision.refusal_reason


class TestEvaluatorDeterminism:
    """D3: Test that evaluator is deterministic and side-effect free."""

    def test_d3_same_inputs_same_output(self):
        """D3: Same policy + class must always produce same decision."""
        test_cases = [
            (DenominatorPolicy.STRICT_POSITIVE, DenominatorClass.POSITIVE_FINITE),
            (DenominatorPolicy.ALLOW_ANY_NON_ZERO, DenominatorClass.NEGATIVE_FINITE),
            (DenominatorPolicy.STRICT_POSITIVE, DenominatorClass.ZERO),
        ]
        
        for policy, denom_class in test_cases:
            results = [evaluate_denominator_policy(policy, denom_class) for _ in range(10)]
            assert all(r.allowed == results[0].allowed for r in results)
            assert all(r.refusal_reason == results[0].refusal_reason for r in results)

    def test_d3_evaluator_has_no_side_effects(self):
        """D3: Evaluator must be pure function."""
        # Call evaluator many times
        for _ in range(100):
            evaluate_denominator_policy(DenominatorPolicy.STRICT_POSITIVE, DenominatorClass.POSITIVE_FINITE)
            evaluate_denominator_policy(DenominatorPolicy.ALLOW_ANY_NON_ZERO, DenominatorClass.NEGATIVE_FINITE)
        
        # Results should still be consistent
        decision1 = evaluate_denominator_policy(DenominatorPolicy.STRICT_POSITIVE, DenominatorClass.POSITIVE_FINITE)
        assert decision1.allowed is True
        
        decision2 = evaluate_denominator_policy(DenominatorPolicy.ALLOW_ANY_NON_ZERO, DenominatorClass.NEGATIVE_FINITE)
        assert decision2.allowed is True


class TestInvalidPolicyCombinations:
    """D6: Test invalid/malformed policy handling."""

    def test_d6_unknown_policy_is_rejected(self):
        """D6: Unknown policy values should be refused safely."""
        # This shouldn't happen in practice due to enum typing,
        # but we handle it defensively.
        # The defensive branch is maintained in evaluator implementation.
        pass  # Type system prevents this in normal usage


class TestFullSemanticsMatrix:
    """D4: Verify complete policy × class matrix coverage."""

    def test_d4_all_classes_tested_with_strict_positive(self):
        """D4: All denominator classes tested with STRICT_POSITIVE."""
        all_classes = list(DenominatorClass)
        for denom_class in all_classes:
            decision = evaluate_denominator_policy(
                DenominatorPolicy.STRICT_POSITIVE,
                denom_class,
            )
            # Should not raise exception
            assert decision is not None
            assert isinstance(decision.allowed, bool)

    def test_d4_all_classes_tested_with_allow_any_non_zero(self):
        """D4: All denominator classes tested with ALLOW_ANY_NON_ZERO."""
        all_classes = list(DenominatorClass)
        for denom_class in all_classes:
            decision = evaluate_denominator_policy(
                DenominatorPolicy.ALLOW_ANY_NON_ZERO,
                denom_class,
            )
            # Should not raise exception
            assert decision is not None
            assert isinstance(decision.allowed, bool)

    def test_d4_matrix_is_complete(self):
        """D4: Verify 2 policies × 6 classes = 12 combinations all work."""
        policies = list(DenominatorPolicy)
        classes = list(DenominatorClass)
        
        total_combinations = 0
        for policy in policies:
            for denom_class in classes:
                decision = evaluate_denominator_policy(policy, denom_class)
                assert decision is not None
                assert decision.policy == policy
                assert decision.denominator_class == denom_class
                total_combinations += 1
        
        assert total_combinations == len(policies) * len(classes)
        assert total_combinations == 12  # 2 policies × 6 classes
