from __future__ import annotations

import math
from typing import Any

from src.analysis.math.contracts import MetricInputRef, TypedInputs
from src.analysis.math.policies import DenominatorClass
from src.analysis.math.registry import get_input_domain_constraint

# Wave 2: Centralized near-zero threshold (Section 10.5, 15.1)
# Single source of truth - MUST NOT be redefined in formula/helper code
DENOMINATOR_EPSILON = 1e-9
KNOWN_MONETARY_UNITS = {None, "currency"}


def validate_input_semantics(key: str, raw_value: Any) -> MetricInputRef:
    candidate = _coerce_input_ref(key, raw_value)
    value = candidate.value
    if candidate.unit not in KNOWN_MONETARY_UNITS:
        return _invalidate_input(candidate, "unexpected_unit")
    if value is None:
        return candidate
    if not math.isfinite(value):
        return _invalidate_input(candidate, "input_non_finite")
    domain_constraint = get_input_domain_constraint(key)
    if domain_constraint.requires_non_negative and value < 0:
        return _invalidate_input(candidate, "unexpected_negative_input")
    return candidate


def normalize_inputs(raw_inputs: dict[str, object]) -> TypedInputs:
    return {
        key: validate_input_semantics(key, value) for key, value in raw_inputs.items()
    }


def classify_denominator(value: float | None) -> DenominatorClass:
    """Canonical denominator classifier (Wave 2 Section 10).

    Single source of truth for denominator class assignment.
    All ratio-like metrics MUST use this classifier.

    Classification order (matches spec Section 10.3-10.5):
    1. MISSING - None value
    2. NON_FINITE - NaN, +Inf, -Inf
    3. ZERO - 0, 0.0, -0.0 (all zero variants treated equally)
    4. NEAR_ZERO_FORBIDDEN - |value| < DENOMINATOR_EPSILON
    5. NEGATIVE_FINITE - value < 0 and finite
    6. POSITIVE_FINITE - value > 0 and finite

    Args:
        value: Denominator value to classify

    Returns:
        DenominatorClass enum value (never string codes)

    Reference: .agent/math_layer_v2_wave2_spec.md Section 10
    """
    # C1-C2: Missing check
    if value is None:
        return DenominatorClass.MISSING

    # C4: Non-finite check (NaN, Inf)
    if not math.isfinite(value):
        return DenominatorClass.NON_FINITE

    # C3: Zero semantics - 0, 0.0, -0.0 all treated as ZERO
    if value == 0:
        return DenominatorClass.ZERO

    # C5: Near-zero semantics with centralized threshold
    if abs(value) < DENOMINATOR_EPSILON:
        return DenominatorClass.NEAR_ZERO_FORBIDDEN

    # Positive/negative classification
    if value < 0:
        return DenominatorClass.NEGATIVE_FINITE

    return DenominatorClass.POSITIVE_FINITE


# =============================================================================
# Wave 2: Shared predicate surface for helper reuse (Section 10.6, C6)
# These predicates provide the same semantics as classify_denominator()
# for cases where helpers need direct checks without full classification.
# =============================================================================


def is_zero_or_signed_zero(value: float | None) -> bool:
    """Check if value is zero or signed-zero (0, 0.0, -0.0).

    Uses same semantics as canonical classifier (value == 0).
    """
    if value is None:
        return False
    return value == 0


def is_non_finite(value: float | None) -> bool:
    """Check if value is non-finite (NaN, +Inf, -Inf).

    Uses same semantics as canonical classifier.
    """
    if value is None:
        return False
    return not math.isfinite(value)


def is_near_zero_forbidden(value: float | None) -> bool:
    """Check if value is forbidden near-zero (|value| < DENOMINATOR_EPSILON).

    Uses centralized threshold from validators module.
    MUST NOT define local epsilon in helper code.
    """
    if value is None:
        return False
    if not math.isfinite(value):
        return False
    if value == 0:
        return False  # Zero is handled by is_zero_or_signed_zero
    return abs(value) < DENOMINATOR_EPSILON


def _coerce_input_ref(key: str, raw_value: Any) -> MetricInputRef:
    if isinstance(raw_value, MetricInputRef):
        return raw_value.model_copy(deep=True)
    if isinstance(raw_value, dict):
        return MetricInputRef(metric_key=key, **raw_value)
    if raw_value is None:
        return MetricInputRef(metric_key=key, value=None)
    if isinstance(raw_value, bool):
        return MetricInputRef(
            metric_key=key, value=None, reason_codes=["input_not_numeric"]
        )
    if isinstance(raw_value, (int, float)):
        return MetricInputRef(metric_key=key, value=float(raw_value))
    return MetricInputRef(
        metric_key=key, value=None, reason_codes=["input_not_numeric"]
    )


def _invalidate_input(candidate: MetricInputRef, reason_code: str) -> MetricInputRef:
    updated = candidate.model_copy(deep=True)
    updated.value = None
    if reason_code not in updated.reason_codes:
        updated.reason_codes.append(reason_code)
    return updated
