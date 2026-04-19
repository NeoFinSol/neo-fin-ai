"""Registry validation for metric definition correctness.

This module provides validation functions to ensure all metric definitions
in the registry are well-formed and consistent before runtime execution.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.analysis.math.registry import MetricDefinition


def validate_metric_definition(
    metric_id: str, 
    definition: "MetricDefinition"
) -> list[str]:
    """Validate a single metric definition.
    
    Returns list of error messages. Empty list means valid.
    
    Validation rules:
    1. If ratio-like (denominator_key is not None), must have both 
       denominator_key and denominator_policy set.
    2. If ratio-like, denominator_key must be in required_inputs.
    3. If ratio-like, denominator_policy must be valid enum value.
    4. If NOT ratio-like, denominator fields should be None.
    """
    errors = []
    
    is_ratio = definition.denominator_key is not None
    
    # Rule 1 & 4: Consistency check for ratio-like vs non-ratio
    if is_ratio:
        # Ratio-like: both fields must be present
        if definition.denominator_policy is None:
            errors.append(
                f"{metric_id}: ratio-like metric (has denominator_key) "
                f"but denominator_policy is None"
            )
    else:
        # Non-ratio: both fields should be None
        if definition.denominator_policy is not None:
            errors.append(
                f"{metric_id}: non-ratio metric (no denominator_key) "
                f"but has denominator_policy={definition.denominator_policy}"
            )
    
    # Rule 2: denominator_key must be in required_inputs
    if is_ratio and definition.denominator_key not in definition.required_inputs:
        errors.append(
            f"{metric_id}: denominator_key '{definition.denominator_key}' "
            f"not found in required_inputs {definition.required_inputs}"
        )
    
    # Rule 3: denominator_policy must be valid (if set)
    if definition.denominator_policy is not None:
        from src.analysis.math.policies import DenominatorPolicy
        if not isinstance(definition.denominator_policy, DenominatorPolicy):
            errors.append(
                f"{metric_id}: invalid denominator_policy type "
                f"'{type(definition.denominator_policy).__name__}'"
            )
    
    return errors


def validate_registry(registry: dict[str, "MetricDefinition"]) -> list[str]:
    """Validate entire registry.
    
    Returns list of all validation errors across all metric definitions.
    Empty list means registry is valid.
    """
    all_errors = []
    for metric_id, definition in registry.items():
        errors = validate_metric_definition(metric_id, definition)
        all_errors.extend(errors)
    return all_errors
