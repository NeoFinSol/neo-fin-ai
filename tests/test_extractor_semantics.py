from __future__ import annotations

import pytest

from src.analysis.extractor.types import ExtractionMetadata


def test_semantics_registry_exposes_expected_profile_order() -> None:
    from src.analysis.extractor import semantics

    assert (
        semantics.compare_profile_trust(
            ("table", "exact", "direct"),
            ("table", "code_match", "direct"),
        )
        > 0
    )
    assert (
        semantics.compare_profile_trust(
            ("text", "code_match", "direct"),
            ("ocr", "exact", "direct"),
        )
        > 0
    )
    assert (
        semantics.compare_profile_trust(
            ("ocr", "section_match", "direct"),
            ("text", "keyword_match", "direct"),
        )
        > 0
    )


def test_semantics_registry_rejects_forbidden_ocr_keyword_profile() -> None:
    from src.analysis.extractor import semantics

    with pytest.raises(ValueError, match="ocr.*keyword_match"):
        semantics.get_profile(("ocr", "keyword_match", "direct"))


def test_public_metadata_state_rejects_policy_override_outside_issuer_fallback() -> (
    None
):
    from src.analysis.extractor import semantics

    invalid = ExtractionMetadata(
        value=10.0,
        confidence=0.95,
        source="text",
        evidence_version="v2",
        match_semantics="not_applicable",
        inference_mode="policy_override",
        postprocess_state="none",
        reason_code="issuer_repo_override",
        signal_flags=[],
        candidate_quality=None,
        authoritative_override=False,
    )

    with pytest.raises(ValueError, match="policy_override"):
        semantics.validate_public_metadata_state(invalid)


def test_public_metadata_state_requires_reason_for_guardrail_adjusted() -> None:
    from src.analysis.extractor import semantics

    invalid = ExtractionMetadata(
        value=10.0,
        confidence=0.4,
        source="text",
        evidence_version="v2",
        match_semantics="keyword_match",
        inference_mode="direct",
        postprocess_state="guardrail_adjusted",
        reason_code=None,
        signal_flags=["pp:guardrail_adjusted"],
        candidate_quality=60,
        authoritative_override=False,
    )

    with pytest.raises(ValueError, match="guardrail"):
        semantics.validate_public_metadata_state(invalid)


def test_legacy_normalization_does_not_invent_missing_semantics() -> None:
    from src.analysis.extractor import semantics

    legacy = ExtractionMetadata(
        value=1000.0,
        confidence=0.7,
        source="table_partial",
    )

    normalized = semantics.normalize_legacy_metadata(legacy)

    assert normalized.evidence_version == "v1"
    assert normalized.source == "table"
    assert normalized.match_semantics == "not_applicable"
    assert normalized.inference_mode == "direct"
    assert normalized.reason_code == "legacy_table_partial_unresolved"
    assert "compat:normalized_from_v1" in normalized.signal_flags


def test_survives_confidence_filter_keeps_authoritative_override() -> None:
    from src.analysis.extractor import semantics

    metadata = ExtractionMetadata(
        value=1000.0,
        confidence=0.1,
        source="issuer_fallback",
        evidence_version="v2",
        match_semantics="not_applicable",
        inference_mode="policy_override",
        postprocess_state="none",
        reason_code="issuer_repo_override",
        signal_flags=[],
        candidate_quality=None,
        authoritative_override=True,
    )

    assert semantics.survives_confidence_filter(metadata, threshold=0.5) is True


def test_semantics_decision_log_captures_guardrail_and_override_state() -> None:
    from src.analysis.extractor import semantics

    decision = semantics.build_decision_log(
        ("issuer_fallback", "not_applicable", "policy_override"),
        candidate_quality=None,
        signal_flags=[],
        conflict_count=0,
        postprocess_state="none",
        authoritative_override=True,
    )

    assert decision.profile_key == (
        "issuer_fallback",
        "not_applicable",
        "policy_override",
    )
    assert decision.baseline_confidence == 0.95
    assert decision.final_confidence == 0.95
    assert decision.postprocess_state == "none"
    assert decision.authoritative_override is True
