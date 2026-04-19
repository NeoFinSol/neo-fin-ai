"""
DerivedMetric and supporting contracts for Math Layer v2.

Wave 1b: Three-field numeric model.
- canonical_value: engine-owned canonical Decimal truth
- projected_value: projection-owned outward-compatible float
- value: read-only computed compatibility alias derived from projected_value

Ownership rules:
- Engine MUST assign canonical_value from canonical finalization path.
- Projection boundary MUST assign projected_value.
- value MUST NOT be assigned manually — it is computed from projected_value.
- Serializer MUST NOT repair missing fields.

Surface exposure policy (Wave 1b):
- REST surface:     canonical_value=internal-only, projected_value=internal-only,
                    value=exposed (via project_legacy_ratios() bridge)
- WebSocket surface: same as REST — DerivedMetric is internal to math layer;
                    outward payloads use float | None from legacy projection bridge
- Internal/debug:   all three fields accessible via model_dump()

DerivedMetric does not appear directly in REST or WebSocket payloads.
Outward consumers receive float | None via project_legacy_ratios() → calculate_ratios().
"""

from __future__ import annotations

from decimal import Decimal
from enum import Enum
from typing import Annotated, Any, TypeAlias

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    PlainSerializer,
    computed_field,
    model_validator,
)

# Wave 1b: canonical_value serializes as JSON number (float), not string.
# This prevents silent Decimal→string migration in JSON output.
_DecimalAsFloat = Annotated[Decimal, PlainSerializer(float, return_type=float)]


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
    """
    Outward-authoritative metric result with three-field numeric contract.

    Numeric field ownership (Wave 1b):
    - canonical_value: assigned by engine/canonical path only
    - projected_value: assigned by projection boundary only
    - value: computed compatibility alias — never assigned manually

    Allowed outward-complete states:
      State A (no numeric result): canonical_value=None, projected_value=None
      State B (complete):          canonical_value=Decimal, projected_value=float

    Forbidden outward-complete states:
      F1: canonical_value=None,    projected_value=float
      F2: canonical_value=Decimal, projected_value=None
      F3: value != projected_value (structurally impossible via computed_field)
    """

    model_config = ConfigDict(extra="forbid")

    metric_id: str
    # Wave 1b: canonical Decimal truth — engine-owned.
    # Serializes as JSON number (float) via PlainSerializer.
    canonical_value: _DecimalAsFloat | None = None
    # Wave 1b: projection-owned outward-compatible float
    projected_value: float | None = None
    unit: MetricUnit
    formula_id: str
    formula_version: str
    validity_state: ValidityState
    inputs_used: list[MetricInputRef] = Field(default_factory=list)
    reason_codes: list[str] = Field(default_factory=list)
    confidence: float | None = None
    confidence_components: dict[str, Any] = Field(default_factory=dict)
    trace: dict[str, Any]

    @computed_field  # type: ignore[prop-decorator]
    @property
    def value(self) -> float | None:
        """
        Read-only compatibility alias derived from projected_value.

        Wave 1b contract:
        - value == projected_value for all outward-complete results
        - value is None iff projected_value is None
        - value MUST NOT be assigned manually
        """
        if self.projected_value is None:
            return None
        return float(self.projected_value)

    @model_validator(mode="after")
    def _enforce_lifecycle_invariants(self) -> "DerivedMetric":
        """
        Enforce forbidden outward-complete field combinations (Wave 1b).

        F1: canonical absent, projected present — forbidden
        F2: canonical present, projected absent — forbidden
        """
        canonical_present = self.canonical_value is not None
        projected_present = self.projected_value is not None

        if not canonical_present and projected_present:
            raise ValueError(
                "DerivedMetric lifecycle violation (F1): "
                "projected_value is set but canonical_value is None. "
                "Engine must assign canonical_value before projection."
            )
        if canonical_present and not projected_present:
            raise ValueError(
                "DerivedMetric lifecycle violation (F2): "
                "canonical_value is set but projected_value is None. "
                "Projection boundary must assign projected_value after canonical."
            )
        return self

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
        """Build an invalid/refusal result with no numeric fields populated."""
        trace = {
            "status": "invalid",
            "reason_codes": list(reason_codes),
            "inputs_snapshot": dict(inputs_snapshot),
            "formula_id": formula_id,
            "formula_version": formula_version,
        }
        return cls(
            metric_id=metric_id,
            canonical_value=None,
            projected_value=None,
            unit=unit,
            formula_id=formula_id,
            formula_version=formula_version,
            validity_state=ValidityState.INVALID,
            inputs_used=[],
            reason_codes=list(reason_codes),
            trace=trace,
        )
