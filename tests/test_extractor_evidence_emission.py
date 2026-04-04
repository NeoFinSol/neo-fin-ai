from __future__ import annotations

from src.analysis.extractor.guardrails import apply_result_guardrails
from src.analysis.extractor.tables import collect_table_candidates
from src.analysis.extractor.text_extraction import collect_text_candidates
from src.analysis.extractor.types import (
    DocumentSignals,
    ExtractionMetadata,
    ExtractorContext,
    RawCandidates,
)


def _context(*, tables: list | None = None, text: str = "") -> ExtractorContext:
    normalized_text = text or ""
    text_lower = normalized_text.lower()
    return ExtractorContext(
        tables=tables or [],
        text=normalized_text,
        signals=DocumentSignals(
            text=normalized_text,
            text_lower=text_lower,
            has_russian_balance_header="бухгалтерский баланс" in text_lower,
            has_russian_results_header="отчет о финансовых результатах" in text_lower,
            is_form_like=False,
            is_balance_like=False,
            scale_factor=1.0,
        ),
    )


def _balance_context() -> ExtractorContext:
    context = _context(text="Бухгалтерский баланс")
    context.signals.is_balance_like = True
    return context


def test_table_line_code_candidate_emits_code_match_semantics() -> None:
    raw = RawCandidates()
    context = _context(
        tables=[{"rows": [["2110", "1 000 000", ""]], "flavor": "stream"}]
    )

    collect_table_candidates(context, raw)

    candidate = raw["revenue"]
    assert candidate.source == "table"
    assert candidate.match_semantics == "code_match"
    assert candidate.inference_mode == "direct"
    assert "ev:line_code" in candidate.signal_flags


def test_table_heading_total_candidate_emits_section_match_semantics() -> None:
    raw = RawCandidates()
    context = _context(
        tables=[
            {
                "rows": [
                    ["Оборотные активы", ""],
                    ["Запасы", "2 000"],
                    ["Дебиторская задолженность", "3 000"],
                    ["Итого оборотные активы", "5 000"],
                ],
                "flavor": "stream",
            }
        ]
    )

    collect_table_candidates(context, raw)

    candidate = raw["current_assets"]
    assert candidate.source == "table"
    assert candidate.match_semantics == "section_match"
    assert candidate.inference_mode == "direct"
    assert "ev:section_total" in candidate.signal_flags


def test_text_code_candidate_emits_code_match_semantics() -> None:
    raw = RawCandidates()
    context = _context(text="2110 Выручка 1 000 000")

    collect_text_candidates(context, raw)

    candidate = raw["revenue"]
    assert candidate.source == "text"
    assert candidate.match_semantics == "code_match"
    assert candidate.inference_mode == "direct"
    assert "ev:line_code" in candidate.signal_flags


def test_gross_profit_mapping_is_emitted_as_approximation() -> None:
    raw = RawCandidates()
    context = _context(
        tables=[{"rows": [["Gross profit", "150 000", ""]], "flavor": "stream"}]
    )

    collect_table_candidates(context, raw)

    candidate = raw["ebitda"]
    assert candidate.source == "table"
    assert candidate.inference_mode == "approximation"
    assert candidate.reason_code == "gross_profit_to_ebitda_approximation"


def test_issuer_fallback_emits_policy_override_metadata() -> None:
    from src.analysis.issuer_fallback import apply_issuer_metric_overrides

    metadata = {
        "net_profit": ExtractionMetadata(
            value=1_000.0,
            confidence=0.2,
            source="derived",
        )
    }

    updated = apply_issuer_metric_overrides(
        metadata,
        filename="magnit_h1_2025_report.pdf",
        text="Magnit H1 2025 six months 30 June 2025",
    )

    candidate = updated["net_profit"]
    assert candidate.evidence_version == "v2"
    assert candidate.source == "issuer_fallback"
    assert candidate.match_semantics == "not_applicable"
    assert candidate.inference_mode == "policy_override"
    assert candidate.authoritative_override is True
    assert candidate.reason_code == "issuer_repo_override"


def test_result_guardrail_marks_invalidated_metric_without_changing_provenance() -> (
    None
):
    context = _balance_context()
    result = {
        "total_assets": ExtractionMetadata(
            value=100.0,
            confidence=0.92,
            source="table",
            evidence_version="v2",
            match_semantics="exact",
            inference_mode="direct",
        ),
        "current_assets": ExtractionMetadata(
            value=80.0,
            confidence=0.80,
            source="table",
            evidence_version="v2",
            match_semantics="section_match",
            inference_mode="direct",
        ),
        "liabilities": ExtractionMetadata(
            value=90.0,
            confidence=0.80,
            source="table",
            evidence_version="v2",
            match_semantics="section_match",
            inference_mode="direct",
        ),
        "equity": ExtractionMetadata(
            value=20.0,
            confidence=0.72,
            source="text",
            evidence_version="v2",
            match_semantics="code_match",
            inference_mode="direct",
        ),
        "short_term_liabilities": ExtractionMetadata(
            value=70.0,
            confidence=0.68,
            source="text",
            evidence_version="v2",
            match_semantics="code_match",
            inference_mode="direct",
            signal_flags=["ev:line_code"],
        ),
        "cash_and_equivalents": ExtractionMetadata(
            value=120.0,
            confidence=0.58,
            source="text",
            evidence_version="v2",
            match_semantics="keyword_match",
            inference_mode="direct",
        ),
        "inventory": ExtractionMetadata(
            value=None,
            confidence=0.0,
            source="derived",
            evidence_version="v2",
            match_semantics="not_applicable",
            inference_mode="derived",
        ),
        "accounts_receivable": ExtractionMetadata(
            value=None,
            confidence=0.0,
            source="derived",
            evidence_version="v2",
            match_semantics="not_applicable",
            inference_mode="derived",
        ),
    }

    apply_result_guardrails(context, result)

    invalidated = result["cash_and_equivalents"]
    assert invalidated.value is None
    assert invalidated.source == "text"
    assert invalidated.match_semantics == "keyword_match"
    assert invalidated.inference_mode == "direct"
    assert invalidated.postprocess_state == "guardrail_adjusted"
    assert invalidated.reason_code == "guardrail_component_gt_current_assets"
    assert "pp:guardrail_adjusted" in invalidated.signal_flags
