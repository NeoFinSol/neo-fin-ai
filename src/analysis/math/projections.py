from __future__ import annotations

from src.analysis.math.contracts import DerivedMetric, ValidityState
from src.analysis.math.registry import LEGACY_RATIO_NAME_MAP


def project_metric_value(
    metric: DerivedMetric | None,
) -> tuple[float | None, dict[str, str]]:
    """Project DerivedMetric into legacy float representation."""
    if metric is None:
        return None, {"projection": "missing_metric"}
    if metric.validity_state in {
        ValidityState.INVALID,
        ValidityState.NOT_APPLICABLE,
        ValidityState.SUPPRESSED,
    }:
        return None, {"projection": "suppressed_to_none"}
    return metric.value, {"projection": "direct_value"}


def project_legacy_ratios(
    metrics: dict[str, DerivedMetric],
) -> tuple[dict[str, float | None], dict[str, dict[str, str]]]:
    projected_values: dict[str, float | None] = {}
    projection_trace: dict[str, dict[str, str]] = {}
    for metric_id, label in LEGACY_RATIO_NAME_MAP.items():
        value, trace = project_metric_value(metrics.get(metric_id))
        projected_values[label] = value
        projection_trace[label] = trace
    return projected_values, projection_trace
