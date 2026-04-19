"""Math layer initialization with registry validation."""

from src.analysis.math.registry import REGISTRY
from src.analysis.math.registry_validation import validate_registry

# Validate registry at import time - fail fast on malformed definitions
_validation_errors = validate_registry(REGISTRY)
if _validation_errors:
    raise RuntimeError(
        f"Math registry validation failed with {len(_validation_errors)} error(s):\n"
        + "\n".join(f"  - {err}" for err in _validation_errors)
    )

from src.analysis.math.contracts import (
    DerivedMetric,
    MetricComputationResult,
    MetricInputRef,
    MetricUnit,
    TypedInputs,
    ValidityState,
)
from src.analysis.math.policies import (
    MISSING_CONFIDENCE_PENALTY_FACTOR,
    AveragingPolicy,
    DenominatorPolicy,
    SuppressionPolicy,
)

__all__ = [
    "AveragingPolicy",
    "DenominatorPolicy",
    "DerivedMetric",
    "MetricComputationResult",
    "MetricInputRef",
    "MetricUnit",
    "MISSING_CONFIDENCE_PENALTY_FACTOR",
    "SuppressionPolicy",
    "TypedInputs",
    "ValidityState",
    "REGISTRY",
]
