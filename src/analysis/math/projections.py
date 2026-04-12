from __future__ import annotations

from copy import deepcopy

from src.analysis.math.contracts import DerivedMetric, ValidityState

LEGACY_RATIO_NAME_MAP = {
    "current_ratio": "Коэффициент текущей ликвидности",
    "absolute_liquidity_ratio": "Коэффициент абсолютной ликвидности",
    "ros": "Рентабельность продаж (ROS)",
    "equity_ratio": "Коэффициент автономии",
    "ebitda_margin": "EBITDA маржа",
    "financial_leverage_debt_only": "Финансовый рычаг (долг/капитал)",
}


def project_metric_value(
    metric: DerivedMetric | None,
) -> tuple[float | None, dict[str, str]]:
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
        projection_trace[label] = deepcopy(trace)
    return projected_values, projection_trace
