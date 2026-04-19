"""
Projection boundary for Math Layer v2 — Wave 1a.

This module is the sole owner of Decimal→float compatibility conversion
for supported runtime numeric paths.

Ownership rules:
- This module MUST NOT accept raw compute float values directly.
- This module MUST NOT re-run canonical normalization.
- This module MUST NOT decide metric semantics or alter validity semantics.
- This module MUST NOT use string formatting as stabilization.
- Decimal→float outward conversion happens ONLY here.
- project_number() is the canonical projection entrypoint.

Anti-double-rounding rule:
  projection_safe rounding is representational only.
  It MUST NOT reinterpret or replace the already-applied normalized_result rounding.
"""

from __future__ import annotations

import math as _math
from dataclasses import dataclass
from decimal import Decimal

from src.analysis.math.contracts import DerivedMetric, ValidityState
from src.analysis.math.numeric_errors import ProjectionSafetyError
from src.analysis.math.registry import LEGACY_RATIO_NAME_MAP
from src.analysis.math.rounding import (
    ROUNDING_POLICY_LEGACY_SAFE_FLOAT_PROJECTION,
    round_number,
)

# ---------------------------------------------------------------------------
# Evidence
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ProjectionEvidence:
    """Machine-checkable evidence that projection boundary was applied."""

    projection_rounding_policy: str


# ---------------------------------------------------------------------------
# Result
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ProjectedNumber:
    """
    Outward-compatible float value produced by the projection boundary.

    Invariants:
    - value is float (not Decimal)
    - value is finite
    - value is negative-zero-clean
    - derived only from a ProjectionReadyNumber (Decimal)
    """

    value: float
    evidence: ProjectionEvidence


# ---------------------------------------------------------------------------
# Core function
# ---------------------------------------------------------------------------


def project_number(
    projection_ready_value: Decimal,
    *,
    projection_rounding_policy: str = ROUNDING_POLICY_LEGACY_SAFE_FLOAT_PROJECTION,
) -> ProjectedNumber:
    """
    Convert a projection-ready Decimal into an outward-compatible float.

    This is the canonical projection entrypoint.
    Callers MUST pass a value that has already been through finalization.

    Steps:
    1. Apply projection-safe rounding (representational only)
    2. Convert Decimal → float
    3. Verify finite and negative-zero-clean
    4. Return ProjectedNumber with evidence

    Raises ProjectionSafetyError if the result is not safe to emit.
    """
    # Step 1: projection-safe rounding (representational, not metric-semantic)
    rounded = round_number(
        projection_ready_value,
        rounding_policy=projection_rounding_policy,
        precision_stage="projection_safe",
    )

    # Step 2: Decimal → float (only conversion point in Wave 1a)
    float_value = float(rounded.value)

    # Step 3: safety checks on the outward float
    if not _math.isfinite(float_value):
        raise ProjectionSafetyError(
            f"Projection produced non-finite float: {float_value!r} "
            f"from Decimal {projection_ready_value!r}"
        )
    # Normalize float negative zero
    if float_value == 0.0 and _math.copysign(1.0, float_value) < 0:
        float_value = 0.0

    evidence = ProjectionEvidence(
        projection_rounding_policy=projection_rounding_policy,
    )
    return ProjectedNumber(value=float_value, evidence=evidence)


# ---------------------------------------------------------------------------
# Legacy metric projection helpers (unchanged public contract)
# ---------------------------------------------------------------------------


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
    """
    Canonical surface mapping layer for Wave 1b.

    Converts internal DerivedMetric objects into outward-compatible
    float | None values for REST and WebSocket surfaces.

    This is the explicit per-surface mapping layer required by Wave 1b spec
    section 12 (Exposure Policy by Surface). canonical_value and projected_value
    remain internal; only value (float | None) reaches outward consumers.
    """
    projected_values: dict[str, float | None] = {}
    projection_trace: dict[str, dict[str, str]] = {}
    for metric_id, label in LEGACY_RATIO_NAME_MAP.items():
        value, trace = project_metric_value(metrics.get(metric_id))
        projected_values[label] = value
        projection_trace[label] = trace
    return projected_values, projection_trace
