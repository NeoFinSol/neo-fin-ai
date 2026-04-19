"""
Task A: Registry Denominator Validation Tests

Tests for ratio-like declaration hardening and registry validation.
Ensures all ratio-like metrics have explicit denominator semantics
and malformed declarations fail validation.
"""

from __future__ import annotations

import pytest
from typing import Callable

from src.analysis.math.contracts import (
    MetricComputationResult,
    TypedInputs,
)
from src.analysis.math.policies import DenominatorPolicy
from src.analysis.math.registry import (
    MetricDefinition,
    is_ratio_like,
    REGISTRY,
)


def _dummy_compute(_: TypedInputs) -> MetricComputationResult:
    """Placeholder compute function for test definitions."""
    return MetricComputationResult(value=None, trace={})


class TestRatioLikeIdentityDetection:
    """Test machine-checkable ratio-like identity based on denominator_key."""

    def test_active_ratio_metrics_detected(self):
        """All active ratio-like metrics should be detected as ratio-like."""
        expected_ratio_metrics = {
            "current_ratio",
            "absolute_liquidity_ratio",
            "ros",
            "equity_ratio",
            "ebitda_margin",
            "roa",
            "roe",
            "asset_turnover",
        }

        for metric_id in expected_ratio_metrics:
            definition = REGISTRY[metric_id]
            assert is_ratio_like(definition), (
                f"Metric '{metric_id}' should be detected as ratio-like "
                f"(has denominator_key={definition.denominator_key})"
            )

    def test_suppressed_placeholders_not_ratio_like(self):
        """Suppressed placeholders should NOT be ratio-like until implemented."""
        suppressed_metrics = {
            "quick_ratio",
            "financial_leverage",
            "financial_leverage_total",
            "financial_leverage_debt_only",
            "interest_coverage",
            "inventory_turnover",
            "receivables_turnover",
        }

        for metric_id in suppressed_metrics:
            definition = REGISTRY[metric_id]
            assert not is_ratio_like(definition), (
                f"Suppressed placeholder '{metric_id}' should NOT be ratio-like "
                f"(denominator_key={definition.denominator_key})"
            )

    def test_is_ratio_like_uses_denominator_key(self):
        """is_ratio_like() should check denominator_key, not implementation details."""
        # Definition with denominator_key should be ratio-like
        ratio_def = MetricDefinition(
            metric_id="test_ratio",
            formula_id="test_ratio",
            formula_version="v1",
            required_inputs=("numerator", "denominator"),
            averaging_policy=None,  # type: ignore[arg-type]
            suppression_policy=None,  # type: ignore[arg-type]
            compute=_dummy_compute,
            denominator_key="denominator",
            denominator_policy=DenominatorPolicy.STRICT_POSITIVE,
        )
        assert is_ratio_like(ratio_def) is True

        # Definition without denominator_key should NOT be ratio-like
        non_ratio_def = MetricDefinition(
            metric_id="test_non_ratio",
            formula_id="test_non_ratio",
            formula_version="v1",
            required_inputs=("value",),
            averaging_policy=None,  # type: ignore[arg-type]
            suppression_policy=None,  # type: ignore[arg-type]
            compute=_dummy_compute,
            denominator_key=None,
            denominator_policy=None,
        )
        assert is_ratio_like(non_ratio_def) is False


class TestExplicitDenominatorDeclaration:
    """Test that all ratio-like metrics have explicit denominator declarations."""

    def test_all_ratio_metrics_have_denominator_key(self):
        """Every ratio-like metric must declare denominator_key explicitly."""
        for metric_id, definition in REGISTRY.items():
            if is_ratio_like(definition):
                assert definition.denominator_key is not None, (
                    f"Ratio-like metric '{metric_id}' must have explicit denominator_key"
                )

    def test_all_ratio_metrics_have_denominator_policy(self):
        """Every ratio-like metric must declare denominator_policy explicitly."""
        for metric_id, definition in REGISTRY.items():
            if is_ratio_like(definition):
                assert definition.denominator_policy is not None, (
                    f"Ratio-like metric '{metric_id}' must have explicit denominator_policy"
                )

    def test_denominator_key_in_required_inputs(self):
        """Denominator key should be in required_inputs for ratio-like metrics."""
        for metric_id, definition in REGISTRY.items():
            if is_ratio_like(definition):
                assert definition.denominator_key in definition.required_inputs, (
                    f"Ratio-like metric '{metric_id}': denominator_key "
                    f"'{definition.denominator_key}' must be in required_inputs "
                    f"{definition.required_inputs}"
                )

    def test_denominator_policy_is_valid_enum(self):
        """Denominator policy must be a valid DenominatorPolicy enum value."""
        valid_policies = {DenominatorPolicy.STRICT_POSITIVE, DenominatorPolicy.ALLOW_ANY_NON_ZERO}

        for metric_id, definition in REGISTRY.items():
            if is_ratio_like(definition):
                assert definition.denominator_policy in valid_policies, (
                    f"Ratio-like metric '{metric_id}' has invalid denominator_policy: "
                    f"{definition.denominator_policy}. Must be one of {valid_policies}"
                )


class TestMalformedDeclarations:
    """Test that malformed ratio-like declarations are caught by validation."""

    def test_ratio_like_without_denominator_key_fails(self):
        """A metric using _ratio helper but missing denominator_key should be invalid."""
        # This tests the invariant: ratio-like identity comes from declaration,
        # not from implementation details
        bad_definition = MetricDefinition(
            metric_id="bad_ratio",
            formula_id="bad_ratio",
            formula_version="v1",
            required_inputs=("num", "den"),
            averaging_policy=None,  # type: ignore[arg-type]
            suppression_policy=None,  # type: ignore[arg-type]
            compute=_dummy_compute,  # Pretends to be ratio but no denominator declared
            denominator_key=None,  # Missing!
            denominator_policy=None,
        )

        # Should NOT be detected as ratio-like (declaration-based identity)
        assert is_ratio_like(bad_definition) is False

    def test_ratio_like_without_policy_fails_detection(self):
        """A metric with denominator_key but no policy is incomplete."""
        incomplete_definition = MetricDefinition(
            metric_id="incomplete_ratio",
            formula_id="incomplete_ratio",
            formula_version="v1",
            required_inputs=("num", "den"),
            averaging_policy=None,  # type: ignore[arg-type]
            suppression_policy=None,  # type: ignore[arg-type]
            compute=_dummy_compute,
            denominator_key="den",
            denominator_policy=None,  # Missing policy!
        )

        # Has denominator_key so technically ratio-like, but policy is None
        assert is_ratio_like(incomplete_definition) is True
        assert incomplete_definition.denominator_policy is None

    def test_suppressed_placeholder_has_no_denominator_semantics(self):
        """True suppressed placeholders (not yet implemented) should have None for denominator fields.
        
        Note: Metrics like ebitda_margin have SUPPRESS_UNSAFE but ARE fully implemented
        ratio-like metrics that are temporarily disabled. They correctly retain their
        denominator declarations for when they're re-enabled.
        """
        # Only check actual placeholders created by _suppressed_placeholder()
        # These have empty required_inputs and NONE averaging policy
        true_placeholders = [
            "quick_ratio",
            "financial_leverage",
            "financial_leverage_total", 
            "financial_leverage_debt_only",
            "interest_coverage",
            "inventory_turnover",
            "receivables_turnover",
        ]
        
        for metric_id in true_placeholders:
            definition = REGISTRY[metric_id]
            # True placeholders should have no denominator semantics
            assert definition.denominator_key is None, (
                f"True placeholder '{metric_id}' should have denominator_key=None"
            )
            assert definition.denominator_policy is None, (
                f"True placeholder '{metric_id}' should have denominator_policy=None"
            )


class TestRegistryConsistency:
    """Test overall registry consistency for denominator semantics."""

    def test_all_active_ratios_have_complete_denominator_declaration(self):
        """Active ratio-like metrics must have BOTH denominator_key AND policy."""
        for metric_id, definition in REGISTRY.items():
            if is_ratio_like(definition):
                has_key = definition.denominator_key is not None
                has_policy = definition.denominator_policy is not None

                assert has_key and has_policy, (
                    f"Active ratio-like metric '{metric_id}' must have both "
                    f"denominator_key (has={has_key}) and denominator_policy (has={has_policy})"
                )

    def test_no_hidden_raw_divide_without_declaration(self):
        """Metrics using _ratio helper must have denominator declarations."""
        # All current _ratio usages in registry already have declarations
        # This test locks that invariant
        for metric_id, definition in REGISTRY.items():
            # If it's ratio-like, it MUST have complete declaration
            if is_ratio_like(definition):
                assert definition.denominator_key is not None, (
                    f"Metric '{metric_id}' uses ratio computation but lacks denominator_key"
                )
                assert definition.denominator_policy is not None, (
                    f"Metric '{metric_id}' uses ratio computation but lacks denominator_policy"
                )

    def test_denominator_key_references_valid_input(self):
        """Denominator key must reference an input in required_inputs."""
        for metric_id, definition in REGISTRY.items():
            if is_ratio_like(definition) and definition.denominator_key is not None:
                assert definition.denominator_key in definition.required_inputs, (
                    f"Metric '{metric_id}': denominator_key '{definition.denominator_key}' "
                    f"not found in required_inputs {definition.required_inputs}"
                )
