from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Any, Iterator

from . import legacy_helpers
from .guardrails import _metric_candidate_quality
from .ranking import _raw_set
from .rules import (
    _GARBLED_KEYWORDS,
    _IFRS_ENGLISH_KEYWORDS,
    _LINE_CODE_MAP,
    _METRIC_KEYWORDS,
    _MONETARY_METRICS,
)
from .types import ExtractorContext, RawCandidates

logger = logging.getLogger(__name__)


@contextmanager
def _patched_legacy(**overrides: Any) -> Iterator[None]:
    original: dict[str, Any] = {}
    for key, value in overrides.items():
        original[key] = getattr(legacy_helpers, key)
        setattr(legacy_helpers, key, value)
    try:
        yield
    finally:
        for key, value in original.items():
            setattr(legacy_helpers, key, value)


def extract_tables(
    pdf_path: str,
    force_ocr: bool = False,
) -> list[dict[str, Any]]:
    from src.analysis import pdf_extractor as facade

    with _patched_legacy(
        camelot=facade.camelot,
        extract_text_from_scanned=facade.extract_text_from_scanned,
    ):
        return legacy_helpers.extract_tables(pdf_path, force_ocr=force_ocr)


def _skip_small_monetary_value(metric_key: str, value: float) -> bool:
    return metric_key in _MONETARY_METRICS and abs(value) < 1000


def _collect_table_line_code_candidates(
    rows: list[list[Any]], raw: RawCandidates
) -> None:
    for row in rows:
        if len(row) < 3:
            continue
        for cell_index, cell in enumerate(row):
            if cell is None:
                continue
            compact = str(cell).strip().replace("\xa0", "").replace(" ", "")
            if compact.isdigit() and len(compact) == 4 and compact in _LINE_CODE_MAP:
                metric_key = _LINE_CODE_MAP[compact]
                value = legacy_helpers._extract_first_numeric_cell(
                    row[cell_index + 1 :]
                )
                if value is not None and legacy_helpers._is_valid_financial_value(
                    value
                ):
                    _raw_set(
                        raw,
                        metric_key,
                        value,
                        "table",
                        True,
                        candidate_quality=120,
                    )


def _collect_garbled_keyword_candidates(
    rows: list[list[Any]],
    raw: RawCandidates,
) -> None:
    for row in rows:
        if len(row) < 3:
            continue
        label_cell = str(row[0]).lower() if row[0] else ""
        for garbled_keyword, metric_key in _GARBLED_KEYWORDS.items():
            if garbled_keyword.lower() not in label_cell:
                continue
            metric_quality = _metric_candidate_quality(metric_key, label_cell)
            if metric_quality is None:
                break
            value = legacy_helpers._extract_first_numeric_cell(row[1:])
            if value is None or not legacy_helpers._is_valid_financial_value(value):
                break
            if _skip_small_monetary_value(metric_key, value):
                logger.debug(
                    "Skipping small value %s for %s (likely TOC page number)",
                    value,
                    metric_key,
                )
                break
            _raw_set(
                raw,
                metric_key,
                value,
                "table",
                True,
                candidate_quality=metric_quality,
            )
            break


def _collect_ifrs_keyword_candidates(
    rows: list[list[Any]],
    raw: RawCandidates,
) -> None:
    for row in rows:
        # Preserve legacy Pass 0 behavior: IFRS exact-match parsing only ran
        # for table rows with at least 3 cells.
        if len(row) < 3:
            continue
        label_cell = str(row[0]).lower() if row[0] else ""
        for english_keyword, metric_key in _IFRS_ENGLISH_KEYWORDS.items():
            if english_keyword not in label_cell:
                continue
            metric_quality = _metric_candidate_quality(metric_key, label_cell)
            if metric_quality is None:
                break
            value = legacy_helpers._extract_first_numeric_cell(row[1:])
            if value is None or not legacy_helpers._is_valid_financial_value(value):
                break
            if _skip_small_monetary_value(metric_key, value):
                logger.debug(
                    "Skipping small value %s for %s (likely TOC page number)",
                    value,
                    metric_key,
                )
                break
            _raw_set(
                raw,
                metric_key,
                value,
                "table",
                True,
                candidate_quality=metric_quality or 85,
            )
            break


def _collect_ocr_table_candidates(rows: list[list[Any]], raw: RawCandidates) -> None:
    for row in rows:
        if len(row) < 2 or row[0] != "OCR_TEXT":
            continue
        ocr_text = row[1]
        ocr_text_lower = ocr_text.lower()
        for metric_key, keywords in _METRIC_KEYWORDS.items():
            for keyword in keywords:
                keyword_quality = _metric_candidate_quality(metric_key, keyword)
                if keyword_quality is None:
                    continue
                pattern = (
                    rf"{keyword}[^0-9]{{0,50}}"
                    r"(\d{1,3}(?:[ \t\xa0]\d{3})+(?:[.,]\d+)?|\d+(?:[.,]\d+)?)"
                )
                match = legacy_helpers.re.search(
                    pattern, ocr_text_lower, legacy_helpers.re.IGNORECASE
                )
                if match:
                    value = legacy_helpers._normalize_number(match.group(1))
                    if legacy_helpers._is_valid_financial_value(value):
                        _raw_set(
                            raw,
                            metric_key,
                            value,
                            "text_regex",
                            False,
                            candidate_quality=keyword_quality,
                        )
                        break


def _collect_regular_table_candidates(
    rows: list[list[Any]], raw: RawCandidates
) -> None:
    for row in rows:
        row_text = " ".join(str(cell) for cell in row if cell is not None)
        row_text_lower = row_text.lower()
        for metric_key, keywords in _METRIC_KEYWORDS.items():
            if not any(keyword in row_text_lower for keyword in keywords):
                continue

            label_index = 0
            for cell_index, cell in enumerate(row):
                if cell is not None and any(
                    keyword in str(cell).lower() for keyword in keywords
                ):
                    label_index = cell_index
                    break

            value = legacy_helpers._extract_first_numeric_cell(row[label_index + 1 :])
            if value is None:
                value = legacy_helpers._extract_number_from_text(row_text)
            if value is None or not legacy_helpers._is_valid_financial_value(value):
                continue

            label_cell = (
                str(row[label_index]).lower().strip()
                if row[label_index] is not None
                else ""
            )
            metric_quality = _metric_candidate_quality(
                metric_key,
                label_cell or row_text_lower,
            )
            if metric_quality is None:
                continue
            is_exact = any(label_cell == keyword for keyword in keywords)
            _raw_set(
                raw,
                metric_key,
                value,
                "table",
                is_exact,
                candidate_quality=metric_quality,
            )


def _collect_heading_total_candidates(
    context: ExtractorContext,
    raw: RawCandidates,
) -> None:
    if not context.tables:
        return

    inferred_current_assets = legacy_helpers._extract_section_total_from_heading_rows(
        context.tables,
        section_headings=("оборотные активы", "current assets"),
        stop_markers=(
            "итого активы",
            "total assets",
            "капитал и обязательства",
            "equity and liabilities",
        ),
    )
    if legacy_helpers._is_valid_financial_value(inferred_current_assets):
        _raw_set(
            raw,
            "current_assets",
            inferred_current_assets,
            "table",
            True,
            candidate_quality=112,
        )

    inferred_short_term = legacy_helpers._extract_section_total_from_heading_rows(
        context.tables,
        section_headings=("краткосрочные обязательства", "current liabilities"),
        stop_markers=(
            "итого обязательства",
            "total liabilities",
            "итого капитал и обязательства",
            "total equity and liabilities",
        ),
    )
    if legacy_helpers._is_valid_financial_value(inferred_short_term):
        _raw_set(
            raw,
            "short_term_liabilities",
            inferred_short_term,
            "table",
            True,
            candidate_quality=112,
        )


def collect_table_candidates(
    context: ExtractorContext,
    raw: RawCandidates,
) -> None:
    for table in context.tables or []:
        rows = legacy_helpers._table_to_rows(table)
        if table.get("flavor") == "ocr":
            _collect_ocr_table_candidates(rows, raw)
            continue

        _collect_table_line_code_candidates(rows, raw)
        _collect_garbled_keyword_candidates(rows, raw)
        _collect_ifrs_keyword_candidates(rows, raw)
        _collect_regular_table_candidates(rows, raw)

    _collect_heading_total_candidates(context, raw)
