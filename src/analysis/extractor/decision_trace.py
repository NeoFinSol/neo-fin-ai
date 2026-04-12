from __future__ import annotations

import dataclasses
import hashlib
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from src.analysis.extractor.types import RawMetricCandidate
from src.analysis.extractor.semantics import (
    EVENT_ANNOTATED,
    EVENT_DROPPED,
    EVENT_INVALIDATED,
    EVENT_REPLACED,
    GuardrailEvent,
    SemanticsDecisionLog,
)
from src.analysis.extractor.types import ExtractionMetadata, RawCandidates

if TYPE_CHECKING:
    from src.analysis.extractor.types import ExtractionSource, ProfileKey

ReasonCode = str

REASON_BELOW_CONFIDENCE_THRESHOLD: ReasonCode = "below_confidence_threshold"
REASON_LOWER_CONFIDENCE: ReasonCode = "lower_confidence"


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


def build_candidate_id(metric_key: str, candidate: RawMetricCandidate) -> str:
    value_hash = _short_value_hash(candidate.value)
    return f"{metric_key}::{candidate.source}::{candidate.match_semantics}::{candidate.inference_mode}::{value_hash}"


_GUARDRAIL_ACTION_MAP: dict[str, DecisionAction] = {
    EVENT_ANNOTATED: DecisionAction.SELECTED,
    EVENT_REPLACED: DecisionAction.REPLACED,
    EVENT_DROPPED: DecisionAction.DROPPED,
    EVENT_INVALIDATED: DecisionAction.INVALIDATED,
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
    """Serialize DecisionTrace to a JSON-compatible dict.

    Recursively normalizes StrEnum values to strings and tuples to lists.
    """
    return _normalize_trace_value(asdict(trace))


def _derive_final_state(outcomes: list[CandidateOutcomeTrace]) -> MetricFinalState:
    has_winner = any(o.outcome == CandidateOutcomeKind.WINNER for o in outcomes)
    if has_winner:
        return MetricFinalState.SELECTED
    outcome_kinds = {o.outcome for o in outcomes}
    if CandidateOutcomeKind.INVALIDATED in outcome_kinds:
        return MetricFinalState.INVALIDATED
    if CandidateOutcomeKind.FILTERED_OUT in outcome_kinds:
        return MetricFinalState.FILTERED_OUT
    return MetricFinalState.ABSENT


def _classify_candidate(
    metric_key: str,
    candidate_id: str,
    winner_id: str | None,
    confidence: float,
    threshold: float,
    invalidated_metric_keys: frozenset[str],
) -> CandidateOutcomeKind:
    if metric_key in invalidated_metric_keys:
        return CandidateOutcomeKind.INVALIDATED
    if winner_id is not None and candidate_id == winner_id:
        return CandidateOutcomeKind.WINNER
    if confidence < threshold:
        return CandidateOutcomeKind.FILTERED_OUT
    return CandidateOutcomeKind.LOSER


def _build_candidate_trace(
    metric_key: str,
    candidate: RawMetricCandidate,
    decision_log: SemanticsDecisionLog | None,
) -> MetricCandidateTrace:
    cid = build_candidate_id(metric_key, candidate)
    if decision_log is not None:
        return MetricCandidateTrace(
            candidate_id=cid,
            profile_key=(
                candidate.source,
                candidate.match_semantics,
                candidate.inference_mode,
            ),
            value=candidate.value,
            confidence=decision_log.final_confidence,
            quality_delta=decision_log.quality_delta,
            structural_bonus=decision_log.structural_bonus,
            conflict_penalty=decision_log.conflict_penalty,
            guardrail_penalty=decision_log.guardrail_penalty,
            candidate_quality=decision_log.candidate_quality,
            signal_flags=list(decision_log.signal_flags),
            reason_code=decision_log.reason_code,
        )
    return MetricCandidateTrace(
        candidate_id=cid,
        profile_key=(
            candidate.source,
            candidate.match_semantics,
            candidate.inference_mode,
        ),
        value=candidate.value,
        confidence=0.0,
        quality_delta=0.0,
        structural_bonus=0.0,
        conflict_penalty=0.0,
        guardrail_penalty=0.0,
        candidate_quality=None,
        signal_flags=[],
        reason_code=None,
    )


def _build_metric_outcomes(
    metric_key: str,
    candidate: RawMetricCandidate | None,
    winner_id: str | None,
    confidence_threshold: float,
    invalidated_metric_keys: frozenset[str],
    guardrail_events: list[GuardrailEvent],
    decision_log: SemanticsDecisionLog | None,
) -> list[CandidateOutcomeTrace]:
    if candidate is None:
        return []
    ct = _build_candidate_trace(metric_key, candidate, decision_log)
    classified = _classify_candidate(
        metric_key,
        ct.candidate_id,
        winner_id,
        ct.confidence,
        confidence_threshold,
        invalidated_metric_keys,
    )
    outcome_reason: ReasonCode | None = None
    outcome_step = DecisionStepKind.RANKING

    if classified == CandidateOutcomeKind.INVALIDATED:
        outcome_step = DecisionStepKind.GUARDRAIL
        inv_events = [
            e
            for e in guardrail_events
            if e.metric_key == metric_key and e.action == EVENT_INVALIDATED
        ]
        outcome_reason = inv_events[0].reason_code if inv_events else None
    elif classified == CandidateOutcomeKind.FILTERED_OUT:
        outcome_step = DecisionStepKind.CONFIDENCE_FILTER
        outcome_reason = REASON_BELOW_CONFIDENCE_THRESHOLD
    elif classified == CandidateOutcomeKind.LOSER:
        outcome_reason = REASON_LOWER_CONFIDENCE

    return [
        CandidateOutcomeTrace(
            candidate=ct,
            outcome=classified,
            outcome_step=outcome_step,
            outcome_reason_code=outcome_reason,
        )
    ]


def _build_cross_cutting_steps(
    metric_key: str,
    llm_merge_trace: LLMMergeTrace | None,
    issuer_overrides: list[IssuerOverrideTrace],
) -> list[DecisionStep]:
    steps: list[DecisionStep] = []
    if llm_merge_trace is not None:
        if metric_key in llm_merge_trace.contributed:
            steps.append(
                DecisionStep(
                    step=DecisionStepKind.LLM_MERGE,
                    action=DecisionAction.MERGED,
                    reason_code=None,
                    detail=f"LLM contributed value for {metric_key}",
                )
            )
        for rejection in llm_merge_trace.rejected:
            if rejection.metric_key == metric_key:
                steps.append(
                    DecisionStep(
                        step=DecisionStepKind.LLM_MERGE,
                        action=DecisionAction.DROPPED,
                        reason_code=rejection.reason_code,
                        detail=f"LLM rejected for {metric_key}: {rejection.reason_code}",
                    )
                )
    for override in issuer_overrides:
        if override.metric_key == metric_key:
            steps.append(
                DecisionStep(
                    step=DecisionStepKind.ISSUER_OVERRIDE,
                    action=DecisionAction.OVERRIDDEN,
                    reason_code=override.reason_code,
                    detail=(
                        f"issuer override for {metric_key}: "
                        f"discrepancy {override.discrepancy_pct}%"
                    ),
                )
            )
    return steps


def _build_reason_path(
    metric_key: str,
    final_state: MetricFinalState,
    metric_guard_events: list[GuardrailEvent],
    llm_merge_trace: LLMMergeTrace | None,
    issuer_overrides: list[IssuerOverrideTrace],
) -> list[DecisionStep]:
    reason_path: list[DecisionStep] = []
    for ev in metric_guard_events:
        mapped_action = _guardrail_action_to_decision_action(ev.action)
        if mapped_action is not None:
            reason_path.append(
                DecisionStep(
                    step=DecisionStepKind.GUARDRAIL,
                    action=mapped_action,
                    reason_code=ev.reason_code,
                    detail=f"guardrail at stage={ev.stage}: {ev.action}",
                )
            )
    reason_path.extend(
        _build_cross_cutting_steps(metric_key, llm_merge_trace, issuer_overrides)
    )
    if final_state == MetricFinalState.SELECTED:
        reason_path.append(
            DecisionStep(
                step=DecisionStepKind.RANKING,
                action=DecisionAction.SELECTED,
                reason_code=None,
                detail=f"selected winner for {metric_key}",
            )
        )
    return reason_path


def _format_metric_summary(
    metric_key: str,
    final_state: MetricFinalState,
    outcomes: list[CandidateOutcomeTrace],
) -> str:
    if final_state == MetricFinalState.ABSENT:
        return f"{metric_key}: no candidate selected"
    winner = next(
        (o for o in outcomes if o.outcome == CandidateOutcomeKind.WINNER), None
    )
    if winner is None:
        return f"{metric_key}: {final_state.value}"
    source = winner.candidate.profile_key[0]
    match_semantics = winner.candidate.profile_key[1]
    return (
        f"{metric_key}: selected from {source}/{match_semantics} "
        f"with confidence {winner.candidate.confidence:.2f}"
    )


def _format_pipeline_summary(
    llm_merge: LLMMergeTrace | None,
    issuer_overrides: list[IssuerOverrideTrace],
) -> str:
    parts: list[str] = []
    if llm_merge is not None:
        n = len(llm_merge.contributed)
        r = len(llm_merge.rejected)
        parts.append(f"LLM: {n} contributed, {r} rejected")
    if issuer_overrides:
        parts.append(f"Issuer overrides: {len(issuer_overrides)} metrics")
    if not parts:
        return "No cross-cutting pipeline overrides applied"
    return "; ".join(parts)


def _build_pipeline_trace(
    llm_merge_trace: LLMMergeTrace | None,
    issuer_overrides: list[IssuerOverrideTrace],
    confidence_threshold: float,
    policy_name: str,
) -> PipelineDecisionTrace:
    return PipelineDecisionTrace(
        llm_merge=llm_merge_trace,
        issuer_overrides=list(issuer_overrides),
        confidence_threshold=confidence_threshold,
        policy_name=policy_name,
        human_summary=_format_pipeline_summary(llm_merge_trace, issuer_overrides),
    )


def _build_metric_decision_trace(
    metric_key: str,
    candidate: RawMetricCandidate | None,
    winner_id: str | None,
    confidence_threshold: float,
    invalidated_metric_keys: frozenset[str],
    guardrail_events: list[GuardrailEvent],
    decision_log: SemanticsDecisionLog | None,
    llm_merge_trace: LLMMergeTrace | None,
    issuer_overrides: list[IssuerOverrideTrace],
) -> MetricDecisionTrace:
    outcomes = _build_metric_outcomes(
        metric_key,
        candidate,
        winner_id,
        confidence_threshold,
        invalidated_metric_keys,
        guardrail_events,
        decision_log,
    )

    metric_guard_events = [ev for ev in guardrail_events if ev.metric_key == metric_key]
    guards_ref = metric_guard_events if metric_guard_events else None
    final_state = _derive_final_state(outcomes)

    reason_path = _build_reason_path(
        metric_key,
        final_state,
        metric_guard_events,
        llm_merge_trace,
        issuer_overrides,
    )

    summary = _format_metric_summary(metric_key, final_state, outcomes)
    return MetricDecisionTrace(
        metric_key=metric_key,
        final_state=final_state,
        outcomes=outcomes,
        reason_path=reason_path,
        guardrail_events=guards_ref,
        human_summary=summary,
    )


def build_decision_trace(
    raw_candidates: RawCandidates,
    metadata: dict[str, ExtractionMetadata],
    decision_logs: dict[str, SemanticsDecisionLog],
    guardrail_events: list[GuardrailEvent],
    winner_map: dict[str, str | None],
    llm_merge_trace: LLMMergeTrace | None,
    issuer_overrides: list[IssuerOverrideTrace],
    confidence_threshold: float,
    policy_name: str,
) -> DecisionTrace:
    """Build a DecisionTrace from extraction pipeline artifacts.

    Produces a derived, read-only view of why each metric was selected,
    filtered, invalidated, or marked absent.  Does not affect runtime
    decisions or modify any input data.
    """
    invalidated_metric_keys: frozenset[str] = frozenset(
        ev.metric_key for ev in guardrail_events if ev.action == EVENT_INVALIDATED
    )

    per_metric: dict[str, MetricDecisionTrace] = {}
    all_metric_keys = (
        set(raw_candidates.keys()) | set(metadata.keys()) | set(winner_map.keys())
    )

    for metric_key in sorted(all_metric_keys):
        per_metric[metric_key] = _build_metric_decision_trace(
            metric_key,
            raw_candidates.get(metric_key),
            winner_map.get(metric_key),
            confidence_threshold,
            invalidated_metric_keys,
            guardrail_events,
            decision_logs.get(metric_key),
            llm_merge_trace,
            issuer_overrides,
        )

    pipeline = _build_pipeline_trace(
        llm_merge_trace,
        issuer_overrides,
        confidence_threshold,
        policy_name,
    )

    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    missing: list[str] = []
    if llm_merge_trace is None and any(m.source == "llm" for m in metadata.values()):
        missing.append("llm_merge_trace")

    return DecisionTrace(
        per_metric=per_metric,
        pipeline=pipeline,
        generated_at=generated_at,
        is_complete=len(missing) == 0,
        missing_components=missing,
    )
