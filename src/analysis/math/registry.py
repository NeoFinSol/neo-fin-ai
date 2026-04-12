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


def _ratio(numerator_key: str, denominator_key: str) -> MetricComputer:
    def _compute(values: TypedInputs) -> MetricComputationResult:
        numerator_ref = values.get(numerator_key, MetricInputRef(metric_key=numerator_key))
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
        ),
    }
)
