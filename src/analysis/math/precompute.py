from __future__ import annotations

from src.analysis.math.contracts import MetricInputRef, TypedInputs


def build_precomputed_inputs(inputs: TypedInputs) -> TypedInputs:
    result = {key: value.model_copy(deep=True) for key, value in inputs.items()}
    result["total_debt"] = _build_total_debt(result)
    result["ebitda_reported"] = _copy_input(
        result.get("ebitda"),
        metric_key="ebitda_reported",
    )
    result["ebitda_canonical"] = MetricInputRef(metric_key="ebitda_canonical", value=None)
    result["ebitda_approximated"] = MetricInputRef(
        metric_key="ebitda_approximated",
        value=None,
    )
    return result


def _build_total_debt(inputs: TypedInputs) -> MetricInputRef:
    short_term = inputs.get("short_term_borrowings")
    long_term = inputs.get("long_term_borrowings")
    if short_term is None or long_term is None:
        return MetricInputRef(metric_key="total_debt", value=None)
    if short_term.value is None or long_term.value is None:
        return MetricInputRef(metric_key="total_debt", value=None)
    return MetricInputRef(
        metric_key="total_debt",
        value=short_term.value + long_term.value,
        confidence=_min_confidence(short_term.confidence, long_term.confidence),
    )


def _copy_input(
    source: MetricInputRef | None,
    *,
    metric_key: str,
) -> MetricInputRef:
    if source is None:
        return MetricInputRef(metric_key=metric_key, value=None)
    copied = source.model_copy(deep=True)
    copied.metric_key = metric_key
    return copied


def _min_confidence(*values: float | None) -> float | None:
    available = [value for value in values if value is not None]
    if not available:
        return None
    return min(available)
