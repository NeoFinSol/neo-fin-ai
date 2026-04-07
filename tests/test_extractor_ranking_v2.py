from __future__ import annotations

from src.analysis.extractor import semantics
from src.analysis.extractor.types import RawMetricCandidate


def test_build_metadata_from_candidate_emits_v2_shape_and_quality_bonus() -> None:
    from src.analysis.extractor import ranking

    candidate = RawMetricCandidate(
        value=1000.0,
        match_type="table",
        is_exact=True,
        candidate_quality=115,
        source="table",
        match_semantics="exact",
        inference_mode="direct",
    )

    metadata = ranking.build_metadata_from_candidate(candidate)

    assert metadata.evidence_version == "v2"
    assert metadata.source == "table"
    assert metadata.match_semantics == "exact"
    assert metadata.inference_mode == "direct"
    assert metadata.confidence == 0.97


def test_build_metadata_from_candidate_applies_conflict_and_guardrail_penalties() -> (
    None
):
    from src.analysis.extractor import ranking

    candidate = RawMetricCandidate(
        value=1000.0,
        match_type="text_regex",
        is_exact=False,
        candidate_quality=90,
        source="text",
        match_semantics="keyword_match",
        inference_mode="direct",
        conflict_count=4,
        postprocess_state="guardrail_adjusted",
        reason_code=semantics.REASON_GUARDRAIL_SHORT_TERM_GT_TOTAL_ASSETS,
        signal_flags=[semantics.FLAG_POSTPROCESS_GUARDRAIL_ADJUSTED],
    )

    metadata = ranking.build_metadata_from_candidate(candidate)

    assert metadata.confidence == 0.34
    assert metadata.postprocess_state == "guardrail_adjusted"
    assert metadata.reason_code == semantics.REASON_GUARDRAIL_SHORT_TERM_GT_TOTAL_ASSETS


def test_apply_confidence_filter_normalizes_v1_payload_to_extended_metadata() -> None:
    from src.analysis.extractor import ranking
    from src.analysis.extractor.types import ExtractionMetadata

    filtered, payload = ranking.apply_confidence_filter(
        {
            "revenue": ExtractionMetadata(
                value=1000.0,
                confidence=0.7,
                source="table_partial",
            )
        },
        threshold=0.5,
    )

    assert filtered["revenue"] == 1000.0
    assert payload["revenue"]["evidence_version"] == "v1"
    assert payload["revenue"]["source"] == "table"
    assert payload["revenue"]["match_semantics"] == "not_applicable"
    assert (
        payload["revenue"]["reason_code"]
        == semantics.REASON_LEGACY_TABLE_PARTIAL_UNRESOLVED
    )
    assert (
        semantics.FLAG_COMPAT_NORMALIZED_FROM_V1 in payload["revenue"]["signal_flags"]
    )


def test_apply_confidence_filter_keeps_authoritative_override_even_below_threshold() -> (
    None
):
    from src.analysis.extractor import ranking
    from src.analysis.extractor.types import ExtractionMetadata

    filtered, payload = ranking.apply_confidence_filter(
        {
            "ebitda": ExtractionMetadata(
                value=85_628_000_000.0,
                confidence=0.10,
                source="issuer_fallback",
                evidence_version="v2",
                match_semantics="not_applicable",
                inference_mode="policy_override",
                postprocess_state="none",
                reason_code=semantics.REASON_ISSUER_REPO_OVERRIDE,
                signal_flags=[],
                candidate_quality=None,
                authoritative_override=True,
            )
        },
        threshold=0.5,
    )

    assert filtered["ebitda"] == 85_628_000_000.0
    assert payload["ebitda"]["authoritative_override"] is True
