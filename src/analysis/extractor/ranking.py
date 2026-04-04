from __future__ import annotations

from . import semantics
from .types import (
    ExtractionMetadata,
    ExtractionSource,
    RawCandidates,
    RawMetricCandidate,
)


def determine_source(
    match_type: str,
    is_exact: bool = False,
    is_derived: bool = False,
) -> tuple[ExtractionSource, float]:
    """
    Backward-compatible helper that maps legacy raw match hints to a V2 source family
    and baseline confidence.
    """
    profile_key = semantics.infer_profile_key_from_legacy_match(
        "derived" if is_derived else match_type,
        is_exact=is_exact,
    )
    source, _, _ = profile_key
    confidence = semantics.calculate_confidence(
        profile_key,
        candidate_quality=None,
        signal_flags=(),
        conflict_count=0,
        postprocess_state=semantics.POSTPROCESS_NONE,
    )
    return source, confidence


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
        normalized = semantics.normalize_legacy_metadata(meta)
        if not semantics.survives_confidence_filter(normalized, threshold):
            filtered_metrics[key] = None
        else:
            filtered_metrics[key] = normalized.value

        extraction_metadata_payload[key] = {
            "evidence_version": normalized.evidence_version,
            "confidence": normalized.confidence,
            "source": normalized.source,
            "match_semantics": normalized.match_semantics,
            "inference_mode": normalized.inference_mode,
            "postprocess_state": normalized.postprocess_state,
            "reason_code": normalized.reason_code,
            "signal_flags": list(normalized.signal_flags),
            "candidate_quality": normalized.candidate_quality,
            "authoritative_override": normalized.authoritative_override,
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


def _get_existing_candidate(
    raw: RawCandidates | dict,
    key: str,
) -> RawMetricCandidate | tuple | None:
    if isinstance(raw, RawCandidates):
        return raw.get(key)
    return raw.get(key)


def _set_candidate(
    raw: RawCandidates | dict,
    key: str,
    candidate: RawMetricCandidate,
) -> None:
    if isinstance(raw, RawCandidates):
        raw[key] = candidate
        return
    raw[key] = (
        candidate.value,
        candidate.match_type,
        candidate.is_exact,
        candidate.candidate_quality,
    )


def _raw_set(
    raw: RawCandidates | dict,
    key: str,
    value: float,
    match_type: str,
    is_exact: bool,
    candidate_quality: int = 50,
    *,
    source: str | None = None,
    match_semantics: str | None = None,
    inference_mode: str | None = None,
    reason_code: str | None = None,
    signal_flags: list[str] | None = None,
    postprocess_state: str = semantics.POSTPROCESS_NONE,
    authoritative_override: bool = False,
) -> None:
    """Set raw[key] with source+quality precedence."""
    new_priority = _source_priority(match_type, is_exact)
    existing = _get_existing_candidate(raw, key)

    next_signal_flags = list(signal_flags or [])
    _, _, resolved_inference_mode = _resolve_candidate_semantics(
        match_type=match_type,
        is_exact=is_exact,
        source=source,
        match_semantics=match_semantics,
        inference_mode=inference_mode,
    )

    existing_candidate: RawMetricCandidate | None = None
    if isinstance(existing, RawMetricCandidate):
        existing_candidate = existing

    if existing is not None:
        if isinstance(existing, RawMetricCandidate):
            existing_priority = _source_priority(
                existing.match_type,
                existing.is_exact,
            )
            existing_quality = existing.candidate_quality
        else:
            existing_priority = _source_priority(existing[1], existing[2])
            existing_quality = existing[3] if len(existing) > 3 else 50

        if new_priority < existing_priority:
            if (
                existing_candidate is not None
                and _counts_as_competing_direct_candidate(
                    candidate_quality=candidate_quality,
                    inference_mode=resolved_inference_mode,
                )
                and _materially_differs(existing_candidate.value, value)
            ):
                existing_candidate.conflict_count += 1
            return
        if new_priority == existing_priority:
            if candidate_quality < existing_quality:
                if (
                    existing_candidate is not None
                    and _counts_as_competing_direct_candidate(
                        candidate_quality=candidate_quality,
                        inference_mode=resolved_inference_mode,
                    )
                    and _materially_differs(existing_candidate.value, value)
                ):
                    existing_candidate.conflict_count += 1
                return
            if candidate_quality == existing_quality:
                if (
                    existing_candidate is not None
                    and _counts_as_competing_direct_candidate(
                        candidate_quality=candidate_quality,
                        inference_mode=resolved_inference_mode,
                    )
                    and _materially_differs(existing_candidate.value, value)
                ):
                    existing_candidate.conflict_count += 1
                return

    resolved_source, resolved_match_semantics = _resolve_candidate_semantics(
        match_type=match_type,
        is_exact=is_exact,
        source=source,
        match_semantics=match_semantics,
        inference_mode=resolved_inference_mode,
    )[:2]

    _set_candidate(
        raw,
        key,
        RawMetricCandidate(
            value=value,
            match_type=match_type,
            is_exact=is_exact,
            candidate_quality=candidate_quality,
            source=resolved_source,
            match_semantics=resolved_match_semantics,
            inference_mode=resolved_inference_mode,
            reason_code=reason_code,
            signal_flags=next_signal_flags,
            conflict_count=0,
            postprocess_state=postprocess_state,
            authoritative_override=authoritative_override,
        ),
    )


def _materially_differs(existing_value: float, new_value: float) -> bool:
    return abs(existing_value - new_value) > max(
        1000.0,
        0.01 * max(abs(existing_value), abs(new_value)),
    )


def _counts_as_competing_direct_candidate(
    *,
    candidate_quality: int,
    inference_mode: str,
) -> bool:
    return candidate_quality >= 60 and inference_mode == semantics.MODE_DIRECT


def _resolve_candidate_semantics(
    *,
    match_type: str,
    is_exact: bool,
    source: str | None,
    match_semantics: str | None,
    inference_mode: str | None,
) -> tuple[str, str, str]:
    if (
        source is not None
        and match_semantics is not None
        and inference_mode is not None
    ):
        return source, match_semantics, inference_mode

    profile_key = semantics.infer_profile_key_from_legacy_match(
        match_type,
        is_exact=is_exact,
    )
    inferred_source, inferred_match_semantics, inferred_inference_mode = profile_key
    return (
        source or inferred_source,
        match_semantics or inferred_match_semantics,
        inference_mode or inferred_inference_mode,
    )


def build_metadata_from_candidate(candidate: RawMetricCandidate) -> ExtractionMetadata:
    metadata, _ = build_metadata_with_decision_log("", candidate)
    return metadata


def build_metadata_with_decision_log(
    metric_key: str,
    candidate: RawMetricCandidate,
) -> tuple[ExtractionMetadata, semantics.SemanticsDecisionLog]:
    source = candidate.source
    match_semantics = candidate.match_semantics
    inference_mode = candidate.inference_mode
    if source is None or match_semantics is None or inference_mode is None:
        source, match_semantics, inference_mode = _resolve_candidate_semantics(
            match_type=candidate.match_type,
            is_exact=candidate.is_exact,
            source=source,
            match_semantics=match_semantics,
            inference_mode=inference_mode,
        )

    profile_key = (source, match_semantics, inference_mode)
    decision_log = semantics.build_decision_log(
        profile_key,
        metric_key=metric_key,
        candidate_quality=candidate.candidate_quality,
        signal_flags=candidate.signal_flags,
        conflict_count=candidate.conflict_count,
        postprocess_state=candidate.postprocess_state,
        authoritative_override=candidate.authoritative_override,
        reason_code=candidate.reason_code,
    )
    confidence = decision_log.final_confidence
    metadata = ExtractionMetadata(
        value=candidate.value,
        confidence=confidence,
        source=source,
        evidence_version=semantics.V2,
        match_semantics=match_semantics,
        inference_mode=inference_mode,
        postprocess_state=candidate.postprocess_state,
        reason_code=candidate.reason_code,
        signal_flags=list(candidate.signal_flags),
        candidate_quality=candidate.candidate_quality,
        authoritative_override=candidate.authoritative_override,
    )
    semantics.validate_public_metadata_state(metadata)
    return metadata, decision_log
