"""
Narrow internal numeric exception model for Math Layer v2 — Wave 1a.

These exceptions are internal-only. They must not be exposed as public API.
engine.py maps them into existing compatible invalid/refusal result semantics.

Ownership:
- normalization.py may raise: NumericCoercionError, NonFiniteNumberError, NumericNormalizationError
- rounding.py may raise: NumericRoundingError
- projections.py may raise: ProjectionSafetyError
- finalization.py lets narrow exceptions pass upward
- engine.py maps them to outward-compatible result semantics
"""

from __future__ import annotations


class NumericCoercionError(ValueError):
    """Raised when a raw value cannot be coerced into a canonical numeric type."""


class NonFiniteNumberError(ValueError):
    """Raised when a value is NaN or Infinity and cannot be normalized."""


class NumericNormalizationError(ValueError):
    """Raised when normalization fails for reasons other than coercion or non-finite."""


class NumericRoundingError(ValueError):
    """Raised when rounding fails due to invalid policy or unsupported input state."""


class ProjectionSafetyError(ValueError):
    """Raised when projection cannot safely convert a value to outward-compatible float."""
