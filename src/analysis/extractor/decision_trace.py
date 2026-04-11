from __future__ import annotations

from enum import StrEnum

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
