from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType
from typing import Callable

from src.analysis.math.contracts import (
    MetricComputationResult,
    MetricInputRef,
    TypedInputs,
)
from src.analysis.math.policies import (
    AveragingPolicy,
    DenominatorClass,
    DenominatorPolicy,
    SuppressionPolicy,
)
from src.analysis.math.reason_codes import (
    MATH_FORMULA_DENOMINATOR_NEAR_ZERO,
    MATH_FORMULA_DENOMINATOR_ZERO,
    MATH_FORMULA_DIVISION_ERROR,
    MATH_FORMULA_INPUT_NON_FINITE,
    MATH_FORMULA_INPUTS_MISSING,
)

MetricComputer = Callable[[TypedInputs], MetricComputationResult]
STRICT_AVERAGE_BALANCE_METRICS = frozenset({"roa", "roe", "asset_turnover"})

# Wave 2: Local near-zero threshold for _ratio() helper fail-safe guards
# NOTE: Cannot import from validators.py due to circular dependency
# (validators imports get_input_domain_constraint from registry).
# This constant MUST stay synchronized with validators.DENOMINATOR_EPSILON.
# Section 15.3 forbids local overrides, but this is an alias to avoid circular import.
_RATIO_DENOMINATOR_EPSILON = 1e-9


@dataclass(frozen=True, slots=True)
class InputDomainConstraint:
    requires_non_negative: bool = False


class MetricCoverageClass(str, Enum):
    FULLY_SUPPORTED = "FULLY_SUPPORTED"
    REPORTED_ONLY = "REPORTED_ONLY"
    DERIVED_FORMULA = "DERIVED_FORMULA"
    APPROXIMATE_ONLY = "APPROXIMATE_ONLY"
    INTENTIONALLY_SUPPRESSED = "INTENTIONALLY_SUPPRESSED"
    OUT_OF_SCOPE = "OUT_OF_SCOPE"


@dataclass(frozen=True, slots=True)
class MetricDefinition:
    metric_id: str
    formula_id: str
    formula_version: str
    required_inputs: tuple[str, ...]
    averaging_policy: AveragingPolicy
    suppression_policy: SuppressionPolicy
    compute: MetricComputer
    coverage_class: MetricCoverageClass

    # Optional denominator semantics (None = not ratio-like)
    denominator_key: str | None = None
    denominator_policy: DenominatorPolicy | None = None
    resolver_slot: str | None = None
    precedence_policy_ref: str | None = None
    average_balance_policy_ref: str | None = None
    synthetic_dependencies: frozenset[str] = frozenset()

    legacy_label: str | None = None
    frontend_key: str | None = None
    non_negative_inputs: tuple[str, ...] = ()
    # When resolver selects a family candidate not listed in required_inputs, map
    # it onto this registry input key (e.g. EBITDA family → ebitda_reported).
    resolver_required_input_prefix: str | None = None
    resolver_bridge_input_key: str | None = None


def is_ratio_like(definition: MetricDefinition) -> bool:
    """Return True if metric requires denominator policy enforcement.

    Machine-checkable ratio-like identity based on explicit denominator declaration.
    """
    return definition.denominator_key is not None


def _guard_missing_inputs(
    numerator: float | None, denominator: float | None
) -> str | None:
    """F2: Check for missing numerator or denominator.

    Returns guard failure reason string if missing, None otherwise.
    """
    if numerator is None:
        return "missing_numerator"
    if denominator is None:
        return "missing_denominator"
    return None


def _guard_non_finite(numerator: float | None, denominator: float | None) -> str | None:
    """F3: Check for non-finite values (NaN, Inf).

    Returns guard failure reason string if non-finite, None otherwise.
    Assumes inputs are not None (call _guard_missing_inputs first).
    """
    if not math.isfinite(numerator):  # type: ignore
        return "non_finite_numerator"
    if not math.isfinite(denominator):  # type: ignore
        return "non_finite_denominator"
    return None


def _guard_zero_denominator(denominator: float | None) -> str | None:
    """F4: Check for zero or signed-zero denominator.

    Returns guard failure reason string if zero, None otherwise.
    Assumes denominator is not None and is finite.
    """
    if denominator == 0:  # type: ignore
        return "zero_denominator"
    return None


def _guard_near_zero_denominator(denominator: float | None) -> str | None:
    """F5: Check for forbidden near-zero denominator.

    Returns guard failure reason string if near-zero, None otherwise.
    Assumes denominator is not None, finite, and non-zero.
    """
    if abs(denominator) < _RATIO_DENOMINATOR_EPSILON:  # type: ignore
        return "near_zero_denominator"
    return None


def _build_ratio_refusal(
    trace: dict,
    guard_failure: str,
    reason_code: str,
) -> MetricComputationResult:
    """Build structured refusal result for ratio helper guards."""
    return MetricComputationResult(
        value=None,
        trace=trace | {"guard_failure": guard_failure},
        extra_reason_codes=[reason_code],
    )


def _safe_divide(
    numerator: float,
    denominator: float,
    trace: dict,
) -> MetricComputationResult:
    """F6: Perform safe division after all guards pass.

    Includes defensive exception handling as final safety net.
    """
    try:
        result_value = numerator / denominator
        return MetricComputationResult(
            value=result_value,
            trace=trace | {"guard_status": "passed"},
        )
    except (ZeroDivisionError, OverflowError) as exc:
        return MetricComputationResult(
            value=None,
            trace=trace
            | {"guard_failure": "unexpected_division_error", "error": str(exc)},
            extra_reason_codes=[MATH_FORMULA_DIVISION_ERROR],
        )


def _ratio(numerator_key: str, denominator_key: str) -> MetricComputer:
    """F1-F11: Create a ratio computation function with fail-safe hardening.

    Wave 2: Local no-crash barrier for ratio-like computations.
    Even if engine-level validation regresses or is bypassed, direct unsafe
    invocation of _ratio() MUST NOT crash (Section 14.4).

    Args:
        numerator_key: Key for numerator input (must be in required_inputs)
        denominator_key: Key for denominator input (must be in required_inputs)

    Returns:
        MetricComputer function with comprehensive fail-safe guards.

    Guards (Section 14.1):
    - F2: Missing numerator/denominator → structured refusal
    - F3: Non-finite numerator/denominator → structured refusal
    - F4: Zero/signed-zero denominator → structured refusal
    - F5: Forbidden near-zero denominator → structured refusal
    - F6: No raw divide before all guards pass

    Reference: .agent/math_layer_v2_wave2_spec.md Section 14
    """

    def _compute(values: TypedInputs) -> MetricComputationResult:
        # Extract inputs
        numerator_ref = values.get(
            numerator_key, MetricInputRef(metric_key=numerator_key)
        )
        denominator_ref = values.get(
            denominator_key,
            MetricInputRef(metric_key=denominator_key),
        )
        numerator = numerator_ref.value
        denominator = denominator_ref.value

        trace = {
            "numerator": numerator,
            "denominator": denominator,
            "numerator_confidence": numerator_ref.confidence,
            "denominator_confidence": denominator_ref.confidence,
        }

        # Apply sequential guards
        # F2: Missing inputs
        failure = _guard_missing_inputs(numerator, denominator)
        if failure:
            reason = MATH_FORMULA_INPUTS_MISSING
            return _build_ratio_refusal(trace, failure, reason)

        # F3: Non-finite values
        failure = _guard_non_finite(numerator, denominator)
        if failure:
            reason = MATH_FORMULA_INPUT_NON_FINITE
            return _build_ratio_refusal(trace, failure, reason)

        # F4: Zero denominator
        failure = _guard_zero_denominator(denominator)
        if failure:
            reason = MATH_FORMULA_DENOMINATOR_ZERO
            return _build_ratio_refusal(trace, failure, reason)

        # F5: Near-zero denominator
        failure = _guard_near_zero_denominator(denominator)
        if failure:
            reason = MATH_FORMULA_DENOMINATOR_NEAR_ZERO
            return _build_ratio_refusal(trace, failure, reason)

        # F6: All guards passed - safe to divide
        return _safe_divide(numerator, denominator, trace)

    return _compute


def _placeholder_compute(metric_id: str) -> MetricComputer:
    def _compute(_: TypedInputs) -> MetricComputationResult:
        return MetricComputationResult(
            value=None,
            trace={"placeholder_metric": metric_id},
        )

    return _compute


def _suppressed_placeholder(
    metric_id: str,
    legacy_label: str,
    *,
    resolver_slot: str | None = None,
    precedence_policy_ref: str | None = None,
    synthetic_dependencies: frozenset[str] = frozenset(),
) -> MetricDefinition:
    """Create placeholder definition for temporarily disabled metrics.

    Suppressed placeholders are NOT ratio-like until real implementation is provided.
    denominator_key and denominator_policy are set to None to avoid misleading
    policy declarations.
    """
    return MetricDefinition(
        metric_id=metric_id,
        formula_id=metric_id,
        formula_version="v1",
        required_inputs=(),
        averaging_policy=AveragingPolicy.NONE,
        suppression_policy=SuppressionPolicy.SUPPRESS_UNSAFE,
        compute=_placeholder_compute(metric_id),
        coverage_class=MetricCoverageClass.INTENTIONALLY_SUPPRESSED,
        denominator_key=None,
        denominator_policy=None,
        resolver_slot=resolver_slot,
        precedence_policy_ref=precedence_policy_ref,
        synthetic_dependencies=synthetic_dependencies,
        legacy_label=legacy_label,
        frontend_key=metric_id,
    )


def _average_balance_metric(
    *,
    metric_id: str,
    legacy_label: str,
    numerator_key: str,
    denominator_key: str,
) -> MetricDefinition:
    """Create metric definition for average-balance ratio.

    Args:
        metric_id: Unique metric identifier
        legacy_label: Russian label for UI
        numerator_key: Numerator input key (e.g., 'net_profit')
        denominator_key: Denominator input key (e.g., 'average_total_assets')

    Returns:
        MetricDefinition with AVERAGE_BALANCE policy and STRICT_POSITIVE denominator.
    """
    return MetricDefinition(
        metric_id=metric_id,
        formula_id=metric_id,
        formula_version="v1.5",
        required_inputs=(numerator_key, denominator_key),
        averaging_policy=AveragingPolicy.AVERAGE_BALANCE,
        suppression_policy=SuppressionPolicy.NEVER,
        compute=_ratio(numerator_key, denominator_key),
        coverage_class=MetricCoverageClass.FULLY_SUPPORTED,
        denominator_key=denominator_key,
        denominator_policy=DenominatorPolicy.STRICT_POSITIVE,
        average_balance_policy_ref="opening_and_closing_required",
        synthetic_dependencies=frozenset({denominator_key}),
        legacy_label=legacy_label,
        frontend_key=metric_id,
        non_negative_inputs=(denominator_key,),
    )


REGISTRY = MappingProxyType(
    {
        "current_ratio": MetricDefinition(
            metric_id="current_ratio",
            formula_id="current_ratio",
            formula_version="v1",
            required_inputs=("current_assets", "short_term_liabilities"),
            averaging_policy=AveragingPolicy.NONE,
            suppression_policy=SuppressionPolicy.NEVER,
            compute=_ratio("current_assets", "short_term_liabilities"),
            coverage_class=MetricCoverageClass.FULLY_SUPPORTED,
            denominator_key="short_term_liabilities",
            denominator_policy=DenominatorPolicy.STRICT_POSITIVE,
            legacy_label="Коэффициент текущей ликвидности",
            frontend_key="current_ratio",
            non_negative_inputs=("current_assets", "short_term_liabilities"),
        ),
        "absolute_liquidity_ratio": MetricDefinition(
            metric_id="absolute_liquidity_ratio",
            formula_id="absolute_liquidity_ratio",
            formula_version="v1",
            required_inputs=("cash_and_equivalents", "short_term_liabilities"),
            averaging_policy=AveragingPolicy.NONE,
            suppression_policy=SuppressionPolicy.NEVER,
            compute=_ratio("cash_and_equivalents", "short_term_liabilities"),
            coverage_class=MetricCoverageClass.FULLY_SUPPORTED,
            denominator_key="short_term_liabilities",
            denominator_policy=DenominatorPolicy.STRICT_POSITIVE,
            legacy_label="Коэффициент абсолютной ликвидности",
            frontend_key="absolute_liquidity_ratio",
            non_negative_inputs=("cash_and_equivalents", "short_term_liabilities"),
        ),
        "ros": MetricDefinition(
            metric_id="ros",
            formula_id="ros",
            formula_version="v1",
            required_inputs=("net_profit", "revenue"),
            averaging_policy=AveragingPolicy.NONE,
            suppression_policy=SuppressionPolicy.NEVER,
            compute=_ratio("net_profit", "revenue"),
            coverage_class=MetricCoverageClass.FULLY_SUPPORTED,
            denominator_key="revenue",
            denominator_policy=DenominatorPolicy.STRICT_POSITIVE,
            legacy_label="Рентабельность продаж (ROS)",
            frontend_key="ros",
            non_negative_inputs=("revenue",),
        ),
        "equity_ratio": MetricDefinition(
            metric_id="equity_ratio",
            formula_id="equity_ratio",
            formula_version="v1",
            required_inputs=("equity", "total_assets"),
            averaging_policy=AveragingPolicy.NONE,
            suppression_policy=SuppressionPolicy.NEVER,
            compute=_ratio("equity", "total_assets"),
            coverage_class=MetricCoverageClass.FULLY_SUPPORTED,
            denominator_key="total_assets",
            denominator_policy=DenominatorPolicy.STRICT_POSITIVE,
            legacy_label="Коэффициент автономии",
            frontend_key="equity_ratio",
            non_negative_inputs=("equity", "total_assets"),
        ),
        "ebitda_margin": MetricDefinition(
            metric_id="ebitda_margin",
            formula_id="ebitda_margin",
            formula_version="v1",
            required_inputs=("ebitda_reported", "revenue"),
            averaging_policy=AveragingPolicy.NONE,
            suppression_policy=SuppressionPolicy.SUPPRESS_UNSAFE,
            compute=_ratio("ebitda_reported", "revenue"),
            coverage_class=MetricCoverageClass.INTENTIONALLY_SUPPRESSED,
            denominator_key="revenue",
            denominator_policy=DenominatorPolicy.STRICT_POSITIVE,
            resolver_slot="ebitda_variants",
            precedence_policy_ref="reported_over_derived",
            synthetic_dependencies=frozenset({"ebitda_reported"}),
            legacy_label="EBITDA маржа",
            frontend_key="ebitda_margin",
            non_negative_inputs=("revenue",),
            resolver_required_input_prefix="ebitda",
            resolver_bridge_input_key="ebitda_reported",
        ),
        "quick_ratio": _suppressed_placeholder(
            "quick_ratio",
            "Коэффициент быстрой ликвидности",
            resolver_slot="reported_vs_derived",
            precedence_policy_ref="reported_over_derived",
        ),
        "roa": _average_balance_metric(
            metric_id="roa",
            legacy_label="Рентабельность активов (ROA)",
            numerator_key="net_profit",
            denominator_key="average_total_assets",
        ),
        "roe": _average_balance_metric(
            metric_id="roe",
            legacy_label="Рентабельность собственного капитала (ROE)",
            numerator_key="net_profit",
            denominator_key="average_equity",
        ),
        "financial_leverage": _suppressed_placeholder(
            "financial_leverage",
            "Финансовый рычаг",
            resolver_slot="debt_basis",
            precedence_policy_ref="reported_over_derived",
            synthetic_dependencies=frozenset({"total_debt"}),
        ),
        "financial_leverage_total": _suppressed_placeholder(
            "financial_leverage_total",
            "Финансовый рычаг (обязательства/капитал)",
            resolver_slot="debt_basis",
            precedence_policy_ref="reported_over_derived",
        ),
        "financial_leverage_debt_only": _suppressed_placeholder(
            "financial_leverage_debt_only",
            "Финансовый рычаг (долг/капитал)",
            resolver_slot="debt_basis",
            precedence_policy_ref="reported_over_derived",
            synthetic_dependencies=frozenset({"total_debt"}),
        ),
        "interest_coverage": _suppressed_placeholder(
            "interest_coverage",
            "Покрытие процентов",
            resolver_slot="reported_vs_derived",
            precedence_policy_ref="reported_over_derived",
        ),
        "asset_turnover": _average_balance_metric(
            metric_id="asset_turnover",
            legacy_label="Оборачиваемость активов",
            numerator_key="revenue",
            denominator_key="average_total_assets",
        ),
        "inventory_turnover": _suppressed_placeholder(
            "inventory_turnover",
            "Оборачиваемость запасов",
            resolver_slot="reported_vs_derived",
            precedence_policy_ref="reported_over_derived",
        ),
        "receivables_turnover": _suppressed_placeholder(
            "receivables_turnover",
            "Оборачиваемость дебиторской задолженности",
            resolver_slot="reported_vs_derived",
            precedence_policy_ref="reported_over_derived",
        ),
        # =========================================================================
        # WAVE 2 PROOF METRIC — Internal test-only metric for ALLOW_ANY_NON_ZERO validation
        # Purpose: Prove that ALLOW_ANY_NON_ZERO denominator policy works correctly
        # through the full engine + classifier + evaluator + helper pipeline.
        #
        # This metric MUST NOT be exported to frontend or legacy name maps.
        # It has legacy_label=None and frontend_key=None to ensure non-export.
        #
        # TODO: Remove after Wave 2 completion (denominator policy hardening).
        # Reference: .agent/math_layer_v2_wave2_spec.md Section 17 (Proof-of-Usage)
        # =========================================================================
        "_wave2_proof_allow_any_non_zero": MetricDefinition(
            metric_id="_wave2_proof_allow_any_non_zero",
            formula_id="wave2_proof_metric",
            formula_version="v1",
            required_inputs=("proof_numerator", "proof_denominator"),
            averaging_policy=AveragingPolicy.NONE,
            suppression_policy=SuppressionPolicy.NEVER,
            compute=_ratio("proof_numerator", "proof_denominator"),
            coverage_class=MetricCoverageClass.FULLY_SUPPORTED,
            denominator_key="proof_denominator",
            denominator_policy=DenominatorPolicy.ALLOW_ANY_NON_ZERO,
            legacy_label=None,  # Explicitly None to prevent export to LEGACY_RATIO_NAME_MAP
            frontend_key=None,  # Explicitly None to prevent export to RATIO_KEY_MAP
            non_negative_inputs=(),
        ),
    }
)


def _build_legacy_ratio_name_map(
    definitions: dict[str, MetricDefinition],
) -> dict[str, str]:
    return {
        metric_id: definition.legacy_label
        for metric_id, definition in definitions.items()
        if definition.legacy_label is not None
    }


def _build_frontend_ratio_key_map(
    definitions: dict[str, MetricDefinition],
) -> dict[str, str]:
    return {
        definition.legacy_label: definition.frontend_key
        for definition in definitions.values()
        if definition.legacy_label is not None and definition.frontend_key is not None
    }


def _build_input_domain_constraints(
    definitions: dict[str, MetricDefinition],
) -> dict[str, InputDomainConstraint]:
    constraints: dict[str, InputDomainConstraint] = {}
    for definition in definitions.values():
        for metric_key in definition.non_negative_inputs:
            constraints[metric_key] = InputDomainConstraint(requires_non_negative=True)
    return constraints


LEGACY_RATIO_NAME_MAP = MappingProxyType(_build_legacy_ratio_name_map(REGISTRY))
RATIO_KEY_MAP = MappingProxyType(_build_frontend_ratio_key_map(REGISTRY))
INPUT_DOMAIN_CONSTRAINTS = MappingProxyType(_build_input_domain_constraints(REGISTRY))

# Bump together with EXPECTED_REGISTRY_SEMANTIC_HASH in startup_validation.py
# when registry semantic fields intentionally change (Wave 3 Phase 6 discipline).
REGISTRY_VERSION = "3.0.1-wave3-audit-fixes"


def get_input_domain_constraint(metric_key: str) -> InputDomainConstraint:
    return INPUT_DOMAIN_CONSTRAINTS.get(metric_key, InputDomainConstraint())
