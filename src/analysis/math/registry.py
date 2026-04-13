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


@dataclass(frozen=True, slots=True)
class InputDomainConstraint:
    requires_non_negative: bool = False


@dataclass(frozen=True, slots=True)
class MetricDefinition:
    metric_id: str
    formula_id: str
    formula_version: str
    required_inputs: tuple[str, ...]
    denominator_key: str
    denominator_policy: DenominatorPolicy
    averaging_policy: AveragingPolicy
    suppression_policy: SuppressionPolicy
    compute: MetricComputer
    legacy_label: str | None = None
    frontend_key: str | None = None
    non_negative_inputs: tuple[str, ...] = ()


def _ratio(numerator_key: str, denominator_key: str) -> MetricComputer:
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
    return MetricDefinition(
        metric_id=metric_id,
        formula_id=metric_id,
        formula_version="v1",
        required_inputs=(),
        denominator_key=metric_id,
        denominator_policy=DenominatorPolicy.ALLOW_ANY_NON_ZERO,
        averaging_policy=AveragingPolicy.NONE,
        suppression_policy=SuppressionPolicy.SUPPRESS_UNSAFE,
        compute=_placeholder_compute(metric_id),
        legacy_label=legacy_label,
        frontend_key=metric_id,
    )


REGISTRY = MappingProxyType(
    {
        "current_ratio": MetricDefinition(
            metric_id="current_ratio",
            formula_id="current_ratio",
            formula_version="v1",
            required_inputs=("current_assets", "short_term_liabilities"),
            denominator_key="short_term_liabilities",
            denominator_policy=DenominatorPolicy.STRICT_POSITIVE,
            averaging_policy=AveragingPolicy.NONE,
            suppression_policy=SuppressionPolicy.NEVER,
            compute=_ratio("current_assets", "short_term_liabilities"),
            legacy_label="Коэффициент текущей ликвидности",
            frontend_key="current_ratio",
            non_negative_inputs=("current_assets", "short_term_liabilities"),
        ),
        "absolute_liquidity_ratio": MetricDefinition(
            metric_id="absolute_liquidity_ratio",
            formula_id="absolute_liquidity_ratio",
            formula_version="v1",
            required_inputs=("cash_and_equivalents", "short_term_liabilities"),
            denominator_key="short_term_liabilities",
            denominator_policy=DenominatorPolicy.STRICT_POSITIVE,
            averaging_policy=AveragingPolicy.NONE,
            suppression_policy=SuppressionPolicy.NEVER,
            compute=_ratio("cash_and_equivalents", "short_term_liabilities"),
            legacy_label="Коэффициент абсолютной ликвидности",
            frontend_key="absolute_liquidity_ratio",
            non_negative_inputs=("cash_and_equivalents", "short_term_liabilities"),
        ),
        "ros": MetricDefinition(
            metric_id="ros",
            formula_id="ros",
            formula_version="v1",
            required_inputs=("net_profit", "revenue"),
            denominator_key="revenue",
            denominator_policy=DenominatorPolicy.STRICT_POSITIVE,
            averaging_policy=AveragingPolicy.NONE,
            suppression_policy=SuppressionPolicy.NEVER,
            compute=_ratio("net_profit", "revenue"),
            legacy_label="Рентабельность продаж (ROS)",
            frontend_key="ros",
            non_negative_inputs=("revenue",),
        ),
        "equity_ratio": MetricDefinition(
            metric_id="equity_ratio",
            formula_id="equity_ratio",
            formula_version="v1",
            required_inputs=("equity", "total_assets"),
            denominator_key="total_assets",
            denominator_policy=DenominatorPolicy.STRICT_POSITIVE,
            averaging_policy=AveragingPolicy.NONE,
            suppression_policy=SuppressionPolicy.NEVER,
            compute=_ratio("equity", "total_assets"),
            legacy_label="Коэффициент автономии",
            frontend_key="equity_ratio",
            non_negative_inputs=("equity", "total_assets"),
        ),
        "ebitda_margin": MetricDefinition(
            metric_id="ebitda_margin",
            formula_id="ebitda_margin",
            formula_version="v1",
            required_inputs=("ebitda_reported", "revenue"),
            denominator_key="revenue",
            denominator_policy=DenominatorPolicy.STRICT_POSITIVE,
            averaging_policy=AveragingPolicy.NONE,
            suppression_policy=SuppressionPolicy.SUPPRESS_UNSAFE,
            compute=_ratio("ebitda_reported", "revenue"),
            legacy_label="EBITDA маржа",
            frontend_key="ebitda_margin",
            non_negative_inputs=("revenue",),
        ),
        "quick_ratio": _suppressed_placeholder(
            "quick_ratio",
            "Коэффициент быстрой ликвидности",
        ),
        "roa": _suppressed_placeholder("roa", "Рентабельность активов (ROA)"),
        "roe": _suppressed_placeholder(
            "roe",
            "Рентабельность собственного капитала (ROE)",
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
        "asset_turnover": _suppressed_placeholder(
            "asset_turnover",
            "Оборачиваемость активов",
        ),
        "inventory_turnover": _suppressed_placeholder(
            "inventory_turnover",
            "Оборачиваемость запасов",
        ),
        "receivables_turnover": _suppressed_placeholder(
            "receivables_turnover",
            "Оборачиваемость дебиторской задолженности",
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
