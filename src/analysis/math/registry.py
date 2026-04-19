from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Callable

from src.analysis.math.contracts import (
    MetricComputationResult,
    MetricInputRef,
    TypedInputs,
)
from src.analysis.math.policies import (
    AveragingPolicy,
    DenominatorPolicy,
    SuppressionPolicy,
)

MetricComputer = Callable[[TypedInputs], MetricComputationResult]
STRICT_AVERAGE_BALANCE_METRICS = frozenset({"roa", "roe", "asset_turnover"})


@dataclass(frozen=True, slots=True)
class InputDomainConstraint:
    requires_non_negative: bool = False


@dataclass(frozen=True, slots=True)
class MetricDefinition:
    metric_id: str
    formula_id: str
    formula_version: str
    required_inputs: tuple[str, ...]
    averaging_policy: AveragingPolicy
    suppression_policy: SuppressionPolicy
    compute: MetricComputer
    
    # Optional denominator semantics (None = not ratio-like)
    denominator_key: str | None = None
    denominator_policy: DenominatorPolicy | None = None
    
    legacy_label: str | None = None
    frontend_key: str | None = None
    non_negative_inputs: tuple[str, ...] = ()


def is_ratio_like(definition: MetricDefinition) -> bool:
    """Return True if metric requires denominator policy enforcement.
    
    Machine-checkable ratio-like identity based on explicit denominator declaration.
    """
    return definition.denominator_key is not None


def _ratio(numerator_key: str, denominator_key: str) -> MetricComputer:
    """Create a ratio computation function.
    
    Args:
        numerator_key: Key for numerator input (must be in required_inputs)
        denominator_key: Key for denominator input (must be in required_inputs)
    
    Returns:
        MetricComputer function that divides numerator by denominator.
    
    Note:
        Denominator policy validation happens upstream in engine layer.
        This function assumes denominator has been validated as safe.
    """
    def _compute(values: TypedInputs) -> MetricComputationResult:
        numerator_ref = values.get(
            numerator_key, MetricInputRef(metric_key=numerator_key)
        )
        denominator_ref = values.get(
            denominator_key,
            MetricInputRef(metric_key=denominator_key),
        )
        numerator = numerator_ref.value
        denominator = denominator_ref.value
        if numerator is None or denominator is None:
            return MetricComputationResult(
                value=None,
                trace={
                    "numerator": numerator,
                    "denominator": denominator,
                    "numerator_confidence": numerator_ref.confidence,
                    "denominator_confidence": denominator_ref.confidence,
                },
                extra_reason_codes=["formula_inputs_missing"],
            )
        return MetricComputationResult(
            value=numerator / denominator,
            trace={
                "numerator": numerator,
                "denominator": denominator,
                "numerator_confidence": numerator_ref.confidence,
                "denominator_confidence": denominator_ref.confidence,
            },
        )

    return _compute


def _placeholder_compute(metric_id: str) -> MetricComputer:
    def _compute(_: TypedInputs) -> MetricComputationResult:
        return MetricComputationResult(
            value=None,
            trace={"placeholder_metric": metric_id},
        )

    return _compute


def _suppressed_placeholder(metric_id: str, legacy_label: str) -> MetricDefinition:
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
        denominator_key=None,
        denominator_policy=None,
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
        denominator_key=denominator_key,
        denominator_policy=DenominatorPolicy.STRICT_POSITIVE,
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
            denominator_key="revenue",
            denominator_policy=DenominatorPolicy.STRICT_POSITIVE,
            legacy_label="EBITDA маржа",
            frontend_key="ebitda_margin",
            non_negative_inputs=("revenue",),
        ),
        "quick_ratio": _suppressed_placeholder(
            "quick_ratio",
            "Коэффициент быстрой ликвидности",
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
        ),
        "financial_leverage_total": _suppressed_placeholder(
            "financial_leverage_total",
            "Финансовый рычаг (обязательства/капитал)",
        ),
        "financial_leverage_debt_only": _suppressed_placeholder(
            "financial_leverage_debt_only",
            "Финансовый рычаг (долг/капитал)",
        ),
        "interest_coverage": _suppressed_placeholder(
            "interest_coverage",
            "Покрытие процентов",
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
        ),
        "receivables_turnover": _suppressed_placeholder(
            "receivables_turnover",
            "Оборачиваемость дебиторской задолженности",
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


def get_input_domain_constraint(metric_key: str) -> InputDomainConstraint:
    return INPUT_DOMAIN_CONSTRAINTS.get(metric_key, InputDomainConstraint())
