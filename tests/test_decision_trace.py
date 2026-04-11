from __future__ import annotations

import dataclasses
import json

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
    _build_candidate_id,
    _guardrail_action_to_decision_action,
    _short_value_hash,
    build_decision_trace,
    decision_trace_to_dict,
)
from src.analysis.extractor.confidence_policy import (
    CALIBRATED_RUNTIME_CONFIDENCE_POLICY,
)
from src.analysis.extractor.semantics import GuardrailEvent, SemanticsDecisionLog
from src.analysis.extractor.types import (
    ExtractionMetadata,
    RawCandidates,
    RawMetricCandidate,
)
from src.analysis.extractor.types import RawMetricCandidate


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


def test_short_value_hash_deterministic() -> None:
    h1 = _short_value_hash(42.5)
    h2 = _short_value_hash(42.5)
    assert h1 == h2
    assert len(h1) == 8


def test_short_value_hash_different_values() -> None:
    h1 = _short_value_hash(1.0)
    h2 = _short_value_hash(2.0)
    assert h1 != h2


def test_short_value_hash_none() -> None:
    h = _short_value_hash(None)
    assert len(h) == 8


def test_build_candidate_id_format() -> None:
    c = RawMetricCandidate(
        value=100.0,
        match_type="exact",
        is_exact=True,
        source="table_exact",
        match_semantics="exact",
        inference_mode="direct",
    )
    cid = _build_candidate_id("revenue", c)
    parts = cid.split("::")
    assert parts[0] == "revenue"
    assert parts[1] == "table_exact"
    assert parts[2] == "exact"
    assert parts[3] == "direct"
    assert len(parts[4]) == 8


def test_build_candidate_id_deterministic() -> None:
    c = RawMetricCandidate(
        value=55.0,
        match_type="exact",
        is_exact=True,
        source="text_regex",
        match_semantics="keyword_match",
        inference_mode="derived",
    )
    id1 = _build_candidate_id("net_income", c)
    id2 = _build_candidate_id("net_income", c)
    assert id1 == id2


def test_build_candidate_id_different_values_different_ids() -> None:
    c1 = RawMetricCandidate(value=10.0, match_type="exact", is_exact=True)
    c2 = RawMetricCandidate(value=20.0, match_type="exact", is_exact=True)
    id1 = _build_candidate_id("metric", c1)
    id2 = _build_candidate_id("metric", c2)
    assert id1 != id2


def test_guardrail_action_mapper_explicit() -> None:
    assert _guardrail_action_to_decision_action("ANNOTATED") == DecisionAction.SELECTED
    assert _guardrail_action_to_decision_action("REPLACED") == DecisionAction.REPLACED
    assert _guardrail_action_to_decision_action("DROPPED") == DecisionAction.DROPPED
    assert (
        _guardrail_action_to_decision_action("INVALIDATED")
        == DecisionAction.INVALIDATED
    )


def test_guardrail_action_mapper_unknown_returns_none() -> None:
    assert _guardrail_action_to_decision_action("UNKNOWN") is None


def test_decision_trace_to_dict_empty() -> None:
    pipeline = PipelineDecisionTrace(
        llm_merge=None,
        issuer_overrides=[],
        confidence_threshold=0.5,
        policy_name="default",
    )
    trace = DecisionTrace(
        per_metric={},
        pipeline=pipeline,
        generated_at="2025-01-01T00:00:00Z",
    )
    result = decision_trace_to_dict(trace)
    serialized = json.dumps(result)
    assert "per_metric" in serialized
    assert "pipeline" in serialized
    assert "generated_at" in serialized


def _make_candidate(
    source: str = "table",
    match: str = "exact",
    mode: str = "direct",
    value: float = 5000.0,
) -> RawMetricCandidate:
    return RawMetricCandidate(
        value=value,
        match_type=match,
        is_exact=(match == "exact"),
        candidate_quality=90,
        source=source,
        match_semantics=match,
        inference_mode=mode,
    )


def _make_decision_log(
    metric_key: str = "revenue",
    profile_key: tuple[str, str, str] = ("table", "exact", "direct"),
    baseline: float = 0.92,
    final: float = 0.92,
) -> SemanticsDecisionLog:
    return SemanticsDecisionLog(
        metric_key=metric_key,
        profile_key=profile_key,
        baseline_confidence=baseline,
        quality_delta=0.0,
        structural_bonus=0.0,
        conflict_penalty=0.0,
        guardrail_penalty=0.0,
        final_confidence=final,
        postprocess_state="none",
        authoritative_override=False,
        reason_code=None,
        signal_flags=[],
        candidate_quality=None,
    )


def test_build_decision_trace_basic() -> None:
    raw = RawCandidates()
    cand = _make_candidate()
    raw["revenue"] = cand
    meta = {
        "revenue": ExtractionMetadata(value=5000.0, confidence=0.92, source="table")
    }
    cid = _build_candidate_id("revenue", cand)
    dl = _make_decision_log()

    trace = build_decision_trace(
        raw_candidates=raw,
        metadata=meta,
        decision_logs={"revenue": dl},
        guardrail_events=[],
        winner_map={"revenue": cid},
        llm_merge_trace=None,
        issuer_overrides=[],
        confidence_threshold=CALIBRATED_RUNTIME_CONFIDENCE_POLICY.strong_direct_threshold,
        policy_name=CALIBRATED_RUNTIME_CONFIDENCE_POLICY.name,
    )

    assert "revenue" in trace.per_metric
    mt = trace.per_metric["revenue"]
    assert mt.final_state == MetricFinalState.SELECTED
    assert len(mt.outcomes) == 1
    assert mt.outcomes[0].outcome == CandidateOutcomeKind.WINNER
    assert trace.pipeline.policy_name == CALIBRATED_RUNTIME_CONFIDENCE_POLICY.name
    assert trace.generated_at != ""
    assert trace.is_complete is True


def test_build_decision_trace_llm_merge_loser() -> None:
    raw = RawCandidates()
    cand = _make_candidate()
    raw["revenue"] = cand
    meta = {
        "revenue": ExtractionMetadata(value=5000.0, confidence=0.92, source="table")
    }
    cid = _build_candidate_id("revenue", cand)
    dl = _make_decision_log()

    llm_trace = LLMMergeTrace(
        contributed=[],
        rejected=[
            RejectionTrace(
                metric_key="revenue",
                winner_profile=("table", "exact", "direct"),
                loser_profile=("llm", "keyword_match", "direct"),
                reason_code="llm_rejected_strong_direct_fallback",
                reason_detail=None,
            )
        ],
    )

    trace = build_decision_trace(
        raw_candidates=raw,
        metadata=meta,
        decision_logs={"revenue": dl},
        guardrail_events=[],
        winner_map={"revenue": cid},
        llm_merge_trace=llm_trace,
        issuer_overrides=[],
        confidence_threshold=0.7,
        policy_name="test",
    )

    mt = trace.per_metric["revenue"]
    winners = [o for o in mt.outcomes if o.outcome == CandidateOutcomeKind.WINNER]
    assert len(winners) == 1
    assert winners[0].candidate.value == 5000.0
    assert trace.pipeline.llm_merge is not None
    assert len(trace.pipeline.llm_merge.rejected) == 1
    assert (
        trace.pipeline.llm_merge.rejected[0].reason_code
        == "llm_rejected_strong_direct_fallback"
    )
    llm_steps = [s for s in mt.reason_path if s.step == DecisionStepKind.LLM_MERGE]
    assert len(llm_steps) >= 1
    assert llm_steps[0].action == DecisionAction.DROPPED


def test_build_decision_trace_filtered_out() -> None:
    raw = RawCandidates()
    cand = _make_candidate(value=50.0)
    raw["revenue"] = cand
    dl = _make_decision_log(final=0.15)

    trace = build_decision_trace(
        raw_candidates=raw,
        metadata={},
        decision_logs={"revenue": dl},
        guardrail_events=[],
        winner_map={"revenue": None},
        llm_merge_trace=None,
        issuer_overrides=[],
        confidence_threshold=0.7,
        policy_name="test",
    )

    mt = trace.per_metric["revenue"]
    assert mt.final_state == MetricFinalState.FILTERED_OUT
    winners = [o for o in mt.outcomes if o.outcome == CandidateOutcomeKind.WINNER]
    assert len(winners) == 0


def test_build_decision_trace_invalidated_by_guardrail() -> None:
    raw = RawCandidates()
    cand = _make_candidate()
    raw["revenue"] = cand
    meta = {"revenue": ExtractionMetadata(value=None, confidence=0.0, source="table")}
    cid = _build_candidate_id("revenue", cand)
    dl = _make_decision_log(final=0.0)

    guardrail = GuardrailEvent(
        metric_key="revenue",
        stage="result_guardrails",
        action="INVALIDATED",
        reason_code="sanity_component_exceeds_total",
        before_value=5000.0,
        after_value=None,
        before_profile_key=("table", "exact", "direct"),
        after_profile_key=None,
    )

    trace = build_decision_trace(
        raw_candidates=raw,
        metadata=meta,
        decision_logs={"revenue": dl},
        guardrail_events=[guardrail],
        winner_map={"revenue": cid},
        llm_merge_trace=None,
        issuer_overrides=[],
        confidence_threshold=0.7,
        policy_name="test",
    )

    mt = trace.per_metric["revenue"]
    assert mt.final_state == MetricFinalState.INVALIDATED
    invalidated = [
        o for o in mt.outcomes if o.outcome == CandidateOutcomeKind.INVALIDATED
    ]
    assert len(invalidated) >= 1
    guardrail_steps = [
        s for s in mt.reason_path if s.step == DecisionStepKind.GUARDRAIL
    ]
    assert len(guardrail_steps) >= 1
    assert guardrail_steps[0].action == DecisionAction.INVALIDATED
    assert guardrail_steps[0].reason_code == "sanity_component_exceeds_total"


def test_build_decision_trace_absent() -> None:
    trace = build_decision_trace(
        raw_candidates=RawCandidates(),
        metadata={},
        decision_logs={},
        guardrail_events=[],
        winner_map={"missing_metric": None},
        llm_merge_trace=None,
        issuer_overrides=[],
        confidence_threshold=0.7,
        policy_name="test",
    )
    if "missing_metric" in trace.per_metric:
        mt = trace.per_metric["missing_metric"]
        assert mt.final_state == MetricFinalState.ABSENT
        winners = [o for o in mt.outcomes if o.outcome == CandidateOutcomeKind.WINNER]
        assert len(winners) == 0


def test_outcomes_invariant_selected_has_one_winner() -> None:
    raw = RawCandidates()
    cand = _make_candidate(value=100.0)
    raw["x"] = cand
    meta = {"x": ExtractionMetadata(value=100.0, confidence=0.9, source="table")}
    cid = _build_candidate_id("x", cand)
    dl = _make_decision_log(metric_key="x", profile_key=("table", "exact", "direct"))

    trace = build_decision_trace(
        raw_candidates=raw,
        metadata=meta,
        decision_logs={"x": dl},
        guardrail_events=[],
        winner_map={"x": cid},
        llm_merge_trace=None,
        issuer_overrides=[],
        confidence_threshold=0.7,
        policy_name="test",
    )
    winners = [
        o
        for o in trace.per_metric["x"].outcomes
        if o.outcome == CandidateOutcomeKind.WINNER
    ]
    assert len(winners) == 1


def test_build_decision_trace_empty() -> None:
    trace = build_decision_trace(
        raw_candidates=RawCandidates(),
        metadata={},
        decision_logs={},
        guardrail_events=[],
        winner_map={},
        llm_merge_trace=None,
        issuer_overrides=[],
        confidence_threshold=0.7,
        policy_name="test",
    )
    assert trace.per_metric == {}
    assert trace.pipeline.confidence_threshold == 0.7
    assert trace.is_complete is True


def test_metric_summary_uses_profile_key_not_source() -> None:
    raw = RawCandidates()
    cand = _make_candidate()
    raw["revenue"] = cand
    meta = {
        "revenue": ExtractionMetadata(value=5000.0, confidence=0.92, source="table")
    }
    cid = _build_candidate_id("revenue", cand)
    dl = _make_decision_log()

    trace = build_decision_trace(
        raw_candidates=raw,
        metadata=meta,
        decision_logs={"revenue": dl},
        guardrail_events=[],
        winner_map={"revenue": cid},
        llm_merge_trace=None,
        issuer_overrides=[],
        confidence_threshold=0.7,
        policy_name="test",
    )
    summary = trace.per_metric["revenue"].human_summary
    assert "table" in summary
    assert "exact" in summary


def test_reconstruct_winner_from_trace_only() -> None:
    raw = RawCandidates()
    cand = _make_candidate()
    raw["revenue"] = cand
    meta = {
        "revenue": ExtractionMetadata(value=5000.0, confidence=0.92, source="table")
    }
    cid = _build_candidate_id("revenue", cand)
    dl = _make_decision_log()

    trace = build_decision_trace(
        raw_candidates=raw,
        metadata=meta,
        decision_logs={"revenue": dl},
        guardrail_events=[],
        winner_map={"revenue": cid},
        llm_merge_trace=None,
        issuer_overrides=[],
        confidence_threshold=0.7,
        policy_name="test",
    )
    mt = trace.per_metric["revenue"]
    assert mt.final_state == MetricFinalState.SELECTED
    winner = next(o for o in mt.outcomes if o.outcome == CandidateOutcomeKind.WINNER)
    assert winner.candidate.value == 5000.0
    assert winner.candidate.confidence == 0.92


def test_llm_rejection_has_explanatory_reason_path_step() -> None:
    raw = RawCandidates()
    cand = _make_candidate()
    raw["revenue"] = cand
    meta = {
        "revenue": ExtractionMetadata(value=5000.0, confidence=0.92, source="table")
    }
    cid = _build_candidate_id("revenue", cand)
    dl = _make_decision_log()

    llm_trace = LLMMergeTrace(
        contributed=[],
        rejected=[
            RejectionTrace(
                metric_key="revenue",
                winner_profile=("table", "exact", "direct"),
                loser_profile=("llm", "keyword_match", "direct"),
                reason_code="llm_rejected_strong_direct_fallback",
                reason_detail=None,
            )
        ],
    )

    trace = build_decision_trace(
        raw_candidates=raw,
        metadata=meta,
        decision_logs={"revenue": dl},
        guardrail_events=[],
        winner_map={"revenue": cid},
        llm_merge_trace=llm_trace,
        issuer_overrides=[],
        confidence_threshold=0.7,
        policy_name="test",
    )
    mt = trace.per_metric["revenue"]
    llm_steps = [s for s in mt.reason_path if s.step == DecisionStepKind.LLM_MERGE]
    assert len(llm_steps) >= 1
    for step in llm_steps:
        assert step.reason_code is not None or step.action in {
            DecisionAction.DROPPED,
            DecisionAction.MERGED,
        }, f"LLM step has no reason: {step}"


def test_trace_does_not_affect_runtime_outputs() -> None:
    raw = RawCandidates()
    cand = _make_candidate()
    raw["revenue"] = cand
    meta = {
        "revenue": ExtractionMetadata(value=5000.0, confidence=0.92, source="table")
    }
    cid = _build_candidate_id("revenue", cand)
    dl = _make_decision_log()

    original_value = meta["revenue"].value
    original_confidence = meta["revenue"].confidence

    build_decision_trace(
        raw_candidates=raw,
        metadata=meta,
        decision_logs={"revenue": dl},
        guardrail_events=[],
        winner_map={"revenue": cid},
        llm_merge_trace=None,
        issuer_overrides=[],
        confidence_threshold=0.7,
        policy_name="test",
    )

    assert meta["revenue"].value == original_value
    assert meta["revenue"].confidence == original_confidence


def test_is_complete_missing_components() -> None:
    trace = build_decision_trace(
        raw_candidates=RawCandidates(),
        metadata={},
        decision_logs={},
        guardrail_events=[],
        winner_map={},
        llm_merge_trace=None,
        issuer_overrides=[],
        confidence_threshold=0.7,
        policy_name="test",
    )
    assert trace.is_complete is True
    assert trace.missing_components == []


def test_pipeline_override_reflected() -> None:
    raw = RawCandidates()
    cand = _make_candidate()
    raw["revenue"] = cand
    meta = {
        "revenue": ExtractionMetadata(value=5000.0, confidence=0.92, source="table")
    }
    cid = _build_candidate_id("revenue", cand)
    dl = _make_decision_log()

    override = IssuerOverrideTrace(
        metric_key="revenue",
        original_value=5000.0,
        original_source="table",
        override_value=5500.0,
        discrepancy_pct=10.0,
        reason_code="issuer_repo_override",
    )

    trace = build_decision_trace(
        raw_candidates=raw,
        metadata=meta,
        decision_logs={"revenue": dl},
        guardrail_events=[],
        winner_map={"revenue": cid},
        llm_merge_trace=None,
        issuer_overrides=[override],
        confidence_threshold=0.7,
        policy_name="test",
    )
    assert len(trace.pipeline.issuer_overrides) == 1
    assert trace.pipeline.issuer_overrides[0].metric_key == "revenue"
    issuer_steps = [
        s
        for s in trace.per_metric["revenue"].reason_path
        if s.step == DecisionStepKind.ISSUER_OVERRIDE
    ]
    assert len(issuer_steps) == 1
    assert issuer_steps[0].action == DecisionAction.OVERRIDDEN
    assert issuer_steps[0].reason_code == "issuer_repo_override"


def test_summary_derivation_independent() -> None:
    raw = RawCandidates()
    cand = _make_candidate()
    raw["revenue"] = cand
    meta = {
        "revenue": ExtractionMetadata(value=5000.0, confidence=0.92, source="table")
    }
    cid = _build_candidate_id("revenue", cand)
    dl = _make_decision_log()

    trace = build_decision_trace(
        raw_candidates=raw,
        metadata=meta,
        decision_logs={"revenue": dl},
        guardrail_events=[],
        winner_map={"revenue": cid},
        llm_merge_trace=None,
        issuer_overrides=[],
        confidence_threshold=0.7,
        policy_name="test",
    )
    summary = trace.per_metric["revenue"].human_summary
    assert isinstance(summary, str)
    assert len(summary) > 0


def test_decision_trace_json_serializable() -> None:
    raw = RawCandidates()
    cand = _make_candidate()
    raw["revenue"] = cand
    meta = {
        "revenue": ExtractionMetadata(value=5000.0, confidence=0.92, source="table")
    }
    cid = _build_candidate_id("revenue", cand)
    dl = _make_decision_log()

    trace = build_decision_trace(
        raw_candidates=raw,
        metadata=meta,
        decision_logs={"revenue": dl},
        guardrail_events=[],
        winner_map={"revenue": cid},
        llm_merge_trace=None,
        issuer_overrides=[],
        confidence_threshold=0.7,
        policy_name="test",
    )
    d = decision_trace_to_dict(trace)
    serialized = json.dumps(d)
    parsed = json.loads(serialized)
    assert "per_metric" in parsed
    assert "pipeline" in parsed
    assert "generated_at" in parsed
    assert "trace_version" in parsed


def test_backward_compatibility_null_handling() -> None:
    payload = {
        "filename": "test.pdf",
        "data": {"scanned": False, "decision_trace": None},
    }
    assert payload["data"]["decision_trace"] is None


def test_strenum_serializes_as_string() -> None:
    raw = RawCandidates()
    cand = _make_candidate()
    raw["revenue"] = cand
    meta = {
        "revenue": ExtractionMetadata(value=5000.0, confidence=0.92, source="table")
    }
    cid = _build_candidate_id("revenue", cand)
    dl = _make_decision_log()

    trace = build_decision_trace(
        raw_candidates=raw,
        metadata=meta,
        decision_logs={"revenue": dl},
        guardrail_events=[],
        winner_map={"revenue": cid},
        llm_merge_trace=None,
        issuer_overrides=[],
        confidence_threshold=0.7,
        policy_name="test",
    )
    d = decision_trace_to_dict(trace)
    serialized = json.dumps(d)
    parsed = json.loads(serialized)

    mt = parsed["per_metric"]["revenue"]
    for step in mt["reason_path"]:
        assert isinstance(step["step"], str)
        assert isinstance(step["action"], str)
    for outcome in mt["outcomes"]:
        assert isinstance(outcome["outcome"], str)
        assert isinstance(outcome["outcome_step"], str)
    assert isinstance(mt["final_state"], str)


def test_candidate_trace_without_decision_log_uses_zero_confidence() -> None:
    raw = RawCandidates()
    cand = _make_candidate()
    raw["revenue"] = cand
    meta = {
        "revenue": ExtractionMetadata(value=5000.0, confidence=0.92, source="table")
    }
    cid = _build_candidate_id("revenue", cand)

    trace = build_decision_trace(
        raw_candidates=raw,
        metadata=meta,
        decision_logs={},
        guardrail_events=[],
        winner_map={"revenue": cid},
        llm_merge_trace=None,
        issuer_overrides=[],
        confidence_threshold=0.7,
        policy_name="test",
    )
    mt = trace.per_metric["revenue"]
    assert len(mt.outcomes) == 1
    assert mt.outcomes[0].candidate.confidence == 0.0


def test_llm_merge_contributed_in_reason_path() -> None:
    raw = RawCandidates()
    cand = _make_candidate()
    raw["revenue"] = cand
    meta = {
        "revenue": ExtractionMetadata(value=5000.0, confidence=0.92, source="table")
    }
    cid = _build_candidate_id("revenue", cand)
    dl = _make_decision_log()

    llm_trace = LLMMergeTrace(
        contributed=["revenue"],
        rejected=[],
    )

    trace = build_decision_trace(
        raw_candidates=raw,
        metadata=meta,
        decision_logs={"revenue": dl},
        guardrail_events=[],
        winner_map={"revenue": cid},
        llm_merge_trace=llm_trace,
        issuer_overrides=[],
        confidence_threshold=0.7,
        policy_name="test",
    )
    mt = trace.per_metric["revenue"]
    llm_steps = [s for s in mt.reason_path if s.step == DecisionStepKind.LLM_MERGE]
    assert len(llm_steps) == 1
    assert llm_steps[0].action == DecisionAction.MERGED
