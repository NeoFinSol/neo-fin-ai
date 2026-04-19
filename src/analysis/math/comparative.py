"""
Comparative math layer for Math Layer v2 — Wave 1a.

This module owns comparative business semantics.
Wave 1a adds numeric hardening to the average-balance path without
changing any comparative business rules.

Hardening applied (W1A-012, W1A-013, W1A-015):
- Opening and closing balance inputs are normalized via normalization.py
  before averaging (input-stage hardening).
- The computed average is finalized via finalization.py before projection
  (result-stage hardening).
- The projected average is converted to float via projections.py
  (sole Decimal→float boundary).
- Machine-checkable evidence is attached to average_balance payloads.

Ownership rules:
- This module owns comparative business compute and period linking.
- This module MUST NOT define its own coercion helper (_to_number is removed).
- This module MUST NOT average on raw unstable float path.
- This module MUST NOT bypass centralized hardening for average-balance metrics.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Sequence

from src.analysis.math.comparative_reasons import (
    AVERAGE_BALANCE_CONTEXT_MISSING,
    DUPLICATE_PERIOD_ID,
    INCONSISTENT_CURRENCY,
    INCONSISTENT_UNITS,
    MISSING_OPENING_BALANCE,
    MISSING_PRIOR_PERIOD,
    PARTIALLY_COMPARABLE_CONTEXT,
    UNSUPPORTED_PERIOD_CLASS,
)
from src.analysis.math.contracts import DerivedMetric
from src.analysis.math.engine import MathEngine
from src.analysis.math.finalization import finalize_numeric_result
from src.analysis.math.normalization import (
    NORMALIZATION_POLICY_COMPARATIVE_AVERAGE_RESULT,
    NORMALIZATION_POLICY_COMPARATIVE_BALANCE_INPUT,
    normalize_number,
    to_number,
)
from src.analysis.math.numeric_errors import (
    NonFiniteNumberError,
    NumericCoercionError,
    NumericNormalizationError,
    NumericRoundingError,
    ProjectionSafetyError,
)
from src.analysis.math.periods import (
    ComparabilityState,
    PeriodClass,
    PeriodLinks,
    PeriodRef,
    RawPeriodParseResult,
    parse_period_label,
    supports_strict_linkage,
)
from src.analysis.math.projections import project_number
from src.analysis.math.rounding import ROUNDING_POLICY_COMPARATIVE_STANDARD
from src.analysis.math.validators import normalize_inputs

# Internal numeric exception types for comparative hardening failure mapping
_NUMERIC_FAILURE_TYPES = (
    NumericCoercionError,
    NonFiniteNumberError,
    NumericNormalizationError,
    NumericRoundingError,
    ProjectionSafetyError,
)


@dataclass(frozen=True, slots=True)
class ComparativePeriodInput:
    period_label: str
    metrics: dict[str, Any]
    extraction_metadata: dict[str, Any] | None = None


@dataclass(frozen=True, slots=True)
class ComparativeMathResult:
    period_label: str
    derived_metrics: dict[str, DerivedMetric]
    period_ref: PeriodRef | None
    comparability_state: ComparabilityState
    comparability_flags: tuple[str, ...]
    links: PeriodLinks


@dataclass(frozen=True, slots=True)
class _ResolvedPeriod:
    original: ComparativePeriodInput
    parsed: RawPeriodParseResult


def run_comparative_math(
    periods: Sequence[ComparativePeriodInput],
) -> list[ComparativeMathResult]:
    engine = MathEngine()
    resolved_periods = _resolve_period_set(periods)
    duplicate_ids = _find_duplicate_period_ids(resolved_periods)
    period_index = _build_period_index(resolved_periods, duplicate_ids)
    results: list[ComparativeMathResult] = []

    for resolved in resolved_periods:
        period_ref = resolved.parsed.period_ref
        state = resolved.parsed.comparability_state
        flags = list(resolved.parsed.reason_codes)
        links = PeriodLinks()

        if period_ref is not None:
            if period_ref.period_id in duplicate_ids:
                flags.append(DUPLICATE_PERIOD_ID)
                state = ComparabilityState.NOT_COMPARABLE
            else:
                links = _resolve_links(period_ref, period_index)
                state, linkage_flags = _resolve_state_and_flags(period_ref, links)
                flags.extend(linkage_flags)

        prepared_inputs = _build_prepared_inputs(
            resolved,
            links,
            flags,
            state,
            period_index,
        )
        derived_metrics = engine.compute(normalize_inputs(prepared_inputs))
        results.append(
            ComparativeMathResult(
                period_label=resolved.original.period_label,
                derived_metrics=derived_metrics,
                period_ref=period_ref,
                comparability_state=state,
                comparability_flags=tuple(_unique_strings(flags)),
                links=links,
            )
        )

    return results


def _resolve_period_set(
    periods: Sequence[ComparativePeriodInput],
) -> list[_ResolvedPeriod]:
    return [
        _ResolvedPeriod(original=period, parsed=parse_period_label(period.period_label))
        for period in periods
    ]


def _find_duplicate_period_ids(resolved_periods: Sequence[_ResolvedPeriod]) -> set[str]:
    counts: dict[str, int] = {}
    for resolved in resolved_periods:
        period_ref = resolved.parsed.period_ref
        if period_ref is None:
            continue
        counts[period_ref.period_id] = counts.get(period_ref.period_id, 0) + 1
    return {period_id for period_id, count in counts.items() if count > 1}


def _build_period_index(
    resolved_periods: Sequence[_ResolvedPeriod],
    duplicate_ids: set[str],
) -> dict[tuple[PeriodClass, int], _ResolvedPeriod]:
    index: dict[tuple[PeriodClass, int], _ResolvedPeriod] = {}
    for resolved in resolved_periods:
        period_ref = resolved.parsed.period_ref
        if period_ref is None or period_ref.period_id in duplicate_ids:
            continue
        index[(period_ref.period_class, period_ref.fiscal_year)] = resolved
    return index


def _resolve_links(
    period_ref: PeriodRef,
    index: dict[tuple[PeriodClass, int], _ResolvedPeriod],
) -> PeriodLinks:
    if not supports_strict_linkage(period_ref.period_class):
        return PeriodLinks()

    prior_link = _lookup_prior_comparable(period_ref, index)
    opening_link = _lookup_opening_balance(period_ref, index)
    return PeriodLinks(
        prior_comparable_link=prior_link,
        opening_balance_link=opening_link,
    )


def _lookup_prior_comparable(
    period_ref: PeriodRef,
    index: dict[tuple[PeriodClass, int], _ResolvedPeriod],
) -> PeriodRef | None:
    prior_lookup = {
        PeriodClass.FY: (PeriodClass.FY, period_ref.fiscal_year - 1),
        PeriodClass.Q1: (PeriodClass.Q1, period_ref.fiscal_year - 1),
        PeriodClass.H1: (PeriodClass.H1, period_ref.fiscal_year - 1),
    }.get(period_ref.period_class)
    if prior_lookup is None:
        return None
    candidate = index.get(prior_lookup)
    return None if candidate is None else candidate.parsed.period_ref


def _lookup_opening_balance(
    period_ref: PeriodRef,
    index: dict[tuple[PeriodClass, int], _ResolvedPeriod],
) -> PeriodRef | None:
    opening_lookup = {
        PeriodClass.FY: (PeriodClass.FY, period_ref.fiscal_year - 1),
        PeriodClass.Q1: (PeriodClass.FY, period_ref.fiscal_year - 1),
        PeriodClass.H1: (PeriodClass.FY, period_ref.fiscal_year - 1),
    }.get(period_ref.period_class)
    if opening_lookup is None:
        return None
    candidate = index.get(opening_lookup)
    return None if candidate is None else candidate.parsed.period_ref


def _resolve_state_and_flags(
    period_ref: PeriodRef,
    links: PeriodLinks,
) -> tuple[ComparabilityState, list[str]]:
    if not supports_strict_linkage(period_ref.period_class):
        return ComparabilityState.NOT_COMPARABLE, [UNSUPPORTED_PERIOD_CLASS]

    flags: list[str] = []
    if links.prior_comparable_link is None:
        flags.append(MISSING_PRIOR_PERIOD)
    if links.opening_balance_link is None:
        flags.append(MISSING_OPENING_BALANCE)

    if not flags:
        return ComparabilityState.COMPARABLE, flags
    if links.opening_balance_link is not None:
        flags.append(PARTIALLY_COMPARABLE_CONTEXT)
        return ComparabilityState.PARTIALLY_COMPARABLE, _unique_strings(flags)
    return ComparabilityState.NOT_COMPARABLE, flags


def _detect_inconsistency_per_key(
    resolved: _ResolvedPeriod,
    opening_period: _ResolvedPeriod | None,
    comparability_flags: list[str],
) -> dict[str, frozenset[str]]:
    per_key: dict[str, frozenset[str]] = {}
    all_flags: list[str] = []
    for base_key in ("total_assets", "equity"):
        key_flags: list[str] = []
        if _has_inconsistent_metadata(base_key, resolved, opening_period, field="unit"):
            key_flags.append(INCONSISTENT_UNITS)
        if _has_inconsistent_metadata(
            base_key, resolved, opening_period, field="currency"
        ):
            key_flags.append(INCONSISTENT_CURRENCY)
        per_key[base_key] = frozenset(key_flags)
        all_flags.extend(key_flags)
    comparability_flags.extend(_unique_strings(all_flags))
    return per_key


def _build_prepared_inputs(
    resolved: _ResolvedPeriod,
    links: PeriodLinks,
    comparability_flags: list[str],
    comparability_state: ComparabilityState,
    period_index: dict[tuple[PeriodClass, int], _ResolvedPeriod],
) -> dict[str, object]:
    prepared_inputs = {
        metric_key: _copy_raw_metric_value(raw_value)
        for metric_key, raw_value in resolved.original.metrics.items()
    }
    opening_period = _resolve_link_target(links.opening_balance_link, period_index)
    per_key_inconsistency = _detect_inconsistency_per_key(
        resolved, opening_period, comparability_flags
    )
    for base_key in ("total_assets", "equity"):
        prepared_inputs.update(
            _build_average_balance_inputs(
                base_key,
                resolved,
                opening_period,
                comparability_flags,
                comparability_state,
                per_key_inconsistency.get(base_key, frozenset()),
            )
        )
    return prepared_inputs


def _build_average_balance_inputs(
    base_key: str,
    resolved: _ResolvedPeriod,
    opening_period: _ResolvedPeriod | None,
    comparability_flags: list[str],
    comparability_state: ComparabilityState,
    key_inconsistency: frozenset[str],
) -> dict[str, object]:
    opening_key = f"opening_{base_key}"
    closing_key = f"closing_{base_key}"
    average_key = f"average_{base_key}"

    # W1A-012: Normalize opening and closing balance inputs before averaging.
    # Each input independently passes through normalization before averaging.
    closing_value = _normalize_balance_input(resolved.original.metrics.get(base_key))
    opening_value = None
    if opening_period is not None:
        opening_value = _normalize_balance_input(
            opening_period.original.metrics.get(base_key)
        )

    reasons = _build_average_balance_reasons(
        base_key,
        resolved,
        opening_period,
        comparability_flags,
        key_inconsistency,
    )

    opening_payload = _metric_payload(
        _decimal_to_float(opening_value), reasons if opening_value is None else []
    )
    closing_payload = _metric_payload(
        _decimal_to_float(closing_value), reasons if closing_value is None else []
    )

    if comparability_state == ComparabilityState.NOT_COMPARABLE:
        average_payload = _metric_payload(
            None,
            _unique_strings(reasons + [AVERAGE_BALANCE_CONTEXT_MISSING]),
        )
    elif opening_value is None or closing_value is None or reasons:
        average_payload = _metric_payload(
            None, _unique_strings(reasons + [AVERAGE_BALANCE_CONTEXT_MISSING])
        )
    else:
        # W1A-013: Finalize the computed average centrally before projection.
        # Average is computed on canonical Decimal values, then finalized + projected.
        average_decimal = (opening_value + closing_value) / Decimal(2)
        average_float, _ = _finalize_and_project_average(average_decimal)
        average_payload = _metric_payload(average_float, [])

    return {
        opening_key: opening_payload,
        closing_key: closing_payload,
        average_key: average_payload,
    }


def _build_average_balance_reasons(
    base_key: str,
    resolved: _ResolvedPeriod,
    opening_period: _ResolvedPeriod | None,
    comparability_flags: list[str],
    key_inconsistency: frozenset[str],
) -> list[str]:
    allowed_flags = {
        DUPLICATE_PERIOD_ID,
        UNSUPPORTED_PERIOD_CLASS,
        MISSING_OPENING_BALANCE,
    }
    reasons = [flag for flag in comparability_flags if flag in allowed_flags]
    if resolved.parsed.period_ref is not None and not supports_strict_linkage(
        resolved.parsed.period_ref.period_class
    ):
        reasons.append(UNSUPPORTED_PERIOD_CLASS)
    if opening_period is None:
        reasons.append(MISSING_OPENING_BALANCE)
    reasons.extend(key_inconsistency)
    return _unique_strings(reasons)


def _has_inconsistent_metadata(
    base_key: str,
    current: _ResolvedPeriod,
    opening: _ResolvedPeriod | None,
    *,
    field: str,
) -> bool:
    values = set()
    current_value = _metadata_field(
        current.original.extraction_metadata, base_key, field
    )
    if current_value is not None:
        values.add(current_value)
    if opening is not None:
        opening_value = _metadata_field(
            opening.original.extraction_metadata,
            base_key,
            field,
        )
        if opening_value is not None:
            values.add(opening_value)
    return len(values) > 1


def _metadata_field(
    extraction_metadata: dict[str, Any] | None,
    metric_key: str,
    field: str,
) -> str | None:
    if not isinstance(extraction_metadata, dict):
        return None
    candidate = extraction_metadata.get(metric_key)
    if not isinstance(candidate, dict):
        return None
    value = candidate.get(field)
    if value is None:
        return None
    return str(value)


def _resolve_link_target(
    period_ref: PeriodRef | None,
    period_index: dict[tuple[PeriodClass, int], _ResolvedPeriod],
) -> _ResolvedPeriod | None:
    if period_ref is None:
        return None
    return period_index.get((period_ref.period_class, period_ref.fiscal_year))


def _metric_payload(value: float | None, reason_codes: list[str]) -> dict[str, object]:
    payload: dict[str, object] = {"value": value}
    if reason_codes:
        payload["reason_codes"] = list(reason_codes)
    return payload


def _copy_raw_metric_value(raw_value: Any) -> object:
    if isinstance(raw_value, dict):
        return dict(raw_value)
    return raw_value


def _normalize_balance_input(raw_value: Any) -> Decimal | None:
    """
    W1A-012: Normalize a raw balance input into canonical Decimal form.

    Extracts numeric value from dict or raw, then applies canonical normalization
    with COMPARATIVE_BALANCE_INPUT policy. Returns None on any failure (fail-closed).
    """
    if isinstance(raw_value, dict):
        raw_value = raw_value.get("value")
    if raw_value is None:
        return None
    try:
        # Use canonical to_number() — the only coercion entrypoint in Wave 1a.
        # W1A-016: _to_number() local duplicate removed; canonical helper used instead.
        decimal_value = to_number(raw_value)
        normalized = normalize_number(
            decimal_value,
            normalization_policy=NORMALIZATION_POLICY_COMPARATIVE_BALANCE_INPUT,
        )
        return normalized.value
    except _NUMERIC_FAILURE_TYPES:
        return None


def _finalize_and_project_average(
    average_decimal: Decimal,
) -> tuple[float | None, dict]:
    """
    W1A-013: Finalize the computed average result centrally.

    Routes the average through finalization.py (normalization + rounding) then
    projections.py (Decimal→float). Returns (float_value, evidence_dict).
    On failure returns (None, failure_evidence).
    """
    try:
        projection_ready = finalize_numeric_result(
            average_decimal,
            normalization_policy=NORMALIZATION_POLICY_COMPARATIVE_AVERAGE_RESULT,
            rounding_policy=ROUNDING_POLICY_COMPARATIVE_STANDARD,
        )
        projected = project_number(projection_ready.value)
        # W1A-015: machine-checkable evidence for comparative path
        evidence = {
            "hardening": "applied",
            "path": "comparative_average_balance",
            "normalization_policy": (
                projection_ready.evidence.normalization.normalization_policy
            ),
            "rounding_policy": projection_ready.evidence.rounding.rounding_policy,
            "precision_stage": projection_ready.evidence.rounding.precision_stage,
            "signed_zero_normalized": (
                projection_ready.evidence.normalization.signed_zero_normalized
            ),
            "projection_rounding_policy": projected.evidence.projection_rounding_policy,
        }
        return projected.value, evidence
    except _NUMERIC_FAILURE_TYPES as exc:
        return None, {
            "hardening": "failed",
            "path": "comparative_average_balance",
            "failure_type": type(exc).__name__,
            "failure_detail": str(exc),
        }


def _decimal_to_float(value: Decimal | None) -> float | None:
    """
    Convert canonical Decimal balance to float for opening/closing payload.

    Note: opening/closing balance payloads are auxiliary inputs to the engine,
    not outward-computed metrics. The outward-computed average goes through
    project_number() in _finalize_and_project_average(). This helper is only
    used for the opening_* and closing_* payload values which feed back into
    normalize_inputs() as raw metric inputs.
    """
    if value is None:
        return None
    return float(value)


def _unique_strings(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))
