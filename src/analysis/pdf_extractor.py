from __future__ import annotations

import os

from src.analysis.extractor import guardrails as _guardrails
from src.analysis.extractor import legacy_helpers as _legacy
from src.analysis.extractor.ocr import (
    extract_text,
    extract_text_from_scanned,
    is_scanned_pdf,
)
from src.analysis.extractor.pipeline import (
    parse_financial_statements,
    parse_financial_statements_with_metadata,
)
from src.analysis.extractor.ranking import (
    _raw_set,
    _source_priority,
    apply_confidence_filter,
    determine_source,
)
from src.analysis.extractor.rules import _METRIC_KEYWORDS, _MONETARY_METRICS
from src.analysis.extractor.tables import extract_tables
from src.analysis.extractor.text_extraction import (
    _detect_scale_factor,
    _extract_best_line_value,
    _extract_best_multiline_value,
    _extract_first_numeric_cell,
    _extract_form_like_pnl_section_candidates,
    _extract_form_long_term_liabilities,
    _extract_form_section_total,
    _extract_number_from_text,
    _extract_section_total,
    _extract_section_total_from_heading_rows,
    _extract_value_near_text_codes,
    _is_valid_financial_value,
    _normalize_metric_text,
    _normalize_number,
    _table_to_rows,
    extract_metrics_regex,
)
from src.analysis.extractor.types import ExtractionMetadata, ExtractionSource

camelot = _legacy.camelot
convert_from_path = _legacy.convert_from_path
MAX_OCR_PAGES = _legacy.MAX_OCR_PAGES
PyPDF2 = _legacy.PyPDF2
pytesseract = _legacy.pytesseract
TESSERACT_AVAILABLE = _legacy.TESSERACT_AVAILABLE

_tesseract_cmd = os.getenv("TESSERACT_CMD")
if _tesseract_cmd:
    pytesseract.pytesseract.tesseract_cmd = _tesseract_cmd

_extract_layout_section_total_lines = _legacy._extract_layout_section_total_lines
_extract_ocr_row_value_tail = _legacy._extract_ocr_row_value_tail
_LAYOUT_BALANCE_ROW_SPECS = _legacy._LAYOUT_BALANCE_ROW_SPECS
_LAYOUT_ROW_SIGNAL_TOKENS = _legacy._LAYOUT_ROW_SIGNAL_TOKENS
_should_run_layout_metric_row_crop = _legacy._should_run_layout_metric_row_crop
_should_stop_scanned_ocr = _legacy._should_stop_scanned_ocr
_get_poppler_path = _legacy._get_poppler_path
_LEGACY_EXTRACT_LAYOUT_METRIC_VALUE_LINES = _legacy._extract_layout_metric_value_lines


def _extract_layout_metric_value_lines(image: object, page_text: str) -> list[str]:
    original_tail = _legacy._extract_ocr_row_value_tail
    original_pytesseract = _legacy.pytesseract
    original_specs = _legacy._LAYOUT_BALANCE_ROW_SPECS
    original_tokens = _legacy._LAYOUT_ROW_SIGNAL_TOKENS
    try:
        _legacy._extract_ocr_row_value_tail = _extract_ocr_row_value_tail
        _legacy.pytesseract = pytesseract
        _legacy._LAYOUT_BALANCE_ROW_SPECS = _LAYOUT_BALANCE_ROW_SPECS
        _legacy._LAYOUT_ROW_SIGNAL_TOKENS = _LAYOUT_ROW_SIGNAL_TOKENS
        return _LEGACY_EXTRACT_LAYOUT_METRIC_VALUE_LINES(image, page_text)
    finally:
        _legacy._extract_ocr_row_value_tail = original_tail
        _legacy.pytesseract = original_pytesseract
        _legacy._LAYOUT_BALANCE_ROW_SPECS = original_specs
        _legacy._LAYOUT_ROW_SIGNAL_TOKENS = original_tokens


def __getattr__(name: str):
    if hasattr(_guardrails, name):
        return getattr(_guardrails, name)
    if hasattr(_legacy, name):
        return getattr(_legacy, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(dir(_guardrails)) | set(dir(_legacy)))
