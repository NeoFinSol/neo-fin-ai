from __future__ import annotations

from . import legacy_helpers
from .guardrails import _apply_form_like_pnl_sanity, _metric_candidate_quality
from .ranking import _raw_set, _source_priority
from .rules import _METRIC_KEYWORDS, _NUMBER_REGEX_FRAGMENT, _TEXT_LINE_CODE_MAP
from .types import ExtractorContext, RawCandidates


def extract_metrics_regex(text: str) -> dict[str, float | None]:
    return legacy_helpers.extract_metrics_regex(text)


def _collect_text_code_candidates(
    context: ExtractorContext,
    raw: RawCandidates,
) -> None:
    for metric_key, (codes, anchor_keywords) in _TEXT_LINE_CODE_MAP.items():
        existing = raw.get(metric_key)
        if (
            existing is not None
            and _source_priority(
                existing.match_type,
                existing.is_exact,
            )
            >= 2
        ):
            continue

        value = legacy_helpers._extract_value_near_text_codes(
            context.text,
            codes,
            anchor_keywords,
        )
        if legacy_helpers._is_valid_financial_value(value):
            _raw_set(
                raw,
                metric_key,
                value,
                "text_regex",
                False,
                candidate_quality=115,
            )


def _collect_form_pnl_code_candidates(
    context: ExtractorContext,
    raw: RawCandidates,
) -> None:
    if not context.signals.is_form_like or context.tables:
        return

    form_pnl_spec = {
        "revenue": (
            ("2110",),
            ("выручка от реализации, без ндс", "выручка", "revenue"),
        ),
        "net_profit": (
            ("2400",),
            ("чистая прибыль", "net profit", "net income", "profit for the period"),
        ),
    }
    for metric_key, (codes, anchors) in form_pnl_spec.items():
        code_value = legacy_helpers._extract_value_near_text_codes(
            context.text,
            codes,
            anchors,
            lookahead_chars=1400,
        )
        if not legacy_helpers._is_valid_financial_value(code_value):
            continue
        context.form_pnl_code_candidates[metric_key] = code_value
        candidate_quality = 110 if metric_key == "revenue" else 120
        _raw_set(
            raw,
            metric_key,
            code_value,
            "text_regex",
            True,
            candidate_quality=candidate_quality,
        )


def _collect_keyword_proximity_candidates(
    context: ExtractorContext,
    raw: RawCandidates,
) -> None:
    ocr_allowlist = {
        "revenue",
        "net_profit",
        "total_assets",
        "current_assets",
        "accounts_receivable",
        "inventory",
    }

    for metric_key, keywords in _METRIC_KEYWORDS.items():
        existing = raw.get(metric_key)
        if (
            existing is not None
            and _source_priority(
                existing.match_type,
                existing.is_exact,
            )
            >= 2
        ):
            continue
        if (
            context.signals.is_form_like
            and not context.tables
            and metric_key not in ocr_allowlist
        ):
            continue

        value: float | None = None
        candidate_quality: int | None = None
        if context.signals.is_form_like:
            value, candidate_quality = legacy_helpers._extract_best_multiline_value(
                context.text,
                keywords,
                lookahead_lines=24 if metric_key == "net_profit" else 8,
                ocr_mode=True,
                metric_key=metric_key,
            )
        if not legacy_helpers._is_valid_financial_value(value):
            value, candidate_quality = legacy_helpers._extract_best_line_value(
                context.text,
                keywords,
                metric_key=metric_key,
            )
        if legacy_helpers._is_valid_financial_value(value):
            _raw_set(
                raw,
                metric_key,
                value,
                "text_regex",
                False,
                candidate_quality=(
                    candidate_quality if candidate_quality is not None else 50
                ),
            )


def _collect_broad_regex_candidates(
    context: ExtractorContext,
    raw: RawCandidates,
) -> None:
    num_pattern = rf"({_NUMBER_REGEX_FRAGMENT})"
    ocr_allowlist = {
        "revenue",
        "net_profit",
        "total_assets",
        "current_assets",
        "accounts_receivable",
        "inventory",
    }
    broad_patterns: dict[str, list[str]] = {
        "revenue": [
            r"total revenues\s*\|\s*" + num_pattern,
            r"revenues\s*\|\s*" + num_pattern,
            r"выручка от реализации\s*\|\s*" + num_pattern,
            r"выручка[^\d]{0,80}" + num_pattern,
            r"total revenues[^\d]{0,80}" + num_pattern,
            r"revenues[^\d]{0,80}" + num_pattern,
            r"turnover[^\d]{0,60}" + num_pattern,
            r"net sales[^\d]{0,60}" + num_pattern,
            r"consolidated revenue[^\d]{0,60}" + num_pattern,
        ],
        "net_profit": [
            r"чистая прибыль\s*\|\s*" + num_pattern,
            r"чистая прибыль[^\d]{0,60}" + num_pattern,
            r"прибыль после налогообложения[^\d]{0,80}" + num_pattern,
            r"net income\s*\|\s*" + num_pattern,
            r"net income[^\d]{0,80}" + num_pattern,
            r"net loss\s*\|\s*" + num_pattern,
            r"net loss[^\d]{0,80}" + num_pattern,
            r"profit for the year[^\d]{0,80}" + num_pattern,
            r"profit for the period[^\d]{0,80}" + num_pattern,
            r"profit attributable to[^\d]{0,80}" + num_pattern,
            r"net profit attributable[^\d]{0,80}" + num_pattern,
        ],
        "total_assets": [
            r"total assets\s*\|\s*" + num_pattern,
            r"итого активов\s*\|\s*" + num_pattern,
            r"итого активов[^\d]{0,60}" + num_pattern,
            r"баланс\s*\|\s*" + num_pattern,
            r"total assets[^\d]{0,80}" + num_pattern,
            r"non-current and current assets[^\d]{0,80}" + num_pattern,
            r"consolidated assets[^\d]{0,60}" + num_pattern,
        ],
        "equity": [
            r"итого капитала\s*\|\s*" + num_pattern,
            r"итого капитала[^\d]{0,60}" + num_pattern,
            r"собственный капитал\s*\|\s*" + num_pattern,
            r"капитал и резервы\s*\|\s*" + num_pattern,
            r"total stockholders[''] equity\s*\|\s*" + num_pattern,
            r"total stockholders[''] equity[^\d]{0,80}" + num_pattern,
            r"stockholders[''] equity[^\d]{0,80}" + num_pattern,
            r"total shareholders[''] equity[^\d]{0,80}" + num_pattern,
            r"total equity\s*\|\s*" + num_pattern,
            r"total equity[^\d]{0,80}" + num_pattern,
            r"equity attributable to[^\d]{0,80}" + num_pattern,
            r"shareholders' equity[^\d]{0,80}" + num_pattern,
        ],
        "current_assets": [
            r"total current assets\s*\|\s*" + num_pattern,
            r"total current assets[^\d]{0,80}" + num_pattern,
            r"итого оборотных активов\s*\|\s*" + num_pattern,
            r"итого оборотных активов[^\d]{0,60}" + num_pattern,
            r"итого оборотные активы[^\d]{0,60}" + num_pattern,
        ],
        "short_term_liabilities": [
            r"total current liabilities\s*\|\s*" + num_pattern,
            r"total current liabilities[^\d]{0,80}" + num_pattern,
            r"итого краткосрочных обязательств\s*\|\s*" + num_pattern,
            r"итого краткосрочных обязательств[^\d]{0,80}" + num_pattern,
            r"итого краткосрочные обязательства[^\d]{0,80}" + num_pattern,
        ],
        "cost_of_goods_sold": [
            r"себестоимость продаж\s*\|\s*" + num_pattern,
            r"себестоимость продаж[^\d]{0,80}" + num_pattern,
        ],
    }

    for metric_key, pattern_list in broad_patterns.items():
        existing = raw.get(metric_key)
        if (
            existing is not None
            and _source_priority(
                existing.match_type,
                existing.is_exact,
            )
            >= 2
        ):
            continue
        if (
            context.signals.is_form_like
            and not context.tables
            and metric_key not in ocr_allowlist
        ):
            continue
        for pattern in pattern_list:
            match = legacy_helpers.re.search(pattern, context.signals.text_lower)
            if not match:
                continue
            raw_match = match.group(1)
            digits_only = "".join(ch for ch in raw_match if ch.isdigit())
            if digits_only.startswith("07") and len(digits_only) >= 6:
                continue
            value = legacy_helpers._normalize_number(raw_match)
            if value is None:
                continue
            pattern_quality = _metric_candidate_quality(metric_key, pattern)
            if pattern_quality is None:
                continue
            _raw_set(
                raw,
                metric_key,
                value,
                "text_regex",
                False,
                candidate_quality=pattern_quality,
            )
            break


def _collect_form_balance_candidates(
    context: ExtractorContext,
    raw: RawCandidates,
) -> None:
    if context.signals.is_balance_like and "short_term_liabilities" not in raw:
        short_term_value = legacy_helpers._extract_form_section_total(
            context.text,
            (
                "итого по разделу v",
                "итого по разделу у",
                "итого краткосрочных обязательств",
                "итого краткосрочные обязательства",
            ),
            lookback_lines=8,
            lookahead_lines=1,
        )
        if legacy_helpers._is_valid_financial_value(short_term_value):
            _raw_set(
                raw,
                "short_term_liabilities",
                short_term_value,
                "text_regex",
                True,
                candidate_quality=110,
            )

    if context.signals.is_balance_like and "long_term_liabilities" not in raw:
        short_term_value = raw.get_value("short_term_liabilities")
        long_term_value = legacy_helpers._extract_form_long_term_liabilities(
            context.text,
            short_term_value=short_term_value,
        )
        if legacy_helpers._is_valid_financial_value(long_term_value):
            _raw_set(
                raw,
                "long_term_liabilities",
                long_term_value,
                "text_regex",
                True,
                candidate_quality=105,
            )

    if context.signals.is_balance_like and not context.tables and "equity" not in raw:
        equity_value = legacy_helpers._extract_form_section_total(
            context.text,
            ("итого по разделу ш", "итого по разделу iii"),
            lookback_lines=8,
            lookahead_lines=1,
        )
        if legacy_helpers._is_valid_financial_value(equity_value):
            _raw_set(
                raw,
                "equity",
                equity_value,
                "text_regex",
                True,
                candidate_quality=105,
            )


def _collect_form_like_pnl_candidates(
    context: ExtractorContext,
    raw: RawCandidates,
) -> None:
    if not context.signals.is_form_like or context.tables:
        return

    section_candidates = legacy_helpers._extract_form_like_pnl_section_candidates(
        context.text
    )
    for metric_key, (value, quality, is_exact) in section_candidates.items():
        if not legacy_helpers._is_valid_financial_value(value):
            continue
        _raw_set(
            raw,
            metric_key,
            value,
            "text_regex",
            is_exact,
            candidate_quality=quality,
        )

    _apply_form_like_pnl_sanity(
        raw,
        context.form_pnl_code_candidates,
        is_standalone_form=(
            "консолид" not in context.signals.text_lower
            and "consolidated" not in context.signals.text_lower
        ),
    )


def collect_text_candidates(
    context: ExtractorContext,
    raw: RawCandidates,
) -> None:
    _collect_text_code_candidates(context, raw)
    _collect_form_pnl_code_candidates(context, raw)
    _collect_keyword_proximity_candidates(context, raw)
    _collect_broad_regex_candidates(context, raw)
    _collect_form_balance_candidates(context, raw)
    _collect_form_like_pnl_candidates(context, raw)


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
