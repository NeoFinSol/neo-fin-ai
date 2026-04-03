from __future__ import annotations

from . import legacy_helpers


def extract_metrics_regex(text: str) -> dict[str, float | None]:
    return legacy_helpers.extract_metrics_regex(text)


_detect_scale_factor = legacy_helpers._detect_scale_factor
_extract_best_line_value = legacy_helpers._extract_best_line_value
_extract_best_multiline_value = legacy_helpers._extract_best_multiline_value
_extract_first_numeric_cell = legacy_helpers._extract_first_numeric_cell
_extract_form_like_pnl_section_candidates = (
    legacy_helpers._extract_form_like_pnl_section_candidates
)
_extract_form_long_term_liabilities = legacy_helpers._extract_form_long_term_liabilities
_extract_form_section_total = legacy_helpers._extract_form_section_total
_extract_number_from_text = legacy_helpers._extract_number_from_text
_extract_section_total = legacy_helpers._extract_section_total
_extract_section_total_from_heading_rows = (
    legacy_helpers._extract_section_total_from_heading_rows
)
_extract_value_near_text_codes = legacy_helpers._extract_value_near_text_codes
_is_valid_financial_value = legacy_helpers._is_valid_financial_value
_normalize_metric_text = legacy_helpers._normalize_metric_text
_normalize_number = legacy_helpers._normalize_number
_table_to_rows = legacy_helpers._table_to_rows
