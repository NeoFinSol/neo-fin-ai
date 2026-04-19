from __future__ import annotations

from enum import Enum
from typing import Final

MISSING_CONFIDENCE_PENALTY_FACTOR: Final = 0.9


# =============================================================================
# Wave 2: Denominator Classification (Section 10 - Canonical Denominator Classification)
# =============================================================================
class DenominatorClass(str, Enum):
    """Canonical denominator classification for ratio-like metrics.
    
    Single source of truth for denominator class semantics.
    All denominator handling MUST use this enum, not string codes.
    
    Reference: .agent/math_layer_v2_wave2_spec.md Section 10
    """
    MISSING = "missing"                    # Value is None/absent
    NON_FINITE = "non_finite"              # NaN, +Inf, -Inf
    ZERO = "zero"                          # 0, 0.0, -0.0 (all zero variants)
    NEAR_ZERO_FORBIDDEN = "near_zero_forbidden"  # |value| < DENOMINATOR_EPSILON
    POSITIVE_FINITE = "positive_finite"    # value > 0 and finite
    NEGATIVE_FINITE = "negative_finite"    # value < 0 and finite


class DenominatorPolicy(str, Enum):
    ALLOW_ANY_NON_ZERO = "allow_any_non_zero"
    STRICT_POSITIVE = "strict_positive"


class AveragingPolicy(str, Enum):
    NONE = "none"
    AVERAGE_BALANCE = "average_balance"


class SuppressionPolicy(str, Enum):
    NEVER = "never"
    SUPPRESS_UNSAFE = "suppress_unsafe"
