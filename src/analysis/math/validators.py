from __future__ import annotations

import math
from typing import Any

from src.analysis.math.contracts import MetricInputRef, TypedInputs

DENOMINATOR_EPSILON = 1e-9
EXPECTED_NON_NEGATIVE_INPUTS = {
    "cash_and_equivalents",
    "current_assets",
    "equity",
    "revenue",
    "short_term_liabilities",
    "total_assets",
}
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
    if key in EXPECTED_NON_NEGATIVE_INPUTS and value < 0:
        return _invalidate_input(candidate, "unexpected_negative_input")
    return candidate


def normalize_inputs(raw_inputs: dict[str, object]) -> TypedInputs:
    return {
        key: validate_input_semantics(key, value)
        for key, value in raw_inputs.items()
    }


def classify_denominator(value: float | None) -> str:
    if value is None:
        return "missing"
    if not math.isfinite(value):
        return "non_finite"
    if value == 0:
        return "zero"
    if abs(value) < DENOMINATOR_EPSILON:
        return "near_zero"
    if value < 0:
        return "negative"
    return "valid"


def _coerce_input_ref(key: str, raw_value: Any) -> MetricInputRef:
    if isinstance(raw_value, MetricInputRef):
        return raw_value.model_copy(deep=True)
    if isinstance(raw_value, dict):
        return MetricInputRef(metric_key=key, **raw_value)
    if raw_value is None:
        return MetricInputRef(metric_key=key, value=None)
    if isinstance(raw_value, bool):
        return MetricInputRef(metric_key=key, value=None, reason_codes=["input_not_numeric"])
    if isinstance(raw_value, (int, float)):
        return MetricInputRef(metric_key=key, value=float(raw_value))
    return MetricInputRef(metric_key=key, value=None, reason_codes=["input_not_numeric"])


def _invalidate_input(candidate: MetricInputRef, reason_code: str) -> MetricInputRef:
    updated = candidate.model_copy(deep=True)
    updated.value = None
    if reason_code not in updated.reason_codes:
        updated.reason_codes.append(reason_code)
    return updated
