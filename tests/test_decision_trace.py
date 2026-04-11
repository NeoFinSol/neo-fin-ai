from __future__ import annotations

import dataclasses

from src.analysis.extractor.decision_trace import (
    CandidateOutcomeKind,
    CandidateOutcomeTrace,
    DecisionAction,
    DecisionStep,
    DecisionStepKind,
    DecisionTrace,
    IssuerOverrideTrace,
    LLMMergeTrace,
    MetricCandidateTrace,
    MetricDecisionTrace,
    MetricFinalState,
    PipelineDecisionTrace,
    ReasonCode,
    RejectionTrace,
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


class TestMetricCandidateTraceFields:
    EXPECTED = [
        "candidate_id",
        "profile_key",
        "value",
        "confidence",
        "quality_delta",
        "structural_bonus",
        "conflict_penalty",
        "guardrail_penalty",
        "candidate_quality",
        "signal_flags",
        "reason_code",
    ]

    @staticmethod
    def test_field_names() -> None:
        names = [f.name for f in dataclasses.fields(MetricCandidateTrace)]
        assert names == TestMetricCandidateTraceFields.EXPECTED


class TestCandidateOutcomeTraceFields:
    EXPECTED = [
        "candidate",
        "outcome",
        "outcome_step",
        "outcome_reason_code",
    ]

    @staticmethod
    def test_field_names() -> None:
        names = [f.name for f in dataclasses.fields(CandidateOutcomeTrace)]
        assert names == TestCandidateOutcomeTraceFields.EXPECTED


class TestDecisionStepFields:
    EXPECTED = ["step", "action", "reason_code", "detail"]

    @staticmethod
    def test_field_names() -> None:
        names = [f.name for f in dataclasses.fields(DecisionStep)]
        assert names == TestDecisionStepFields.EXPECTED


class TestMetricDecisionTraceFields:
    EXPECTED = [
        "metric_key",
        "final_state",
        "outcomes",
        "reason_path",
        "guardrail_events",
        "human_summary",
    ]

    @staticmethod
    def test_field_names() -> None:
        names = [f.name for f in dataclasses.fields(MetricDecisionTrace)]
        assert names == TestMetricDecisionTraceFields.EXPECTED

    @staticmethod
    def test_guardrail_events_default_is_none() -> None:
        flds = {f.name: f for f in dataclasses.fields(MetricDecisionTrace)}
        assert flds["guardrail_events"].default is None


class TestRejectionTraceFields:
    EXPECTED = [
        "metric_key",
        "winner_profile",
        "loser_profile",
        "reason_code",
        "reason_detail",
    ]

    @staticmethod
    def test_field_names() -> None:
        names = [f.name for f in dataclasses.fields(RejectionTrace)]
        assert names == TestRejectionTraceFields.EXPECTED


class TestLLMMergeTraceFields:
    EXPECTED = ["contributed", "rejected"]

    @staticmethod
    def test_field_names() -> None:
        names = [f.name for f in dataclasses.fields(LLMMergeTrace)]
        assert names == TestLLMMergeTraceFields.EXPECTED


class TestIssuerOverrideTraceFields:
    EXPECTED = [
        "metric_key",
        "original_value",
        "original_source",
        "override_value",
        "discrepancy_pct",
        "reason_code",
    ]

    @staticmethod
    def test_field_names() -> None:
        names = [f.name for f in dataclasses.fields(IssuerOverrideTrace)]
        assert names == TestIssuerOverrideTraceFields.EXPECTED


class TestPipelineDecisionTraceFields:
    EXPECTED = [
        "llm_merge",
        "issuer_overrides",
        "confidence_threshold",
        "policy_name",
        "human_summary",
    ]

    @staticmethod
    def test_field_names() -> None:
        names = [f.name for f in dataclasses.fields(PipelineDecisionTrace)]
        assert names == TestPipelineDecisionTraceFields.EXPECTED


class TestDecisionTraceFields:
    EXPECTED = [
        "per_metric",
        "pipeline",
        "generated_at",
        "is_complete",
        "missing_components",
        "trace_version",
    ]

    @staticmethod
    def test_field_names() -> None:
        names = [f.name for f in dataclasses.fields(DecisionTrace)]
        assert names == TestDecisionTraceFields.EXPECTED

    @staticmethod
    def test_generated_at_before_is_complete() -> None:
        names = [f.name for f in dataclasses.fields(DecisionTrace)]
        ga_idx = names.index("generated_at")
        ic_idx = names.index("is_complete")
        assert ga_idx < ic_idx
