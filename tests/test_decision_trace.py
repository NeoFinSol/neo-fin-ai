from __future__ import annotations

from src.analysis.extractor.decision_trace import (
    CandidateOutcomeKind,
    DecisionAction,
    DecisionStepKind,
    MetricFinalState,
    ReasonCode,
)


def test_reason_code_is_str_alias() -> None:
    assert ReasonCode is str


class TestDecisionStepKind:
    @staticmethod
    def test_ranking() -> None:
        assert DecisionStepKind.RANKING == "ranking"

    @staticmethod
    def test_confidence_filter() -> None:
        assert DecisionStepKind.CONFIDENCE_FILTER == "confidence_filter"

    @staticmethod
    def test_guardrail() -> None:
        assert DecisionStepKind.GUARDRAIL == "guardrail"

    @staticmethod
    def test_llm_merge() -> None:
        assert DecisionStepKind.LLM_MERGE == "llm_merge"

    @staticmethod
    def test_issuer_override() -> None:
        assert DecisionStepKind.ISSUER_OVERRIDE == "issuer_override"

    @staticmethod
    def test_member_count() -> None:
        assert len(DecisionStepKind) == 5


class TestDecisionAction:
    @staticmethod
    def test_selected() -> None:
        assert DecisionAction.SELECTED == "selected"

    @staticmethod
    def test_dropped() -> None:
        assert DecisionAction.DROPPED == "dropped"

    @staticmethod
    def test_replaced() -> None:
        assert DecisionAction.REPLACED == "replaced"

    @staticmethod
    def test_invalidated() -> None:
        assert DecisionAction.INVALIDATED == "invalidated"

    @staticmethod
    def test_merged() -> None:
        assert DecisionAction.MERGED == "merged"

    @staticmethod
    def test_overridden() -> None:
        assert DecisionAction.OVERRIDDEN == "overridden"

    @staticmethod
    def test_member_count() -> None:
        assert len(DecisionAction) == 6


class TestMetricFinalState:
    @staticmethod
    def test_selected() -> None:
        assert MetricFinalState.SELECTED == "selected"

    @staticmethod
    def test_absent() -> None:
        assert MetricFinalState.ABSENT == "absent"

    @staticmethod
    def test_filtered_out() -> None:
        assert MetricFinalState.FILTERED_OUT == "filtered_out"

    @staticmethod
    def test_invalidated() -> None:
        assert MetricFinalState.INVALIDATED == "invalidated"

    @staticmethod
    def test_member_count() -> None:
        assert len(MetricFinalState) == 4


class TestCandidateOutcomeKind:
    @staticmethod
    def test_winner() -> None:
        assert CandidateOutcomeKind.WINNER == "winner"

    @staticmethod
    def test_loser() -> None:
        assert CandidateOutcomeKind.LOSER == "loser"

    @staticmethod
    def test_filtered_out() -> None:
        assert CandidateOutcomeKind.FILTERED_OUT == "filtered_out"

    @staticmethod
    def test_invalidated() -> None:
        assert CandidateOutcomeKind.INVALIDATED == "invalidated"

    @staticmethod
    def test_member_count() -> None:
        assert len(CandidateOutcomeKind) == 4
