"""
Canonical numeric normalization module for Math Layer v2 — Wave 1a.

This module is the single source of truth for:
- numeric coercion (to_number)
- finite validation
- canonical normalization (normalize_number)
- signed-zero normalization
- normalization evidence

Ownership rules:
- This module MUST NOT depend on engine.py, projections.py, or comparative.py.
- This module MUST NOT own projection logic, payload serialization, or scoring helpers.
- to_number() is the only canonical coercion entrypoint in Wave 1a.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Literal

from src.analysis.math.numeric_errors import (
    NonFiniteNumberError,
    NumericCoercionError,
    NumericNormalizationError,
)

# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------

CanonicalNumericKind = Literal["decimal", "int_like", "float_like"]


# ---------------------------------------------------------------------------
# Normalization policies
# ---------------------------------------------------------------------------

NORMALIZATION_POLICY_DEFAULT = "DEFAULT_NUMERIC_NORMALIZATION"
NORMALIZATION_POLICY_COMPARATIVE_BALANCE_INPUT = "COMPARATIVE_BALANCE_INPUT"
NORMALIZATION_POLICY_COMPARATIVE_AVERAGE_RESULT = "COMPARATIVE_AVERAGE_RESULT"

_KNOWN_NORMALIZATION_POLICIES = frozenset(
    {
        NORMALIZATION_POLICY_DEFAULT,
        NORMALIZATION_POLICY_COMPARATIVE_BALANCE_INPUT,
        NORMALIZATION_POLICY_COMPARATIVE_AVERAGE_RESULT,
    }
)


# ---------------------------------------------------------------------------
# Evidence
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class NormalizationEvidence:
    """Machine-checkable evidence that normalization path was applied."""

    source_kind: str
    coercion_applied: bool
    finite_checked: bool
    signed_zero_normalized: bool
    canonical_kind: CanonicalNumericKind
    normalization_policy: str


# ---------------------------------------------------------------------------
# Result
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class NormalizedNumber:
    """
    Canonical internal numeric form after normalization.

    Invariants:
    - value is Decimal
    - value is finite
    - value is signed-zero-clean (pre-round)
    - not yet rounded at normalized-result stage
    """

    value: Decimal
    evidence: NormalizationEvidence


# ---------------------------------------------------------------------------
# Core functions
# ---------------------------------------------------------------------------


def to_number(raw_value: object) -> Decimal:
    """
    Canonical numeric coercion entrypoint.

    Accepts only explicitly allowed numeric runtime types.
    Rejects bool, arbitrary strings, and unsupported objects.
    Fails closed on unsupported input.

    This is the only canonical coercion helper in Wave 1a.
    """
    # bool is a subclass of int — must be rejected explicitly before int check
    if isinstance(raw_value, bool):
        raise NumericCoercionError(
            f"bool is not an accepted numeric type: {raw_value!r}"
        )

    if isinstance(raw_value, Decimal):
        return raw_value

    if isinstance(raw_value, int):
        return Decimal(raw_value)

    if isinstance(raw_value, float):
        # Convert via string to avoid IEEE 754 representation artifacts
        # e.g. float 0.1 → Decimal("0.1") not Decimal("0.1000000000000000055511...")
        try:
            return Decimal(str(raw_value))
        except InvalidOperation as exc:
            raise NumericCoercionError(
                f"Cannot coerce float to Decimal: {raw_value!r}"
            ) from exc

    raise NumericCoercionError(
        f"Unsupported numeric type {type(raw_value).__name__!r}: {raw_value!r}"
    )


def normalize_number(
    raw_value: object,
    *,
    normalization_policy: str = NORMALIZATION_POLICY_DEFAULT,
) -> NormalizedNumber:
    """
    Normalize a raw value into canonical internal numeric form.

    Steps (strict order):
    1. to_number() coercion
    2. finite validation
    3. signed-zero normalization
    4. evidence production

    Returns NormalizedNumber with canonical Decimal value and evidence.
    The returned value is NOT yet rounded at normalized-result stage.
    """
    if normalization_policy not in _KNOWN_NORMALIZATION_POLICIES:
        raise NumericNormalizationError(
            f"Unknown normalization policy: {normalization_policy!r}. "
            f"Known policies: {sorted(_KNOWN_NORMALIZATION_POLICIES)}"
        )

    # Determine source kind for evidence
    source_kind = _source_kind(raw_value)
    coercion_applied = not isinstance(raw_value, Decimal)

    # Step 1: coercion
    try:
        decimal_value = to_number(raw_value)
    except NumericCoercionError:
        raise
    except Exception as exc:
        raise NumericNormalizationError(
            f"Normalization failed during coercion: {exc}"
        ) from exc

    # Step 2: finite validation
    _assert_finite(decimal_value, raw_value)

    # Step 3: signed-zero normalization
    signed_zero_normalized = False
    if decimal_value == Decimal(0) and decimal_value.is_signed():
        decimal_value = Decimal(0)
        signed_zero_normalized = True

    # Step 4: evidence
    evidence = NormalizationEvidence(
        source_kind=source_kind,
        coercion_applied=coercion_applied,
        finite_checked=True,
        signed_zero_normalized=signed_zero_normalized,
        canonical_kind=_canonical_kind(raw_value),
        normalization_policy=normalization_policy,
    )

    return NormalizedNumber(value=decimal_value, evidence=evidence)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _assert_finite(value: Decimal, original: object) -> None:
    """Raise NonFiniteNumberError if value is NaN or Infinity."""
    if value.is_nan():
        raise NonFiniteNumberError(
            f"Non-finite value (NaN) cannot be normalized: {original!r}"
        )
    if value.is_infinite():
        raise NonFiniteNumberError(
            f"Non-finite value (Infinity) cannot be normalized: {original!r}"
        )


def _source_kind(raw_value: object) -> str:
    if isinstance(raw_value, bool):
        return "bool"
    if isinstance(raw_value, Decimal):
        return "decimal"
    if isinstance(raw_value, int):
        return "int"
    if isinstance(raw_value, float):
        return "float"
    return type(raw_value).__name__


def _canonical_kind(raw_value: object) -> CanonicalNumericKind:
    if isinstance(raw_value, Decimal):
        return "decimal"
    if isinstance(raw_value, int) and not isinstance(raw_value, bool):
        return "int_like"
    return "float_like"
