from __future__ import annotations

from . import semantics
from .types import ExtractionMetadata


def is_strong_direct_evidence_with_threshold(
    metadata: ExtractionMetadata,
    *,
    strong_direct_threshold: float,
) -> bool:
    normalized = semantics.normalize_legacy_metadata(metadata)
    if normalized.value is None:
        return False
    if normalized.inference_mode != semantics.MODE_DIRECT:
        return False
    return normalized.confidence >= strong_direct_threshold


def is_replaceable_by_llm_with_threshold(
    metadata: ExtractionMetadata,
    *,
    threshold: float,
) -> bool:
    normalized = semantics.normalize_legacy_metadata(metadata)
    if normalized.authoritative_override:
        return False
    if normalized.inference_mode == semantics.MODE_DERIVED:
        return True
    return not semantics.survives_confidence_filter(normalized, threshold=threshold)


def should_prefer_llm_metric(
    llm_meta: ExtractionMetadata | None,
    fallback_meta: ExtractionMetadata | None,
    *,
    threshold: float,
    strong_direct_threshold: float | None = None,
) -> bool:
    effective_strong_threshold = (
        semantics.ACTIVE_CONFIDENCE_POLICY.strong_direct_threshold
        if strong_direct_threshold is None
        else strong_direct_threshold
    )

    if llm_meta is None or llm_meta.value is None:
        return False
    if not semantics.survives_confidence_filter(llm_meta, threshold):
        return False
    if not is_strong_direct_evidence_with_threshold(
        llm_meta,
        strong_direct_threshold=effective_strong_threshold,
    ):
        return False
    if fallback_meta is None or fallback_meta.value is None:
        return True
    if semantics.is_authoritative_override(fallback_meta):
        return False
    if is_replaceable_by_llm_with_threshold(fallback_meta, threshold=threshold):
        return True

    fallback_value = float(fallback_meta.value)
    llm_value = float(llm_meta.value)
    if fallback_value == 0.0 or llm_value == 0.0:
        return False
    if fallback_value * llm_value < 0:
        return False

    ratio = max(abs(fallback_value), abs(llm_value)) / max(
        min(abs(fallback_value), abs(llm_value)),
        1e-9,
    )
    return ratio < 10.0


LLM_MERGE_REASON_AUTHORITATIVE_OVERRIDE = "llm_rejected_authoritative_override"
LLM_MERGE_REASON_STRONG_DIRECT_FALLBACK = "llm_rejected_strong_direct_fallback"
LLM_MERGE_REASON_SAME_SIGN_RATIO = "llm_rejected_same_sign_ratio"
LLM_MERGE_REASON_BELOW_THRESHOLD = "llm_rejected_below_threshold"


def _llm_rejection_reason(
    llm_meta: ExtractionMetadata | None,
    fallback_meta: ExtractionMetadata | None,
    *,
    threshold: float,
    strong_direct_threshold: float | None = None,
) -> str | None:
    effective_strong_threshold = (
        semantics.ACTIVE_CONFIDENCE_POLICY.strong_direct_threshold
        if strong_direct_threshold is None
        else strong_direct_threshold
    )

    if llm_meta is None or llm_meta.value is None:
        return None
    if not semantics.survives_confidence_filter(llm_meta, threshold):
        return LLM_MERGE_REASON_BELOW_THRESHOLD
    if not is_strong_direct_evidence_with_threshold(
        llm_meta,
        strong_direct_threshold=effective_strong_threshold,
    ):
        return LLM_MERGE_REASON_BELOW_THRESHOLD
    if fallback_meta is None or fallback_meta.value is None:
        return None
    if semantics.is_authoritative_override(fallback_meta):
        return LLM_MERGE_REASON_AUTHORITATIVE_OVERRIDE
    if is_replaceable_by_llm_with_threshold(fallback_meta, threshold=threshold):
        return None

    fallback_value = float(fallback_meta.value)
    llm_value = float(llm_meta.value)
    if fallback_value == 0.0 or llm_value == 0.0:
        return LLM_MERGE_REASON_SAME_SIGN_RATIO
    if fallback_value * llm_value < 0:
        return LLM_MERGE_REASON_SAME_SIGN_RATIO
    ratio = max(abs(fallback_value), abs(llm_value)) / max(
        min(abs(fallback_value), abs(llm_value)),
        1e-9,
    )
    if ratio >= 10.0:
        return LLM_MERGE_REASON_SAME_SIGN_RATIO
    return LLM_MERGE_REASON_STRONG_DIRECT_FALLBACK


__all__ = [
    "LLM_MERGE_REASON_AUTHORITATIVE_OVERRIDE",
    "LLM_MERGE_REASON_BELOW_THRESHOLD",
    "LLM_MERGE_REASON_SAME_SIGN_RATIO",
    "LLM_MERGE_REASON_STRONG_DIRECT_FALLBACK",
    "_llm_rejection_reason",
    "is_replaceable_by_llm_with_threshold",
    "is_strong_direct_evidence_with_threshold",
    "should_prefer_llm_metric",
]
