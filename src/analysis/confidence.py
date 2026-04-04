"""
Legacy compatibility helpers for confidence-based metric filtering.

The extractor's semantic source of truth lives in ``src.analysis.extractor.semantics``.
This module remains as a thin compatibility layer for older callers that still expect
``Metric`` helpers and confidence-based filtering utilities.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from src.analysis.extractor import semantics
from src.analysis.extractor.types import ExtractionMetadata

LegacyExtractionSource = Literal[
    "table",
    "text_regex",
    "ocr",
    "derived",
    "text",
    "issuer_fallback",
]


@dataclass(slots=True)
class Metric:
    """Compatibility metric container with confidence metadata."""

    value: float | None
    source: LegacyExtractionSource
    method: str
    confidence: float


def _profile_key_for_source(source: LegacyExtractionSource) -> semantics.ProfileKey:
    if source == "table":
        return (semantics.SOURCE_TABLE, semantics.MATCH_EXACT, semantics.MODE_DIRECT)
    if source == "text_regex":
        return (
            semantics.SOURCE_TEXT,
            semantics.MATCH_KEYWORD,
            semantics.MODE_DIRECT,
        )
    if source == "text":
        return (
            semantics.SOURCE_TEXT,
            semantics.MATCH_KEYWORD,
            semantics.MODE_DIRECT,
        )
    if source == "ocr":
        return (semantics.SOURCE_OCR, semantics.MATCH_EXACT, semantics.MODE_DIRECT)
    if source == "issuer_fallback":
        return (
            semantics.SOURCE_ISSUER_FALLBACK,
            semantics.MATCH_NA,
            semantics.MODE_POLICY_OVERRIDE,
        )
    return (semantics.SOURCE_DERIVED, semantics.MATCH_NA, semantics.MODE_DERIVED)


def calculate_confidence(source: LegacyExtractionSource) -> float:
    """Return the baseline confidence for a legacy compatibility source."""
    return semantics.calculate_confidence(
        _profile_key_for_source(source),
        candidate_quality=None,
        signal_flags=(),
        conflict_count=0,
        postprocess_state=semantics.POSTPROCESS_NONE,
    )


def build_metric(
    value: float | None, source: LegacyExtractionSource, method: str
) -> Metric:
    """Build a compatibility metric using the current semantic confidence model."""
    return Metric(
        value=value,
        source=source,
        method=method,
        confidence=calculate_confidence(source),
    )


def _to_metadata(metric: Metric) -> ExtractionMetadata:
    if metric.source in {"text_regex", "issuer_fallback"}:
        legacy_source = metric.source
    elif metric.source == "table":
        legacy_source = "table_exact"
    elif metric.source == "text":
        legacy_source = "text_regex"
    else:
        legacy_source = metric.source
    return ExtractionMetadata(
        value=metric.value,
        confidence=metric.confidence,
        source=legacy_source,
    )


def filter_by_confidence(
    metrics: dict[str, Metric],
    threshold: float = 0.5,
) -> dict[str, Metric]:
    """Filter compatibility metrics through the shared semantic threshold helper."""
    return {
        key: metric
        for key, metric in metrics.items()
        if semantics.survives_confidence_filter(_to_metadata(metric), threshold)
    }


def count_reliable(metrics: dict[str, Metric], threshold: float = 0.7) -> int:
    """Count compatibility metrics that survive the shared semantic threshold helper."""
    return sum(
        1
        for metric in metrics.values()
        if semantics.survives_confidence_filter(_to_metadata(metric), threshold)
    )


__all__ = [
    "LegacyExtractionSource",
    "Metric",
    "build_metric",
    "calculate_confidence",
    "count_reliable",
    "filter_by_confidence",
]
