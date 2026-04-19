"""
Canonical rounding module for Math Layer v2 — Wave 1a.

This module is the single source of truth for rounding semantics.

Ownership rules:
- This module MUST NOT depend on engine.py, projections.py, or comparative.py.
- This module MUST NOT own coercion, normalization, or projection serialization.
- round_number() is the only canonical rounding entrypoint in Wave 1a.

Precision stages:
- normalized_result: metric-level numeric semantics after normalization.
  Applied once, before projection.
- projection_safe: representational compatibility semantics for stable legacy float emission.
  Applied at projection boundary only.
  MUST NOT reinterpret or replace metric-level rounding semantics.

Anti-double-rounding rule:
  projection_safe rounding MUST NOT override the already-applied normalized_result rounding.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_EVEN, Decimal
from typing import Literal

from src.analysis.math.numeric_errors import NumericRoundingError

# ---------------------------------------------------------------------------
# Precision stages
# ---------------------------------------------------------------------------

PrecisionStage = Literal["normalized_result", "projection_safe"]

# ---------------------------------------------------------------------------
# Rounding policies — canonical declaration site
# All policy names must be declared here and only here.
# ---------------------------------------------------------------------------

ROUNDING_POLICY_MONETARY_STANDARD = "MONETARY_STANDARD"
ROUNDING_POLICY_RATIO_STANDARD = "RATIO_STANDARD"
ROUNDING_POLICY_PERCENT_STANDARD = "PERCENT_STANDARD"
ROUNDING_POLICY_COMPARATIVE_STANDARD = "COMPARATIVE_STANDARD"
ROUNDING_POLICY_INTERNAL_HIGH_PRECISION = "INTERNAL_HIGH_PRECISION"
ROUNDING_POLICY_LEGACY_SAFE_FLOAT_PROJECTION = "LEGACY_SAFE_FLOAT_PROJECTION"

_KNOWN_ROUNDING_POLICIES = frozenset(
    {
        ROUNDING_POLICY_MONETARY_STANDARD,
        ROUNDING_POLICY_RATIO_STANDARD,
        ROUNDING_POLICY_PERCENT_STANDARD,
        ROUNDING_POLICY_COMPARATIVE_STANDARD,
        ROUNDING_POLICY_INTERNAL_HIGH_PRECISION,
        ROUNDING_POLICY_LEGACY_SAFE_FLOAT_PROJECTION,
    }
)

# Policy → (quantize_exponent, rounding_mode)
# All policies use ROUND_HALF_EVEN (banker's rounding) for stability.
_POLICY_QUANTIZE: dict[str, tuple[Decimal, str]] = {
    ROUNDING_POLICY_MONETARY_STANDARD: (Decimal("0.01"), ROUND_HALF_EVEN),
    ROUNDING_POLICY_RATIO_STANDARD: (Decimal("0.0001"), ROUND_HALF_EVEN),
    ROUNDING_POLICY_PERCENT_STANDARD: (Decimal("0.01"), ROUND_HALF_EVEN),
    ROUNDING_POLICY_COMPARATIVE_STANDARD: (Decimal("0.0001"), ROUND_HALF_EVEN),
    ROUNDING_POLICY_INTERNAL_HIGH_PRECISION: (Decimal("0.00000001"), ROUND_HALF_EVEN),
    ROUNDING_POLICY_LEGACY_SAFE_FLOAT_PROJECTION: (Decimal("0.000001"), ROUND_HALF_EVEN),
}

# ---------------------------------------------------------------------------
# Evidence
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RoundingEvidence:
    """Machine-checkable evidence that rounding was applied."""

    rounding_policy: str
    precision_stage: PrecisionStage
    signed_zero_normalized_post_round: bool


# ---------------------------------------------------------------------------
# Result
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RoundedNumber:
    """
    Decimal value after policy-based rounding.

    Invariants:
    - value is rounded for the declared precision stage
    - value is finite
    - value is negative-zero-clean post-round
    """

    value: Decimal
    evidence: RoundingEvidence


# ---------------------------------------------------------------------------
# Core function
# ---------------------------------------------------------------------------


def round_number(
    value: Decimal,
    *,
    rounding_policy: str,
    precision_stage: PrecisionStage,
) -> RoundedNumber:
    """
    Apply policy-based rounding to a canonical Decimal value.

    Preconditions:
    - value is already canonicalized (finite, signed-zero-clean pre-round)
    - rounding_policy is a known policy identifier
    - precision_stage is "normalized_result" or "projection_safe"

    Postconditions:
    - output value is finite
    - output value is rounded per policy
    - output value is negative-zero-clean post-round
    - rounding evidence exists
    """
    if rounding_policy not in _KNOWN_ROUNDING_POLICIES:
        raise NumericRoundingError(
            f"Unknown rounding policy: {rounding_policy!r}. "
            f"Known policies: {sorted(_KNOWN_ROUNDING_POLICIES)}"
        )

    if precision_stage not in ("normalized_result", "projection_safe"):
        raise NumericRoundingError(
            f"Unknown precision stage: {precision_stage!r}. "
            "Must be 'normalized_result' or 'projection_safe'."
        )

    quantize_exp, rounding_mode = _POLICY_QUANTIZE[rounding_policy]

    try:
        rounded = value.quantize(quantize_exp, rounding=rounding_mode)
    except Exception as exc:
        raise NumericRoundingError(
            f"Rounding failed for policy={rounding_policy!r}, "
            f"stage={precision_stage!r}, value={value!r}: {exc}"
        ) from exc

    # Post-round signed-zero normalization
    signed_zero_normalized = False
    if rounded == Decimal(0) and rounded.is_signed():
        rounded = Decimal(0)
        signed_zero_normalized = True

    evidence = RoundingEvidence(
        rounding_policy=rounding_policy,
        precision_stage=precision_stage,
        signed_zero_normalized_post_round=signed_zero_normalized,
    )

    return RoundedNumber(value=rounded, evidence=evidence)
