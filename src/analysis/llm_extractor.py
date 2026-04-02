"""
LLM-based financial metrics extractor for NeoFin AI.

Replaces the regex/camelot extraction pipeline with an LLM-based approach.
Falls back to the existing extractor when LLM is unavailable or returns
insufficient data.

Architecture rule: this module must NOT import FastAPI or SQLAlchemy.
"""
import json
import logging
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal

from src.analysis.pdf_extractor import (
    ExtractionMetadata,
    _METRIC_KEYWORDS,
    _is_valid_financial_value,
)
from src.core.prompts import LLM_EXTRACTION_PROMPT, LLM_EXTRACTION_RETRY_PROMPT

if TYPE_CHECKING:
    from src.core.ai_service import AIService

logger = logging.getLogger(__name__)

ParseFailureReason = Literal["invalid_json", "invalid_schema", "empty_metrics"]


@dataclass(frozen=True)
class ParsedLlmExtractionResponse:
    """Detailed parse result for a single LLM response."""

    metrics: dict[str, ExtractionMetadata]
    failure_reason: ParseFailureReason | None


@dataclass(frozen=True)
class LlmExtractionRunResult:
    """Detailed extraction result across all processed chunks."""

    metrics: dict[str, ExtractionMetadata] | None
    failure_reason: ParseFailureReason | Literal["llm_error"] | None


_EXTRACTION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "metrics": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "metric": {
                        "type": "string",
                        "enum": sorted(_METRIC_KEYWORDS.keys()),
                    },
                    "value": {"type": "number"},
                    "confidence_score": {"type": "number"},
                    "source_fragment": {"type": "string"},
                },
                "required": [
                    "metric",
                    "value",
                    "confidence_score",
                    "source_fragment",
                ],
                "additionalProperties": False,
            },
        }
    },
    "required": ["metrics"],
    "additionalProperties": False,
}

_EXTRACTION_MODEL_OPTIONS: dict[str, int] = {
    "temperature": 0,
    "num_predict": 1200,
}

# ---------------------------------------------------------------------------
# Scale suffix map for number normalisation
# ---------------------------------------------------------------------------

_SCALE_SUFFIXES: dict[str, float] = {
    "тыс": 1_000.0,
    "тысяч": 1_000.0,
    "тыс.": 1_000.0,
    "млн": 1_000_000.0,
    "млн.": 1_000_000.0,
    "миллион": 1_000_000.0,
    "миллионов": 1_000_000.0,
    "млрд": 1_000_000_000.0,
    "млрд.": 1_000_000_000.0,
    "миллиард": 1_000_000_000.0,
    "миллиардов": 1_000_000_000.0,
}

# Anomaly thresholds per metric key
_ANOMALY_RULES: dict[str, tuple[float | None, float | None]] = {
    # (min_valid, max_valid) — None means no bound
    "revenue": (0.0, None),
    "net_profit": (None, None),  # can be negative
    "total_assets": (0.0, None),
    "equity": (None, None),
    "liabilities": (0.0, None),
    "current_assets": (0.0, None),
    "short_term_liabilities": (0.0, None),
    "accounts_receivable": (0.0, None),
    "inventory": (0.0, None),
    "cash_and_equivalents": (0.0, None),
    "ebitda": (None, None),
    "ebit": (None, None),
    "interest_expense": (None, None),
    "cost_of_goods_sold": (None, None),
    "average_inventory": (0.0, None),
    # ratio-like metrics (if LLM ever returns them)
    "current_ratio": (0.0, 1_000.0),
    "equity_ratio": (-10.0, 10.0),
    "roa": (-100.0, 100.0),
    "roe": (-1_000.0, 1_000.0),
}


# ---------------------------------------------------------------------------
# 2.1  _normalize_number_str
# ---------------------------------------------------------------------------

def _normalize_number_str(value_str: str) -> float | None:
    """Normalise a string representation of a number to float.

    Handles:
    - Russian thousands separator (space / non-breaking space): "1 234 567"
    - Comma as decimal separator: "1 234,56" → 1234.56
    - European dot-comma format: "1.234.567,89" → 1234567.89
    - Scale suffixes: "1,5 млн" → 1_500_000.0

    Returns None if the string cannot be parsed.
    """
    if not value_str or not isinstance(value_str, str):
        return None

    text = value_str.strip()

    # Detect and strip scale suffix (case-insensitive, suffix after the number)
    scale = 1.0
    text_lower = text.lower()
    for suffix, multiplier in sorted(_SCALE_SUFFIXES.items(), key=lambda x: -len(x[0])):
        if text_lower.endswith(suffix):
            scale = multiplier
            text = text[: len(text) - len(suffix)].strip()
            break
        # suffix may appear after a space: "500 тыс руб" → check word boundary
        pattern = r"\s+" + re.escape(suffix) + r"(\s|$)"
        m = re.search(pattern, text_lower)
        if m:
            scale = multiplier
            text = text[: m.start()].strip()
            break

    # Remove currency symbols and extra whitespace
    text = re.sub(r"[₽$€£¥]", "", text).strip()

    # Detect format: if there are both dots and commas, determine which is decimal
    has_dot = "." in text
    has_comma = "," in text

    if has_dot and has_comma:
        # European format: "1.234.567,89" — last comma is decimal
        if text.rfind(",") > text.rfind("."):
            text = text.replace(".", "").replace(",", ".")
        else:
            # "1,234,567.89" — last dot is decimal
            text = text.replace(",", "")
    elif has_comma and not has_dot:
        # Could be thousands "1,234,567" or decimal "1,5"
        comma_count = text.count(",")
        if comma_count == 1:
            # Single comma — treat as decimal separator
            text = text.replace(",", ".")
        else:
            # Multiple commas — thousands separator
            text = text.replace(",", "")
    elif has_dot and not has_comma:
        dot_count = text.count(".")
        if dot_count > 1:
            # "1.234.567" — thousands separator
            text = text.replace(".", "")
        # single dot → already decimal

    # Remove remaining spaces (thousands separator)
    text = text.replace("\u00a0", "").replace("\u202f", "").replace(" ", "")

    if not text or text in ("-", "+"):
        return None

    try:
        value = float(text)
    except ValueError:
        return None

    return value * scale


# ---------------------------------------------------------------------------
# 2.3  _apply_anomaly_check
# ---------------------------------------------------------------------------

def _apply_anomaly_check(
    key: str,
    value: float,
    confidence: float,
) -> tuple[float, float]:
    """Check value against known reasonable bounds for the metric.

    Returns (value, adjusted_confidence).
    If the value is anomalous, confidence is capped at 0.3 and a WARNING is logged.
    """
    bounds = _ANOMALY_RULES.get(key)
    if bounds is None:
        return value, confidence

    min_val, max_val = bounds
    anomalous = False

    if min_val is not None and value < min_val:
        anomalous = True
    if max_val is not None and value > max_val:
        anomalous = True

    if anomalous:
        adjusted = min(confidence, 0.3)
        logger.warning(
            "Anomalous value for metric %s: %s (confidence reduced from %.2f to %.2f)",
            key, value, confidence, adjusted,
        )
        return value, adjusted

    return value, confidence


# ---------------------------------------------------------------------------
# 2.5  parse_llm_extraction_response
# ---------------------------------------------------------------------------

def _is_metric_object(payload: object) -> bool:
    """Return True when payload looks like a single metric item."""
    if not isinstance(payload, dict):
        return False

    return {
        "metric",
        "value",
        "confidence_score",
        "source_fragment",
    }.issubset(payload.keys())


def _normalize_parsed_payload(
    parsed: object,
) -> tuple[list[dict[str, Any]] | None, ParseFailureReason | None]:
    """Normalize supported payload variants to a metrics list."""
    if isinstance(parsed, dict) and "metrics" in parsed:
        items = parsed["metrics"]
        if not isinstance(items, list):
            return None, "invalid_schema"
        return items, None

    if _is_metric_object(parsed):
        return [parsed], None

    return None, "invalid_schema"


def _salvage_metric_items_from_partial_response(
    response: str,
) -> list[dict[str, Any]]:
    """Recover complete metric objects from a truncated ``{"metrics": [...]}`` payload."""
    marker = '"metrics"'
    marker_index = response.find(marker)
    if marker_index == -1:
        return []

    array_start = response.find("[", marker_index)
    if array_start == -1:
        return []

    items: list[dict[str, Any]] = []
    brace_depth = 0
    object_start: int | None = None
    in_string = False
    escaped = False

    for index in range(array_start + 1, len(response)):
        char = response[index]

        if escaped:
            escaped = False
            continue

        if char == "\\" and in_string:
            escaped = True
            continue

        if char == '"':
            in_string = not in_string
            continue

        if in_string:
            continue

        if char == "{":
            if brace_depth == 0:
                object_start = index
            brace_depth += 1
            continue

        if char == "}":
            if brace_depth == 0:
                continue
            brace_depth -= 1
            if brace_depth == 0 and object_start is not None:
                fragment = response[object_start : index + 1]
                try:
                    parsed = json.loads(fragment)
                except json.JSONDecodeError:
                    object_start = None
                    continue
                if isinstance(parsed, dict):
                    items.append(parsed)
                object_start = None

    return items


def parse_llm_extraction_response_detailed(
    response: str,
) -> ParsedLlmExtractionResponse:
    """Parse a JSON response from the LLM with explicit failure reasons."""
    if not response or not response.strip():
        logger.warning("LLM returned empty response; returning empty extraction result")
        return ParsedLlmExtractionResponse(
            metrics=_build_empty_result(),
            failure_reason="invalid_json",
        )

    cleaned = _strip_markdown(response)

    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        salvaged_items = _salvage_metric_items_from_partial_response(cleaned)
        if salvaged_items:
            logger.warning(
                "LLM JSON truncated; salvaged %d complete metric objects",
                len(salvaged_items),
            )
            parsed = {"metrics": salvaged_items}
        else:
            logger.warning("LLM response is not valid JSON: %s", cleaned[:200])
            return ParsedLlmExtractionResponse(
                metrics=_build_empty_result(),
                failure_reason="invalid_json",
            )

    items, failure_reason = _normalize_parsed_payload(parsed)
    if items is None:
        logger.warning(
            "Unexpected LLM response structure (expected {metrics:[...]}): %s",
            str(parsed)[:200],
        )
        return ParsedLlmExtractionResponse(
            metrics=_build_empty_result(),
            failure_reason=failure_reason,
        )

    result = _build_empty_result()

    for item in items:
        if not isinstance(item, dict):
            continue

        metric_key = item.get("metric")
        if metric_key not in _METRIC_KEYWORDS:
            continue

        raw_value = item.get("value")
        confidence_raw = item.get("confidence_score", 0.5)

        if raw_value is None:
            continue

        if isinstance(raw_value, str):
            value = _normalize_number_str(raw_value)
        elif isinstance(raw_value, (int, float)):
            value = float(raw_value)
        else:
            continue

        if value is None or not _is_valid_financial_value(value):
            continue

        try:
            confidence = float(confidence_raw)
            confidence = max(0.0, min(1.0, confidence))
        except (TypeError, ValueError):
            confidence = 0.5

        value, confidence = _apply_anomaly_check(metric_key, value, confidence)
        result[metric_key] = ExtractionMetadata(
            value=value,
            confidence=confidence,
            source="llm",  # type: ignore[arg-type]
        )

    non_null = sum(1 for meta in result.values() if meta.value is not None)
    if non_null == 0:
        return ParsedLlmExtractionResponse(
            metrics=result,
            failure_reason="empty_metrics",
        )

    return ParsedLlmExtractionResponse(metrics=result, failure_reason=None)


def parse_llm_extraction_response(
    response: str,
) -> dict[str, ExtractionMetadata]:
    """Parse a JSON response from the LLM into metric metadata."""
    return parse_llm_extraction_response_detailed(response).metrics


def _strip_markdown(text: str) -> str:
    """Extract JSON from a markdown code block if present."""
    m = re.search(r"```+(?:json)?\s*(.*?)\s*```+", text, re.DOTALL | re.IGNORECASE)
    if m:
        return m.group(1).strip()
    return text.strip()


def _build_empty_result() -> dict[str, ExtractionMetadata]:
    """Return a dict with all metric keys set to (None, 0.0, 'derived')."""
    return {
        key: ExtractionMetadata(value=None, confidence=0.0, source="derived")  # type: ignore[arg-type]
        for key in _METRIC_KEYWORDS
    }


def _line_dedup_key(line: str) -> str:
    """Create a normalised key for line-level deduplication."""
    return re.sub(r"\s+", " ", line).strip().lower()


def _is_likely_noise_line(line: str) -> bool:
    """Return True for headers/footers that add little value to the LLM prompt."""
    compact = line.strip()
    if not compact:
        return True

    if any(pattern.fullmatch(compact) for pattern in _NOISE_LINE_PATTERNS):
        return True

    punctuation = sum(1 for char in compact if not char.isalnum() and not char.isspace())
    if compact and punctuation / len(compact) > 0.35:
        return True

    return False


def _score_financial_line(line: str) -> int:
    """Score a line by how likely it is to help extraction or narrative analysis."""
    lowered = line.lower()
    keyword_hits = sum(1 for keyword in _FINANCIAL_KEYWORDS if keyword in lowered)
    digit_groups = len(re.findall(r"\d{3,}", line))
    money_units = len(re.findall(r"\b(?:руб|тыс|млн|млрд)\.?\b", lowered))
    structured_bonus = 2 if ":" in line or "|" in line or "\t" in line else 0
    return keyword_hits * 4 + digit_groups * 2 + money_units * 2 + structured_bonus


def _split_oversized_paragraph(
    paragraph: str,
    chunk_size: int,
    overlap: int,
) -> list[str]:
    """Split a paragraph that exceeds chunk_size into overlapping slices."""
    if len(paragraph) <= chunk_size:
        return [paragraph]

    safe_overlap = max(0, min(overlap, max(chunk_size - 1, 0)))
    step = max(chunk_size - safe_overlap, 1)
    chunks: list[str] = []

    for start in range(0, len(paragraph), step):
        part = paragraph[start:start + chunk_size]
        if not part:
            break
        chunks.append(part)
        if start + chunk_size >= len(paragraph):
            break

    return chunks


def _compact_financial_lines(
    lines: list[str],
    max_chars: int | None,
    max_lines: int,
) -> list[str]:
    """Keep the highest-signal lines while preserving document order."""
    candidates: list[tuple[int, int, str]] = []
    seen: set[str] = set()

    for index, line in enumerate(lines):
        stripped = line.strip()
        if len(stripped) < 5 or _is_likely_noise_line(stripped):
            continue

        lowered = stripped.lower()
        has_keyword = any(keyword in lowered for keyword in _FINANCIAL_KEYWORDS)
        has_numbers = bool(re.search(r"\d{3,}", stripped))
        if not (has_keyword or has_numbers):
            continue

        dedup_key = _line_dedup_key(stripped)
        if dedup_key in seen:
            continue

        seen.add(dedup_key)
        candidates.append((_score_financial_line(stripped), index, stripped))

    candidates.sort(key=lambda item: (-item[0], item[1]))
    selected = candidates[:max_lines]
    selected.sort(key=lambda item: item[1])

    compacted: list[str] = []
    current_chars = 0
    for _, _, line in selected:
        line_len = len(line) + 1
        if max_chars is not None and compacted and current_chars + line_len > max_chars:
            break
        compacted.append(line)
        current_chars += line_len

    return compacted


# ---------------------------------------------------------------------------
# 2.7  chunk_text
# ---------------------------------------------------------------------------

def chunk_text(
    text: str,
    chunk_size: int = 12_000,
    overlap: int = 200,
    max_chunks: int = 5,
) -> list[str]:
    """Split text into overlapping chunks on paragraph boundaries.

    Args:
        text: Input text to split.
        chunk_size: Maximum characters per chunk.
        overlap: Characters of overlap between consecutive chunks.
        max_chunks: Maximum number of chunks to return (first chunks prioritised).

    Returns:
        List of text chunks, each ≤ chunk_size characters.
    """
    if not text:
        return []

    if len(text) <= chunk_size:
        return [text]

    paragraphs = text.split("\n\n")
    chunks: list[str] = []
    current_parts: list[str] = []
    current_len = 0

    for para in paragraphs:
        para_parts = _split_oversized_paragraph(
            para,
            chunk_size=chunk_size,
            overlap=overlap,
        )

        if len(para_parts) > 1:
            if current_parts:
                chunks.append("\n\n".join(current_parts))
                if len(chunks) >= max_chunks:
                    break
                current_parts = []
                current_len = 0

            for para_part in para_parts:
                chunks.append(para_part)
                if len(chunks) >= max_chunks:
                    break

            if len(chunks) >= max_chunks:
                break
            continue

        for para_part in para_parts:
            para_len = len(para_part) + 2  # +2 for the "\n\n" separator

            if current_len + para_len > chunk_size and current_parts:
                chunk = "\n\n".join(current_parts)
                chunks.append(chunk)

                if len(chunks) >= max_chunks:
                    break

                # Start next chunk with overlap from end of current chunk
                overlap_text = chunk[-overlap:] if len(chunk) > overlap else chunk
                current_parts = [overlap_text] if overlap_text else []
                current_len = len(overlap_text)

            current_parts.append(para_part)
            current_len += para_len

        if len(chunks) >= max_chunks:
            break

    # Add remaining content as final chunk (if budget allows)
    if current_parts and len(chunks) < max_chunks:
        chunks.append("\n\n".join(current_parts))

    return chunks[:max_chunks]


# ---------------------------------------------------------------------------
# 2.9  merge_extraction_results
# ---------------------------------------------------------------------------

def merge_extraction_results(
    results: list[dict[str, ExtractionMetadata]],
) -> dict[str, ExtractionMetadata]:
    """Merge extraction results from multiple chunks.

    For each metric key, selects the ExtractionMetadata with the highest
    confidence across all chunks (max confidence wins).
    Missing keys default to ExtractionMetadata(None, 0.0, "derived").
    """
    merged = _build_empty_result()

    for chunk_result in results:
        for key, meta in chunk_result.items():
            if key not in _METRIC_KEYWORDS:
                continue
            if meta.value is None:
                continue
            if merged[key].value is None or meta.confidence > merged[key].confidence:
                merged[key] = meta

    return merged


def build_extraction_invoke_input(
    chunk: str,
    *,
    retry_invalid_schema: bool = False,
) -> dict[str, Any]:
    """Build a structured-output request for extraction chunks."""
    system_prompt = (
        LLM_EXTRACTION_RETRY_PROMPT if retry_invalid_schema else LLM_EXTRACTION_PROMPT
    )
    return {
        "tool_input": chunk,
        "system": system_prompt,
        "format": _EXTRACTION_SCHEMA,
        "think": False,
        "options": dict(_EXTRACTION_MODEL_OPTIONS),
    }


# ---------------------------------------------------------------------------
# 2.11  extract_with_llm
# ---------------------------------------------------------------------------

async def extract_with_llm(
    text: str,
    ai_service: "AIService",
    chunk_size: int = 12_000,
    max_chunks: int = 5,
    token_budget: int = 50_000,
    ai_provider: str | None = None,
) -> LlmExtractionRunResult:
    """Extract financial metrics from PDF text using the LLM.

    Args:
        text: Full PDF text content.
        ai_service: Configured AIService instance.
        chunk_size: Max characters per LLM request.
        max_chunks: Max number of chunks to process.
        token_budget: Max total characters to process (checked before chunking).

    Returns:
        Detailed extraction result with parsed metrics or a failure reason.
    """
    effective_budget = max(chunk_size, token_budget)
    filtered_text = clean_for_llm_extraction(
        text,
        max_chars=effective_budget,
        max_lines=max_chunks * 60,
    )
    if not filtered_text.strip():
        logger.warning(
            "clean_for_llm_extraction returned empty text — no financial content found"
        )
        return LlmExtractionRunResult(metrics=None, failure_reason="empty_metrics")
    text = filtered_text

    if len(text) > token_budget:
        logger.info(
            "LLM extraction input compacted to budget boundary: %d -> %d chars",
            len(text), token_budget,
        )
        text = text[:token_budget]

    chunks = chunk_text(text, chunk_size=chunk_size, max_chunks=max_chunks)
    if not chunks:
        return LlmExtractionRunResult(metrics=None, failure_reason="empty_metrics")

    chunk_results: list[dict[str, ExtractionMetadata]] = []
    chars_processed = 0
    failure_reason: ParseFailureReason | Literal["llm_error"] | None = None

    for chunk_idx, chunk in enumerate(chunks):
        try:
            invoke_kwargs: dict[str, Any] = {
                "input": build_extraction_invoke_input(chunk),
                "timeout": 120,
            }
            if ai_provider is not None:
                invoke_kwargs["provider"] = ai_provider
            response = await ai_service.invoke(
                **invoke_kwargs,
            )
        except Exception as exc:
            logger.warning(
                "LLM invoke error for chunk %d: %s", chunk_idx, repr(exc)
            )
            failure_reason = failure_reason or "llm_error"
            continue

        if response is None:
            logger.warning("LLM returned None for chunk %d", chunk_idx)
            failure_reason = failure_reason or "llm_error"
            continue

        parsed = parse_llm_extraction_response_detailed(response)
        if parsed.failure_reason == "invalid_schema":
            logger.warning("LLM returned invalid schema for chunk %d", chunk_idx)
            try:
                retry_kwargs: dict[str, Any] = {
                    "input": build_extraction_invoke_input(
                        chunk,
                        retry_invalid_schema=True,
                    ),
                    "timeout": 120,
                }
                if ai_provider is not None:
                    retry_kwargs["provider"] = ai_provider
                retry_response = await ai_service.invoke(
                    **retry_kwargs,
                )
            except Exception as exc:
                logger.warning(
                    "LLM retry invoke error for chunk %d: %s",
                    chunk_idx,
                    repr(exc),
                )
                retry_response = None
            if retry_response is not None:
                parsed = parse_llm_extraction_response_detailed(retry_response)

        if parsed.failure_reason is not None:
            if parsed.failure_reason == "empty_metrics":
                logger.warning("LLM returned empty metrics for chunk %d", chunk_idx)
            failure_reason = failure_reason or parsed.failure_reason
        else:
            chunk_results.append(parsed.metrics)

        chars_processed += len(chunk)

    if not chunk_results:
        return LlmExtractionRunResult(
            metrics=None,
            failure_reason=failure_reason or "empty_metrics",
        )

    merged = merge_extraction_results(chunk_results)

    # Structured logging
    non_null_count = sum(1 for m in merged.values() if m.value is not None)
    confidences = [m.confidence for m in merged.values() if m.value is not None]
    confidence_avg = sum(confidences) / len(confidences) if confidences else 0.0

    logger.info(
        "LLM extraction completed: method=%s metrics=%d confidence_avg=%.2f chunks=%d chars=%d",
        "llm",
        non_null_count,
        confidence_avg,
        len(chunk_results),
        chars_processed,
    )

    if non_null_count == 0:
        return LlmExtractionRunResult(metrics=None, failure_reason="empty_metrics")

    return LlmExtractionRunResult(metrics=merged, failure_reason=None)

# ---------------------------------------------------------------------------
# Text preprocessing — filter OCR garbage before sending to LLM
# ---------------------------------------------------------------------------

_FINANCIAL_KEYWORDS = [
    "выручка", "прибыль", "актив", "капитал", "руб", "тыс", "млн", "млрд",
    "баланс", "обязательств", "ликвидност", "дебитор", "кредитор", "запас",
    "revenue", "profit", "asset", "equity", "liabilit", "cash",
    "риск", "убыт", "задолж", "снижен", "рост", "падени", "debt", "loss",
    "risk", "decline", "growth",
]

_EXTRACTION_LINE_KEYWORDS = tuple(
    dict.fromkeys(
        keyword.lower()
        for keywords in _METRIC_KEYWORDS.values()
        for keyword in keywords
    )
)

_EXTRACTION_TOTAL_TOKENS = (
    "итого",
    "итого по разделу",
    "total",
    "subtotal",
    "balance",
    "assets",
    "liabilities",
    "equity",
)

_EXTRACTION_UNIT_TOKENS = (
    "тыс",
    "тыс.",
    "млн",
    "млн.",
    "млрд",
    "млрд.",
    "руб",
    "руб.",
    "thousand",
    "million",
    "billion",
)

_NOISE_LINE_PATTERNS = (
    re.compile(r"^\d{4}$"),
    re.compile(r"^страница\s+\d+(\s+из\s+\d+)?$", re.IGNORECASE),
    re.compile(r"^page\s+\d+(\s+of\s+\d+)?$", re.IGNORECASE),
    re.compile(r"^\d+\s*/\s*\d+$"),
)


def is_clean_financial_text(text: str) -> bool:
    """Return True if text looks like readable financial content."""
    if not text or len(text) < 100:
        return False
    text_lower = text.lower()
    if not any(kw in text_lower for kw in _FINANCIAL_KEYWORDS):
        return False
    garbage = sum(1 for c in text if ord(c) < 32 and c not in "\n\t\r")
    if len(text) > 0 and garbage / len(text) > 0.05:
        return False
    return True


def clean_for_llm(
    raw_text: str,
    max_chars: int | None = None,
    max_lines: int = 120,
) -> str:
    """Filter OCR text to keep only financially relevant lines.

    Reduces token consumption by 80-90% by discarding lines with no
    financial keywords. Also strips control characters.
    """
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", raw_text)
    lines = text.split("\n")
    compacted = _compact_financial_lines(
        lines,
        max_chars=max_chars,
        max_lines=max_lines,
    )
    result = "\n".join(compacted)
    logger.info(
        "clean_for_llm: %d chars -> %d chars (%.0f%% reduction)",
        len(raw_text), len(result),
        (1 - len(result) / max(len(raw_text), 1)) * 100,
    )
    return result


def _is_extraction_neighbor_candidate(line: str) -> bool:
    """Return True for numeric or unit-bearing lines near extraction anchors."""
    lowered = line.lower()
    return bool(re.search(r"\d{3,}", line)) or any(
        token in lowered for token in _EXTRACTION_UNIT_TOKENS
    )


def _score_extraction_line(line: str) -> int:
    """Score a line by extraction relevance rather than narrative usefulness."""
    lowered = line.lower()
    metric_hits = sum(
        1 for keyword in _EXTRACTION_LINE_KEYWORDS if keyword in lowered
    )
    total_hits = sum(1 for token in _EXTRACTION_TOTAL_TOKENS if token in lowered)
    unit_hits = sum(1 for token in _EXTRACTION_UNIT_TOKENS if token in lowered)
    digit_groups = len(re.findall(r"\d{3,}", line))
    dense_numbers = 3 if digit_groups >= 2 else 0
    return metric_hits * 6 + total_hits * 3 + unit_hits * 2 + digit_groups * 2 + dense_numbers


def clean_for_llm_extraction(
    raw_text: str,
    max_chars: int | None = None,
    max_lines: int = 200,
) -> str:
    """Compact text specifically for metric extraction, not narrative analysis."""
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", raw_text)
    raw_lines = text.split("\n")
    candidates: list[tuple[int, int, str]] = []
    seen: set[str] = set()

    for index, line in enumerate(raw_lines):
        stripped = line.strip()
        if len(stripped) < 3 or _is_likely_noise_line(stripped):
            continue

        lowered = stripped.lower()
        metric_hit = any(keyword in lowered for keyword in _EXTRACTION_LINE_KEYWORDS)
        total_hit = any(token in lowered for token in _EXTRACTION_TOTAL_TOKENS)
        unit_hit = any(token in lowered for token in _EXTRACTION_UNIT_TOKENS)
        digit_groups = len(re.findall(r"\d{3,}", stripped))
        word_count = len(re.findall(r"\S+", stripped))
        dense_numeric = digit_groups >= 2
        narrative_noise = word_count > 20 and digit_groups == 0 and not metric_hit

        if narrative_noise:
            continue

        if not (metric_hit or total_hit or (unit_hit and digit_groups > 0) or dense_numeric):
            continue

        dedup_key = _line_dedup_key(stripped)
        if dedup_key in seen:
            continue

        seen.add(dedup_key)
        candidates.append((_score_extraction_line(stripped), index, stripped))

        if metric_hit or total_hit:
            for neighbor in (index - 1, index + 1):
                if neighbor < 0 or neighbor >= len(raw_lines):
                    continue
                neighbor_line = raw_lines[neighbor].strip()
                if not neighbor_line or _is_likely_noise_line(neighbor_line):
                    continue
                if not _is_extraction_neighbor_candidate(neighbor_line):
                    continue
                neighbor_key = _line_dedup_key(neighbor_line)
                if neighbor_key in seen:
                    continue
                seen.add(neighbor_key)
                candidates.append(
                    (_score_extraction_line(neighbor_line), neighbor, neighbor_line)
                )

    candidates.sort(key=lambda item: (-item[0], item[1]))
    selected = candidates[:max_lines]
    selected.sort(key=lambda item: item[1])

    compacted: list[str] = []
    current_chars = 0
    for _, _, line in selected:
        line_len = len(line) + 1
        if max_chars is not None and compacted and current_chars + line_len > max_chars:
            break
        compacted.append(line)
        current_chars += line_len

    result = "\n".join(compacted)
    logger.info(
        "clean_for_llm_extraction: %d chars -> %d chars (%.0f%% reduction)",
        len(raw_text),
        len(result),
        (1 - len(result) / max(len(raw_text), 1)) * 100,
    )
    return result
