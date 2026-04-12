from __future__ import annotations

from enum import Enum
from typing import Any, TypeAlias

from pydantic import BaseModel, ConfigDict, Field


class MetricUnit(str, Enum):
    RATIO = "ratio"
    PERCENT = "percent"
    CURRENCY = "currency"
    DAYS = "days"
    TURNS = "turns"


class ValidityState(str, Enum):
    VALID = "valid"
    # PARTIAL reserved for future partial-computation semantics
    PARTIAL = "partial"
    INVALID = "invalid"
    NOT_APPLICABLE = "not_applicable"
    SUPPRESSED = "suppressed"


class MetricInputRef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    metric_key: str
    value: float | None = None
    confidence: float | None = None
    unit: str | None = None
    source: str | None = None
    reason_codes: list[str] = Field(default_factory=list)


TypedInputs: TypeAlias = dict[str, MetricInputRef]


class MetricComputationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: float | None = None
    trace: dict[str, Any] = Field(default_factory=dict)
    extra_reason_codes: list[str] = Field(default_factory=list)


class DerivedMetric(BaseModel):
    model_config = ConfigDict(extra="forbid")

    metric_id: str
    value: float | None = None
    unit: MetricUnit
    formula_id: str
    formula_version: str
    validity_state: ValidityState
    inputs_used: list[MetricInputRef] = Field(default_factory=list)
    reason_codes: list[str] = Field(default_factory=list)
    confidence: float | None = None
    confidence_components: dict[str, Any] = Field(default_factory=dict)
    trace: dict[str, Any]

    @classmethod
    def invalid(
        cls,
        metric_id: str,
        formula_id: str,
        formula_version: str,
        reason_codes: list[str],
        inputs_snapshot: dict[str, Any],
        unit: MetricUnit = MetricUnit.RATIO,
    ) -> "DerivedMetric":
        trace = {
            "status": "invalid",
            "reason_codes": list(reason_codes),
            "inputs_snapshot": dict(inputs_snapshot),
            "formula_id": formula_id,
            "formula_version": formula_version,
        }
        return cls(
            metric_id=metric_id,
            value=None,
            unit=unit,
            formula_id=formula_id,
            formula_version=formula_version,
            validity_state=ValidityState.INVALID,
            inputs_used=[],
            reason_codes=list(reason_codes),
            trace=trace,
        )
