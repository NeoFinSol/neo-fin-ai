from __future__ import annotations

import pytest

from src.analysis.extractor import guardrails, pipeline, ranking, semantics
from src.analysis.extractor.types import (
    DocumentSignals,
    ExtractionMetadata,
    ExtractorContext,
    RawCandidates,
)


def _context(*, text: str = "Бухгалтерский баланс") -> ExtractorContext:
    text_lower = text.lower()
    return ExtractorContext(
        tables=[],
        text=text,
        signals=DocumentSignals(
            text=text,
            text_lower=text_lower,
            has_russian_balance_header="бухгалтерский баланс" in text_lower,
            has_russian_results_header="отчет о финансовых результатах" in text_lower,
            is_form_like=False,
            is_balance_like=True,
            scale_factor=1.0,
        ),
    )


def test_pnl_sanity_drop_records_single_drop_event() -> None:
    raw = RawCandidates()
    ranking._raw_set(
        raw,
        "revenue",
        100.0,
        "text_regex",
        False,
        candidate_quality=50,
    )
    ranking._raw_set(
        raw,
        "net_profit",
        90.0,
        "text_regex",
        False,
        candidate_quality=120,
    )
    events: list[semantics.GuardrailEvent] = []

    guardrails._apply_form_like_pnl_sanity(
        raw,
        {"revenue": 100.0},
        is_standalone_form=False,
        guardrail_events=events,
    )

    assert "revenue" not in raw
    assert len(events) == 1
    assert events[0].metric_key == "revenue"
    assert events[0].action == semantics.EVENT_DROPPED
    assert events[0].reason_code == semantics.REASON_SANITY_PNL_CONFLICT_DROP_REVENUE


def test_current_assets_guardrail_records_drop_and_replacement() -> None:
    context = _context()
    raw = RawCandidates()
    ranking._raw_set(
        raw,
        "current_assets",
        50.0,
        "table",
        False,
        candidate_quality=90,
        source=semantics.SOURCE_TABLE,
        match_semantics=semantics.MATCH_SECTION,
        inference_mode=semantics.MODE_DIRECT,
    )
    ranking._raw_set(raw, "inventory", 60.0, "table", True, candidate_quality=100)
    ranking._raw_set(
        raw,
        "accounts_receivable",
        40.0,
        "table",
        True,
        candidate_quality=100,
    )
    events: list[semantics.GuardrailEvent] = []

    guardrails.derive_missing_metrics(context, raw, guardrail_events=events)

    assert raw["current_assets"].value == 100.0
    assert (
        raw["current_assets"].reason_code
        == semantics.REASON_GUARDRAIL_CURRENT_ASSETS_CANDIDATE_LT_COMPONENT_REPLACED
    )
    assert [event.action for event in events] == [
        semantics.EVENT_DROPPED,
        semantics.EVENT_REPLACED,
    ]
    assert events[0].reason_code == (
        semantics.REASON_GUARDRAIL_CURRENT_ASSETS_CANDIDATE_LT_COMPONENT_DROPPED
    )
    assert events[1].reason_code == (
        semantics.REASON_GUARDRAIL_CURRENT_ASSETS_CANDIDATE_LT_COMPONENT_REPLACED
    )


def test_build_metadata_with_decision_log_exposes_final_reason_summary() -> None:
    candidate = ranking.RawMetricCandidate(
        value=1000.0,
        match_type="text_regex",
        is_exact=False,
        candidate_quality=90,
        source=semantics.SOURCE_TEXT,
        match_semantics=semantics.MATCH_KEYWORD,
        inference_mode=semantics.MODE_DIRECT,
        reason_code=semantics.REASON_GUARDRAIL_SHORT_TERM_GT_TOTAL_ASSETS,
        signal_flags=[semantics.FLAG_POSTPROCESS_GUARDRAIL_ADJUSTED],
        postprocess_state=semantics.POSTPROCESS_GUARDRAIL,
    )

    metadata, decision_log = ranking.build_metadata_with_decision_log(
        "short_term_liabilities",
        candidate,
    )

    assert metadata.reason_code == semantics.REASON_GUARDRAIL_SHORT_TERM_GT_TOTAL_ASSETS
    assert decision_log.metric_key == "short_term_liabilities"
    assert decision_log.reason_code == (
        semantics.REASON_GUARDRAIL_SHORT_TERM_GT_TOTAL_ASSETS
    )
    assert decision_log.signal_flags == [semantics.FLAG_POSTPROCESS_GUARDRAIL_ADJUSTED]
    assert decision_log.candidate_quality == 90


def test_parse_financial_statements_debug_preserves_output_and_exposes_trace() -> None:
    tables = [{"rows": [["2110", "1 000", ""]], "flavor": "stream"}]

    baseline = pipeline.parse_financial_statements_with_metadata(tables, "")
    debug_trace = pipeline.parse_financial_statements_debug(tables, "")

    assert debug_trace.metadata == baseline
    assert debug_trace.decision_logs["revenue"].metric_key == "revenue"
    assert debug_trace.guardrail_events == []
    rendered = pipeline.format_metric_debug_trace(debug_trace, "revenue")
    assert "baseline=" in rendered
    assert "final=" in rendered


def test_debug_trace_net_profit_candidate_ignores_line_code_2300() -> None:
    tables = [
        {
            "rows": [
                ["2300", "9 000", ""],
                ["2400", "1 000", ""],
                ["2110", "100 000", ""],
            ],
            "flavor": "stream",
        }
    ]

    debug_trace = pipeline.parse_financial_statements_debug(tables, "")

    assert debug_trace.metadata["net_profit"].value == 1000.0
    assert debug_trace.raw_candidates["net_profit"].value == 1000.0
    assert debug_trace.raw_candidates["net_profit"].conflict_count == 0


def test_debug_trace_leaves_net_profit_absent_when_only_line_code_2300_exists() -> None:
    tables = [
        {
            "rows": [
                ["2300", "9 000", ""],
                ["2110", "100 000", ""],
            ],
            "flavor": "stream",
        }
    ]

    debug_trace = pipeline.parse_financial_statements_debug(tables, "")

    assert debug_trace.metadata["net_profit"].value is None
    assert debug_trace.raw_candidates.get("net_profit") is None


def test_result_guardrail_invalidation_records_chronological_event() -> None:
    context = _context()
    result = {
        "total_assets": ExtractionMetadata(
            value=100.0,
            confidence=0.92,
            source=semantics.SOURCE_TABLE,
            evidence_version=semantics.V2,
            match_semantics=semantics.MATCH_EXACT,
            inference_mode=semantics.MODE_DIRECT,
        ),
        "current_assets": ExtractionMetadata(
            value=80.0,
            confidence=0.80,
            source=semantics.SOURCE_TABLE,
            evidence_version=semantics.V2,
            match_semantics=semantics.MATCH_SECTION,
            inference_mode=semantics.MODE_DIRECT,
        ),
        "liabilities": ExtractionMetadata(
            value=90.0,
            confidence=0.80,
            source=semantics.SOURCE_TABLE,
            evidence_version=semantics.V2,
            match_semantics=semantics.MATCH_SECTION,
            inference_mode=semantics.MODE_DIRECT,
        ),
        "equity": ExtractionMetadata(
            value=20.0,
            confidence=0.72,
            source=semantics.SOURCE_TEXT,
            evidence_version=semantics.V2,
            match_semantics=semantics.MATCH_CODE,
            inference_mode=semantics.MODE_DIRECT,
        ),
        "short_term_liabilities": ExtractionMetadata(
            value=70.0,
            confidence=0.68,
            source=semantics.SOURCE_TEXT,
            evidence_version=semantics.V2,
            match_semantics=semantics.MATCH_CODE,
            inference_mode=semantics.MODE_DIRECT,
        ),
        "cash_and_equivalents": ExtractionMetadata(
            value=120.0,
            confidence=0.58,
            source=semantics.SOURCE_TEXT,
            evidence_version=semantics.V2,
            match_semantics=semantics.MATCH_KEYWORD,
            inference_mode=semantics.MODE_DIRECT,
        ),
        "inventory": ExtractionMetadata(
            value=None,
            confidence=0.0,
            source=semantics.SOURCE_DERIVED,
            evidence_version=semantics.V2,
            match_semantics=semantics.MATCH_NA,
            inference_mode=semantics.MODE_DERIVED,
        ),
        "accounts_receivable": ExtractionMetadata(
            value=None,
            confidence=0.0,
            source=semantics.SOURCE_DERIVED,
            evidence_version=semantics.V2,
            match_semantics=semantics.MATCH_NA,
            inference_mode=semantics.MODE_DERIVED,
        ),
    }
    events: list[semantics.GuardrailEvent] = []

    guardrails.apply_result_guardrails(
        context,
        result,
        guardrail_events=events,
    )

    assert result["cash_and_equivalents"].reason_code == (
        semantics.REASON_GUARDRAIL_COMPONENT_GT_CURRENT_ASSETS
    )
    assert events[-1].metric_key == "cash_and_equivalents"
    assert events[-1].action == semantics.EVENT_INVALIDATED
    assert events[-1].reason_code == (
        semantics.REASON_GUARDRAIL_COMPONENT_GT_CURRENT_ASSETS
    )


@pytest.mark.parametrize(
    ("reason_code", "expected_action"),
    [
        (
            semantics.REASON_SANITY_PNL_CONFLICT_DROP_REVENUE,
            semantics.EVENT_DROPPED,
        ),
        (
            semantics.REASON_GUARDRAIL_CURRENT_ASSETS_CANDIDATE_LT_COMPONENT_REPLACED,
            semantics.EVENT_REPLACED,
        ),
        (
            semantics.REASON_GUARDRAIL_COMPONENT_GT_CURRENT_ASSETS,
            semantics.EVENT_INVALIDATED,
        ),
    ],
)
def test_reason_registry_covers_known_guardrail_branches(
    reason_code: str,
    expected_action: str,
) -> None:
    definition = semantics.get_reason_definition(reason_code)

    assert definition.event_action == expected_action


def test_reason_registry_is_exhaustive_for_declared_extractor_reason_constants() -> (
    None
):
    declared_reasons = {
        value
        for name, value in vars(semantics).items()
        if name.startswith("REASON_") and isinstance(value, str)
    }

    assert declared_reasons <= set(semantics.REASON_REGISTRY)
