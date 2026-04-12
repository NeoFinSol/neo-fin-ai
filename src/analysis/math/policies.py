from __future__ import annotations

from enum import Enum
from typing import Final

MISSING_CONFIDENCE_PENALTY_FACTOR: Final = 0.9


class DenominatorPolicy(str, Enum):
    ALLOW_ANY_NON_ZERO = "allow_any_non_zero"
    STRICT_POSITIVE = "strict_positive"


class AveragingPolicy(str, Enum):
    NONE = "none"
    AVERAGE_BALANCE = "average_balance"


class SuppressionPolicy(str, Enum):
    NEVER = "never"
    SUPPRESS_UNSAFE = "suppress_unsafe"
