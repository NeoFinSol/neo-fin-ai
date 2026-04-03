from __future__ import annotations

import inspect

from src.analysis import pdf_extractor
from src.analysis.extractor import (
    guardrails,
    legacy_helpers,
    ocr,
    pipeline,
    ranking,
    rules,
    text_extraction,
    types,
)


def _module_filename(obj: object) -> str:
    source_path = inspect.getsourcefile(obj)
    assert source_path is not None
    return source_path.replace("\\", "/")


def test_pdf_extractor_facade_reexports_stable_public_contract() -> None:
    assert pdf_extractor.ExtractionMetadata is types.ExtractionMetadata
    assert pdf_extractor.ExtractionSource == types.ExtractionSource
    assert pdf_extractor.determine_source is ranking.determine_source
    assert pdf_extractor.apply_confidence_filter is ranking.apply_confidence_filter
    assert pdf_extractor._METRIC_KEYWORDS is rules._METRIC_KEYWORDS
    assert pdf_extractor.extract_metrics_regex is text_extraction.extract_metrics_regex
    assert (
        pdf_extractor.parse_financial_statements_with_metadata
        is pipeline.parse_financial_statements_with_metadata
    )
    assert (
        pdf_extractor.parse_financial_statements is pipeline.parse_financial_statements
    )


def test_pdf_extractor_public_entrypoints_live_in_internal_extractor_modules() -> None:
    assert _module_filename(pdf_extractor.determine_source).endswith(
        "/src/analysis/extractor/ranking.py"
    )
    assert _module_filename(pdf_extractor.is_scanned_pdf).endswith(
        "/src/analysis/extractor/ocr.py"
    )
    assert _module_filename(pdf_extractor.extract_text_from_scanned).endswith(
        "/src/analysis/extractor/ocr.py"
    )
    assert _module_filename(pdf_extractor.extract_tables).endswith(
        "/src/analysis/extractor/tables.py"
    )
    assert _module_filename(pdf_extractor.extract_metrics_regex).endswith(
        "/src/analysis/extractor/text_extraction.py"
    )
    assert _module_filename(
        pdf_extractor.parse_financial_statements_with_metadata
    ).endswith("/src/analysis/extractor/pipeline.py")


def test_pipeline_exposes_explicit_stage_types_for_internal_orchestration() -> None:
    assert hasattr(types, "ExtractorContext")
    assert hasattr(types, "DocumentSignals")
    assert hasattr(types, "RawMetricCandidate")
    assert hasattr(types, "RawCandidates")


def test_raw_candidates_use_named_candidate_records_with_existing_precedence() -> None:
    raw = types.RawCandidates()

    ranking._raw_set(
        raw,
        "revenue",
        10.0,
        "text_regex",
        False,
        candidate_quality=60,
    )
    ranking._raw_set(
        raw,
        "revenue",
        20.0,
        "table",
        True,
        candidate_quality=40,
    )

    candidate = raw["revenue"]
    assert isinstance(candidate, types.RawMetricCandidate)
    assert candidate.value == 20.0
    assert candidate.match_type == "table"
    assert candidate.is_exact is True
    assert candidate.candidate_quality == 40


def test_pipeline_parse_with_metadata_runs_explicit_stage_sequence(monkeypatch) -> None:
    call_order: list[str] = []

    context = types.ExtractorContext(
        tables=[],
        text="Revenue 1000",
        signals=types.DocumentSignals(
            text="Revenue 1000",
            text_lower="revenue 1000",
            has_russian_balance_header=False,
            has_russian_results_header=False,
            is_form_like=False,
            is_balance_like=False,
            scale_factor=1.0,
        ),
    )

    def fake_build_context(tables: list, text: str) -> types.ExtractorContext:
        call_order.append("context")
        assert tables == []
        assert text == "Revenue 1000"
        return context

    def fake_collect_table_candidates(
        extractor_context: types.ExtractorContext,
        raw: types.RawCandidates,
    ) -> None:
        call_order.append("tables")
        assert extractor_context is context
        ranking._raw_set(raw, "revenue", 1000.0, "table", True, candidate_quality=120)

    def fake_collect_text_candidates(
        extractor_context: types.ExtractorContext,
        raw: types.RawCandidates,
    ) -> None:
        call_order.append("text")
        assert extractor_context is context

    def fake_derive_missing_metrics(
        extractor_context: types.ExtractorContext,
        raw: types.RawCandidates,
    ) -> None:
        call_order.append("derive")
        assert extractor_context is context

    def fake_build_metadata_result(
        extractor_context: types.ExtractorContext,
        raw: types.RawCandidates,
    ) -> dict[str, types.ExtractionMetadata]:
        call_order.append("build")
        assert extractor_context is context
        assert raw["revenue"].value == 1000.0
        result = {
            key: types.ExtractionMetadata(
                value=None,
                confidence=0.0,
                source="derived",
            )
            for key in rules._METRIC_KEYWORDS
        }
        result["revenue"] = types.ExtractionMetadata(
            value=1000.0,
            confidence=0.9,
            source="table_exact",
        )
        return result

    monkeypatch.setattr(pipeline, "_build_context", fake_build_context)
    monkeypatch.setattr(
        pipeline,
        "_collect_table_candidates",
        fake_collect_table_candidates,
    )
    monkeypatch.setattr(
        pipeline,
        "_collect_text_candidates",
        fake_collect_text_candidates,
    )
    monkeypatch.setattr(
        pipeline,
        "_derive_missing_metrics",
        fake_derive_missing_metrics,
    )
    monkeypatch.setattr(
        pipeline,
        "_build_metadata_result",
        fake_build_metadata_result,
    )

    metadata = pipeline.parse_financial_statements_with_metadata([], "Revenue 1000")

    assert call_order == ["context", "tables", "text", "derive", "build"]
    assert metadata["revenue"].value == 1000.0
    assert metadata["revenue"].source == "table_exact"


def test_form_like_pnl_sanity_keeps_legacy_conflict_resolution() -> None:
    raw = types.RawCandidates()
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

    guardrails._apply_form_like_pnl_sanity(
        raw,
        {"revenue": 100.0},
        is_standalone_form=False,
    )

    assert "revenue" not in raw
    assert raw["net_profit"].value == 90.0


def test_legacy_helpers_parse_entrypoint_delegates_to_pipeline(monkeypatch) -> None:
    sentinel = {
        "revenue": types.ExtractionMetadata(
            value=123.0,
            confidence=0.9,
            source="table_exact",
        )
    }

    def fake_parse_with_metadata(
        tables: list, text: str
    ) -> dict[str, types.ExtractionMetadata]:
        assert tables == []
        assert text == "Revenue 123"
        return sentinel

    monkeypatch.setattr(
        pipeline,
        "parse_financial_statements_with_metadata",
        fake_parse_with_metadata,
    )

    result = legacy_helpers.parse_financial_statements_with_metadata([], "Revenue 123")

    assert result is sentinel
