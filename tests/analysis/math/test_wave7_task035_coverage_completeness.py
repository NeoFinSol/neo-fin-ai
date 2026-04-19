"""Wave 3 Phase 7 — TASK-035 coverage completeness for legacy-exported metrics."""

from __future__ import annotations

import pytest

from src.analysis.math.registry import (
    LEGACY_RATIO_NAME_MAP,
    REGISTRY,
    MetricCoverageClass,
    MetricDefinition,
)


@pytest.mark.wave3_phase7
def test_legacy_exported_metric_has_exactly_one_coverage_class():
    for metric_id, legacy_label in LEGACY_RATIO_NAME_MAP.items():
        definition = REGISTRY[metric_id]
        assert isinstance(definition, MetricDefinition)
        assert isinstance(definition.coverage_class, MetricCoverageClass)
        assert legacy_label == definition.legacy_label


@pytest.mark.wave3_phase7
def test_registry_key_matches_metric_id_for_all_entries():
    for registry_key, definition in REGISTRY.items():
        assert registry_key == definition.metric_id


@pytest.mark.wave3_phase7
def test_no_metric_missing_coverage_class_field():
    for definition in REGISTRY.values():
        assert definition.coverage_class is not None
