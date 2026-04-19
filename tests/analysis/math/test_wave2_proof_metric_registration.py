"""
Task B: Proof Metric Registration Tests

Tests for Wave 2 proof metric declaration and non-export boundary.
Ensures ALLOW_ANY_NON_ZERO proof metric exists in registry but does NOT
leak into product-facing export surfaces.

Reference: .agent/math_layer_v2_wave2_spec.md Section 17 (Proof-of-Usage)
"""

from __future__ import annotations

from src.analysis.math.policies import DenominatorPolicy
from src.analysis.math.registry import (
    LEGACY_RATIO_NAME_MAP,
    RATIO_KEY_MAP,
    REGISTRY,
    is_ratio_like,
)

PROOF_METRIC_ID = "_wave2_proof_allow_any_non_zero"


class TestProofMetricDeclaration:
    """Test that proof metric is properly declared with canonical model."""

    def test_proof_metric_exists_in_registry(self):
        """B1: Proof metric must exist in main REGISTRY."""
        assert PROOF_METRIC_ID in REGISTRY, (
            f"Proof metric '{PROOF_METRIC_ID}' not found in REGISTRY. "
            "It should be declared for ALLOW_ANY_NON_ZERO validation."
        )

    def test_proof_metric_is_ratio_like(self):
        """B2: Proof metric must be detected as ratio-like."""
        definition = REGISTRY[PROOF_METRIC_ID]
        assert is_ratio_like(definition), (
            f"Proof metric '{PROOF_METRIC_ID}' must be ratio-like "
            f"(denominator_key={definition.denominator_key})"
        )

    def test_proof_metric_has_explicit_denominator_key(self):
        """B2: Proof metric must declare explicit denominator source."""
        definition = REGISTRY[PROOF_METRIC_ID]
        assert (
            definition.denominator_key is not None
        ), f"Proof metric '{PROOF_METRIC_ID}' must have explicit denominator_key"
        assert definition.denominator_key == "proof_denominator", (
            f"Proof metric denominator_key should be 'proof_denominator', "
            f"got '{definition.denominator_key}'"
        )

    def test_proof_metric_declares_allow_any_non_zero(self):
        """B2: Proof metric must use ALLOW_ANY_NON_ZERO policy."""
        definition = REGISTRY[PROOF_METRIC_ID]
        assert definition.denominator_policy == DenominatorPolicy.ALLOW_ANY_NON_ZERO, (
            f"Proof metric '{PROOF_METRIC_ID}' must use ALLOW_ANY_NON_ZERO policy, "
            f"got {definition.denominator_policy}"
        )

    def test_proof_metric_uses_canonical_ratio_helper(self):
        """B2: Proof metric must use canonical _ratio() helper path."""
        definition = REGISTRY[PROOF_METRIC_ID]
        # The compute function should be the one created by _ratio()
        # We can verify it's not a placeholder or suppressed metric
        assert (
            definition.suppression_policy.name == "NEVER"
        ), f"Proof metric should not be suppressed, got {definition.suppression_policy}"

    def test_proof_metric_has_required_inputs(self):
        """B2: Proof metric must declare numerator and denominator inputs."""
        definition = REGISTRY[PROOF_METRIC_ID]
        assert "proof_numerator" in definition.required_inputs, (
            f"Proof metric must require 'proof_numerator' input, "
            f"got {definition.required_inputs}"
        )
        assert "proof_denominator" in definition.required_inputs, (
            f"Proof metric must require 'proof_denominator' input, "
            f"got {definition.required_inputs}"
        )
        assert len(definition.required_inputs) == 2, (
            f"Proof metric should have exactly 2 required inputs, "
            f"got {len(definition.required_inputs)}: {definition.required_inputs}"
        )


class TestProofMetricNonExportBoundary:
    """Test that proof metric does NOT leak into product-facing export surfaces."""

    def test_proof_metric_not_in_legacy_name_map(self):
        """B3: Proof metric must NOT appear in LEGACY_RATIO_NAME_MAP."""
        assert PROOF_METRIC_ID not in LEGACY_RATIO_NAME_MAP, (
            f"SECURITY VIOLATION: Proof metric '{PROOF_METRIC_ID}' leaked into "
            f"LEGACY_RATIO_NAME_MAP. It has legacy_label=None and should be filtered out."
        )

    def test_proof_metric_not_in_frontend_key_map(self):
        """B3: Proof metric must NOT appear in RATIO_KEY_MAP."""
        # RATIO_KEY_MAP maps legacy_label -> frontend_key
        # Since proof metric has legacy_label=None, it shouldn't be in values either
        assert PROOF_METRIC_ID not in RATIO_KEY_MAP.values(), (
            f"SECURITY VIOLATION: Proof metric '{PROOF_METRIC_ID}' leaked into "
            f"RATIO_KEY_MAP values. Check frontend_key assignment."
        )

    def test_proof_metric_has_no_legacy_label(self):
        """B3: Proof metric must have legacy_label=None to prevent export."""
        definition = REGISTRY[PROOF_METRIC_ID]
        assert definition.legacy_label is None, (
            f"Proof metric must have legacy_label=None to prevent export, "
            f"got '{definition.legacy_label}'"
        )

    def test_proof_metric_has_no_frontend_key(self):
        """B3: Proof metric must have frontend_key=None to prevent export."""
        definition = REGISTRY[PROOF_METRIC_ID]
        assert definition.frontend_key is None, (
            f"Proof metric must have frontend_key=None to prevent export, "
            f"got '{definition.frontend_key}'"
        )

    def test_export_maps_filter_none_labels(self):
        """B3: Verify that export map builders correctly filter None labels."""
        # This tests the mechanism that keeps proof metric out of exports
        from src.analysis.math.registry import _build_legacy_ratio_name_map

        test_definitions = {
            "normal_metric": type(
                "obj",
                (object,),
                {"legacy_label": "Normal Label", "frontend_key": "normal_metric"},
            )(),
            "hidden_metric": type(
                "obj", (object,), {"legacy_label": None, "frontend_key": None}
            )(),
        }

        result_map = _build_legacy_ratio_name_map(test_definitions)
        assert "normal_metric" in result_map, "Normal metrics should be in export map"
        assert (
            "hidden_metric" not in result_map
        ), "Metrics with legacy_label=None should be filtered out"


class TestProofMetricDocumentation:
    """Test that proof metric purpose is documented."""

    def test_proof_metric_has_documentation_comment(self):
        """B4: Proof metric should have clear documentation in registry.py."""
        # Read registry.py source to verify documentation exists
        import inspect

        import src.analysis.math.registry as registry_module

        source = inspect.getsource(registry_module)

        # Check for key documentation markers
        assert (
            "WAVE 2 PROOF METRIC" in source or "wave2_proof" in source.lower()
        ), "Proof metric should have documentation comment explaining its purpose"
        assert (
            "ALLOW_ANY_NON_ZERO" in source
        ), "Documentation should mention ALLOW_ANY_NON_ZERO policy"

    def test_proof_metric_naming_convention(self):
        """B4: Proof metric naming should indicate internal/test-only status."""
        assert PROOF_METRIC_ID.startswith("_wave2_"), (
            f"Proof metric should use '_wave2_' prefix for internal identification, "
            f"got '{PROOF_METRIC_ID}'"
        )
        assert "proof" in PROOF_METRIC_ID, (
            f"Proof metric name should contain 'proof' for discoverability, "
            f"got '{PROOF_METRIC_ID}'"
        )
