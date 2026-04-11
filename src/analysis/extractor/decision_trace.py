from __future__ import annotations

import dataclasses
import hashlib
from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from src.analysis.extractor.types import RawMetricCandidate

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


def _short_value_hash(value: float | None) -> str:
    raw = repr(value).encode("utf-8")
    return hashlib.blake2s(raw, digest_size=4).hexdigest()


def _build_candidate_id(metric_key: str, candidate: RawMetricCandidate) -> str:
    value_hash = _short_value_hash(candidate.value)
    return f"{metric_key}::{candidate.source}::{candidate.match_semantics}::{candidate.inference_mode}::{value_hash}"


_GUARDRAIL_ACTION_MAP: dict[str, DecisionAction] = {
    "ANNOTATED": DecisionAction.SELECTED,
    "REPLACED": DecisionAction.REPLACED,
    "DROPPED": DecisionAction.DROPPED,
    "INVALIDATED": DecisionAction.INVALIDATED,
}


def _guardrail_action_to_decision_action(
    guardrail_action: str,
) -> DecisionAction | None:
    return _GUARDRAIL_ACTION_MAP.get(guardrail_action)


def _normalize_trace_value(value: Any) -> Any:
    if isinstance(value, StrEnum):
        return value.value
    if isinstance(value, tuple):
        return [_normalize_trace_value(v) for v in value]
    if isinstance(value, list):
        return [_normalize_trace_value(v) for v in value]
    if isinstance(value, dict):
        return {k: _normalize_trace_value(v) for k, v in value.items()}
    if hasattr(value, "__dataclass_fields__"):
        return _normalize_trace_value(asdict(value))
    return value


def decision_trace_to_dict(trace: DecisionTrace) -> dict:
    return _normalize_trace_value(asdict(trace))
