from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.analysis.extractor.semantics import GuardrailEvent
    from src.analysis.extractor.types import ExtractionSource, ProfileKey

ReasonCode = str


class DecisionStepKind(StrEnum):
    RANKING = "ranking"
    CONFIDENCE_FILTER = "confidence_filter"
    GUARDRAIL = "guardrail"
    LLM_MERGE = "llm_merge"
    ISSUER_OVERRIDE = "issuer_override"


class DecisionAction(StrEnum):
    SELECTED = "selected"
    DROPPED = "dropped"
    REPLACED = "replaced"
    INVALIDATED = "invalidated"
    MERGED = "merged"
    OVERRIDDEN = "overridden"


class MetricFinalState(StrEnum):
    SELECTED = "selected"
    ABSENT = "absent"
    FILTERED_OUT = "filtered_out"
    INVALIDATED = "invalidated"


class CandidateOutcomeKind(StrEnum):
    WINNER = "winner"
    LOSER = "loser"
    FILTERED_OUT = "filtered_out"
    INVALIDATED = "invalidated"


@dataclass(frozen=True, slots=True)
class MetricCandidateTrace:
    candidate_id: str
    profile_key: ProfileKey
    value: float | None
    confidence: float
    quality_delta: float
    structural_bonus: float
    conflict_penalty: float
    guardrail_penalty: float
    candidate_quality: int | None
    signal_flags: list[str]
    reason_code: ReasonCode | None


@dataclass(frozen=True, slots=True)
class CandidateOutcomeTrace:
    candidate: MetricCandidateTrace
    outcome: CandidateOutcomeKind
    outcome_step: DecisionStepKind
    outcome_reason_code: ReasonCode | None


@dataclass(frozen=True, slots=True)
class DecisionStep:
    step: DecisionStepKind
    action: DecisionAction
    reason_code: ReasonCode | None
    detail: str | None


@dataclass(frozen=True, slots=True)
class MetricDecisionTrace:
    metric_key: str
    final_state: MetricFinalState
    outcomes: list[CandidateOutcomeTrace]
    reason_path: list[DecisionStep]
    guardrail_events: list[GuardrailEvent] | None = None
    human_summary: str = ""


@dataclass(frozen=True, slots=True)
class RejectionTrace:
    metric_key: str
    winner_profile: ProfileKey
    loser_profile: ProfileKey
    reason_code: ReasonCode
    reason_detail: str | None


@dataclass(frozen=True, slots=True)
class LLMMergeTrace:
    contributed: list[str]
    rejected: list[RejectionTrace]


@dataclass(frozen=True, slots=True)
class IssuerOverrideTrace:
    metric_key: str
    original_value: float | None
    original_source: ExtractionSource
    override_value: float | None
    discrepancy_pct: float | None
    reason_code: ReasonCode


@dataclass(frozen=True, slots=True)
class PipelineDecisionTrace:
    llm_merge: LLMMergeTrace | None
    issuer_overrides: list[IssuerOverrideTrace]
    confidence_threshold: float
    policy_name: str
    human_summary: str = ""


@dataclass(frozen=True, slots=True)
class DecisionTrace:
    per_metric: dict[str, MetricDecisionTrace]
    pipeline: PipelineDecisionTrace
    generated_at: str
    is_complete: bool = True
    missing_components: list[str] = field(default_factory=list)
    trace_version: str = "v1"
