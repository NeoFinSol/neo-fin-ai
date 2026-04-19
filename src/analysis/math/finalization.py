"""
Mandatory finalization coordinator for Math Layer v2 — Wave 1a.

This module is the single sequencing coordinator for numeric finalization.
It encodes the strict finalization order once and exposes one entrypoint.

Ownership rules:
- This module MUST NOT own raw compute logic.
- This module MUST NOT own projection conversion to outward float.
- This module MUST NOT own payload assembly or public status mapping.
- This module depends ONLY on normalization.py and rounding.py.
- finalization.py is the ONLY module allowed to aggregate normalization
  and rounding evidence into one finalization-level structure.

Finalization order (strict):
1. to_number() coercion          (inside normalize_number)
2. finite validation             (inside normalize_number)
3. canonical normalization       (inside normalize_number)
4. signed-zero normalization     (inside normalize_number)
5. normalized-result rounding    (round_number, stage="normalized_result")
6. evidence aggregation
7. return ProjectionReadyNumber  (Decimal, NOT float)

Output contract:
- finalize_numeric_result() returns ProjectionReadyNumber (Decimal).
- It MUST NOT return a float.
- The caller (engine or comparative) is responsible for projection.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from src.analysis.math.normalization import (
    NORMALIZATION_POLICY_DEFAULT,
    NormalizationEvidence,
    NormalizedNumber,
    normalize_number,
)
from src.analysis.math.rounding import (
    ROUNDING_POLICY_RATIO_STANDARD,
    RoundingEvidence,
    RoundedNumber,
    round_number,
)

# ---------------------------------------------------------------------------
# Evidence
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FinalizationEvidence:
    """
    Aggregated evidence for one complete finalization pass.

    Invariant: aggregated only in finalization.py.
    """

    normalization: NormalizationEvidence
    rounding: RoundingEvidence


# ---------------------------------------------------------------------------
# Result
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ProjectionReadyNumber:
    """
    Canonical internal Decimal value ready for projection.

    Invariants:
    - value is Decimal (NOT float)
    - value is finite
    - value is normalized
    - value is rounded at normalized-result stage
    - value is negative-zero-clean
    - safe to hand to projections.py
    """

    value: Decimal
    evidence: FinalizationEvidence


# ---------------------------------------------------------------------------
# Core function
# ---------------------------------------------------------------------------


def finalize_numeric_result(
    raw_value: object,
    *,
    normalization_policy: str = NORMALIZATION_POLICY_DEFAULT,
    rounding_policy: str = ROUNDING_POLICY_RATIO_STANDARD,
) -> ProjectionReadyNumber:
    """
    Apply the full numeric finalization pipeline to a raw compute result.

    This is the single canonical finalization entrypoint.
    Callers (engine, comparative) MUST use this function instead of
    reproducing the step ordering manually.

    Steps (strict order):
    1. normalize_number() — coercion, finite check, signed-zero normalization
    2. round_number(..., precision_stage="normalized_result")
    3. aggregate FinalizationEvidence
    4. return ProjectionReadyNumber (Decimal, NOT float)

    Raises narrow internal numeric exceptions on failure.
    Does NOT swallow failures silently.
    Does NOT produce outward float.
    """
    # Step 1: normalize
    normalized: NormalizedNumber = normalize_number(
        raw_value,
        normalization_policy=normalization_policy,
    )

    # Step 2: round at normalized-result stage
    rounded: RoundedNumber = round_number(
        normalized.value,
        rounding_policy=rounding_policy,
        precision_stage="normalized_result",
    )

    # Step 3: aggregate evidence
    evidence = FinalizationEvidence(
        normalization=normalized.evidence,
        rounding=rounded.evidence,
    )

    # Step 4: return projection-ready Decimal
    return ProjectionReadyNumber(value=rounded.value, evidence=evidence)
