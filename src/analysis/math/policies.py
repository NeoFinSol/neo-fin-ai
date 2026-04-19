from __future__ import annotations

from dataclasses import dataclass
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
    """Denominator policy declarations for ratio-like metrics.
    
    Reference: .agent/math_layer_v2_wave2_spec.md Section 9
    """
    ALLOW_ANY_NON_ZERO = "allow_any_non_zero"
    STRICT_POSITIVE = "strict_positive"


# =============================================================================
# Wave 2: Denominator Policy Evaluation (Section 7, 9 - Canonical Policy Evaluator)
# =============================================================================
@dataclass(frozen=True)
class DenominatorPolicyDecision:
    """Result of denominator policy evaluation (D2).
    
    Explicit decision object with machine-readable semantics.
    NOT a bare boolean - carries full context for trace/refusal.
    
    Reference: .agent/math_layer_v2_wave2_spec.md Section 7.2, 9.2
    """
    allowed: bool                                    # True if denominator passes policy
    denominator_class: DenominatorClass             # Classified denominator
    policy: DenominatorPolicy                        # Applied policy
    refusal_reason: str | None = None               # Reason if refused (None if allowed)


def evaluate_denominator_policy(
    policy: DenominatorPolicy,
    denominator_class: DenominatorClass,
) -> DenominatorPolicyDecision:
    """Canonical denominator policy evaluator (D3-D4).
    
    Deterministic, side-effect free policy decision function.
    Implements full semantics matrix from spec Section 9.3-9.4.
    
    Args:
        policy: Declared denominator policy for the metric
        denominator_class: Classified denominator value
        
    Returns:
        DenominatorPolicyDecision with explicit allow/refuse semantics
        
    Reference: .agent/math_layer_v2_wave2_spec.md Section 9
    """
    # D4: STRICT_POSITIVE semantics (Section 9.3)
    if policy == DenominatorPolicy.STRICT_POSITIVE:
        if denominator_class == DenominatorClass.POSITIVE_FINITE:
            return DenominatorPolicyDecision(
                allowed=True,
                denominator_class=denominator_class,
                policy=policy,
            )
        else:
            return DenominatorPolicyDecision(
                allowed=False,
                denominator_class=denominator_class,
                policy=policy,
                refusal_reason=f"denominator_policy_violation:{policy.value}:{denominator_class.value}",
            )
    
    # D4: ALLOW_ANY_NON_ZERO semantics (Section 9.4)
    elif policy == DenominatorPolicy.ALLOW_ANY_NON_ZERO:
        if denominator_class in (DenominatorClass.POSITIVE_FINITE, DenominatorClass.NEGATIVE_FINITE):
            return DenominatorPolicyDecision(
                allowed=True,
                denominator_class=denominator_class,
                policy=policy,
            )
        else:
            return DenominatorPolicyDecision(
                allowed=False,
                denominator_class=denominator_class,
                policy=policy,
                refusal_reason=f"denominator_policy_violation:{policy.value}:{denominator_class.value}",
            )
    
    # Unknown policy - refuse to be safe
    else:
        return DenominatorPolicyDecision(
            allowed=False,
            denominator_class=denominator_class,
            policy=policy,
            refusal_reason=f"unknown_denominator_policy:{policy.value}",
        )


class AveragingPolicy(str, Enum):
    NONE = "none"
    AVERAGE_BALANCE = "average_balance"


class SuppressionPolicy(str, Enum):
    NEVER = "never"
    SUPPRESS_UNSAFE = "suppress_unsafe"
