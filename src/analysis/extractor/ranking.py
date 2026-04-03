from __future__ import annotations

from .types import ExtractionMetadata, ExtractionSource


def determine_source(
    match_type: str,
    is_exact: bool = False,
    is_derived: bool = False,
) -> tuple[ExtractionSource, float]:
    """Return (source, confidence) deterministically based on extraction method."""
    if match_type == "derived_strong":
        return ("derived", 0.6)
    if is_derived:
        return ("derived", 0.3)
    if match_type == "table":
        if is_exact:
            return ("table_exact", 0.9)
        return ("table_partial", 0.7)
    if match_type == "text_regex":
        return ("text_regex", 0.5)
    return ("derived", 0.3)


def apply_confidence_filter(
    metadata: dict[str, ExtractionMetadata],
    threshold: float | None = None,
) -> tuple[dict[str, float | None], dict[str, dict]]:
    """
    Filter extraction metadata by confidence threshold.
    """
    from .legacy_helpers import CONFIDENCE_THRESHOLD

    if threshold is None:
        threshold = CONFIDENCE_THRESHOLD

    filtered_metrics: dict[str, float | None] = {}
    extraction_metadata_payload: dict[str, dict] = {}

    for key, meta in metadata.items():
        if meta.value is None or meta.confidence < threshold:
            filtered_metrics[key] = None
        else:
            filtered_metrics[key] = meta.value

        extraction_metadata_payload[key] = {
            "confidence": meta.confidence,
            "source": meta.source,
        }

    return filtered_metrics, extraction_metadata_payload


def _source_priority(match_type: str, is_exact: bool) -> int:
    """Return numeric priority for a raw extraction entry."""
    if match_type == "table" and is_exact:
        return 3
    if match_type == "text_regex":
        return 2
    if match_type == "table":
        return 1
    return 0


def _raw_set(
    raw: dict,
    key: str,
    value: float,
    match_type: str,
    is_exact: bool,
    candidate_quality: int = 50,
) -> None:
    """Set raw[key] with source+quality precedence."""
    new_priority = _source_priority(match_type, is_exact)
    if key in raw:
        existing_priority = _source_priority(raw[key][1], raw[key][2])
        existing_quality = raw[key][3] if len(raw[key]) > 3 else 50
        if new_priority < existing_priority:
            return
        if new_priority == existing_priority:
            if candidate_quality < existing_quality:
                return
            if candidate_quality == existing_quality:
                return
    raw[key] = (value, match_type, is_exact, candidate_quality)
