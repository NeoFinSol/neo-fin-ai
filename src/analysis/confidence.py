"""
Confidence scoring for extracted financial metrics.

Each metric gets a confidence score based on extraction source:
- table: 0.9 (most reliable)
- text_regex: 0.7 (good, but may have noise)
- ocr: 0.5 (OCR errors possible)
- derived: 0.3 (calculated/estimated)
"""

from dataclasses import dataclass
from typing import Literal

ExtractionSource = Literal["table", "text_regex", "ocr", "derived"]

CONFIDENCE_MAP: dict[ExtractionSource, float] = {
    "table": 0.9,
    "text_regex": 0.7,
    "ocr": 0.5,
    "derived": 0.3,
}


@dataclass
class Metric:
    """Financial metric with confidence metadata."""

    value: float | None
    source: ExtractionSource
    method: str
    confidence: float


def calculate_confidence(source: ExtractionSource) -> float:
    """Calculate confidence score for extraction source."""
    return CONFIDENCE_MAP.get(source, 0.3)


def build_metric(value: float | None, source: ExtractionSource, method: str) -> Metric:
    """Build a metric with confidence score."""
    return Metric(
        value=value,
        source=source,
        method=method,
        confidence=calculate_confidence(source),
    )


def filter_by_confidence(metrics: dict, threshold: float = 0.5) -> dict:
    """
    Filter metrics by confidence threshold.

    Args:
        metrics: Dict of metric_name → Metric
        threshold: Minimum confidence to keep (0.0–1.0)

    Returns:
        Dict with only metrics >= threshold
    """
    return {
        k: v
        for k, v in metrics.items()
        if v.confidence >= threshold and v.value is not None
    }


def count_reliable(metrics: dict, threshold: float = 0.7) -> int:
    """Count metrics with confidence >= threshold."""
    return sum(1 for m in metrics.values() if m.confidence >= threshold)
