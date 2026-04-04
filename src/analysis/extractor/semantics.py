from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from .types import ExtractionMetadata

V1: Final = "v1"
V2: Final = "v2"

SOURCE_TABLE: Final = "table"
SOURCE_TEXT: Final = "text"
SOURCE_OCR: Final = "ocr"
SOURCE_DERIVED: Final = "derived"
SOURCE_ISSUER_FALLBACK: Final = "issuer_fallback"

MATCH_EXACT: Final = "exact"
MATCH_CODE: Final = "code_match"
MATCH_SECTION: Final = "section_match"
MATCH_KEYWORD: Final = "keyword_match"
MATCH_NA: Final = "not_applicable"

MODE_DIRECT: Final = "direct"
MODE_DERIVED: Final = "derived"
MODE_APPROXIMATION: Final = "approximation"
MODE_POLICY_OVERRIDE: Final = "policy_override"

POSTPROCESS_NONE: Final = "none"
POSTPROCESS_GUARDRAIL: Final = "guardrail_adjusted"

REASON_ISSUER_REPO_OVERRIDE: Final = "issuer_repo_override"
REASON_LEGACY_TABLE_PARTIAL_UNRESOLVED: Final = "legacy_table_partial_unresolved"
REASON_LEGACY_TEXT_REGEX_UNRESOLVED: Final = "legacy_text_regex_unresolved"
REASON_GROSS_PROFIT_TO_EBITDA_APPROXIMATION: Final = (
    "gross_profit_to_ebitda_approximation"
)
REASON_LLM_EXTRACTION: Final = "llm_extraction"
REASON_GUARDRAIL_CURRENT_ASSETS_GT_TOTAL_ASSETS: Final = (
    "guardrail_current_assets_gt_total_assets"
)
REASON_GUARDRAIL_LIABILITIES_GT_TOTAL_ASSETS: Final = (
    "guardrail_liabilities_gt_total_assets"
)
REASON_GUARDRAIL_EQUITY_GT_TOTAL_ASSETS: Final = "guardrail_equity_gt_total_assets"
REASON_GUARDRAIL_SHORT_TERM_GT_TOTAL_ASSETS: Final = (
    "guardrail_short_term_liabilities_gt_total_assets"
)
REASON_GUARDRAIL_COMPONENT_GT_CURRENT_ASSETS: Final = (
    "guardrail_component_gt_current_assets"
)
REASON_GUARDRAIL_SHORT_TERM_GT_LIABILITIES: Final = (
    "guardrail_short_term_liabilities_gt_liabilities"
)

FLAG_COMPAT_NORMALIZED_FROM_V1: Final = "compat:normalized_from_v1"
FLAG_POSTPROCESS_GUARDRAIL_ADJUSTED: Final = "pp:guardrail_adjusted"

ProfileKey = tuple[str, str, str]


@dataclass(frozen=True, slots=True)
class EvidenceProfile:
    rank: int
    baseline_confidence: float
    description: str
    allowed_signal_whitelist: frozenset[str]


@dataclass(frozen=True, slots=True)
class SemanticsDecisionLog:
    profile_key: ProfileKey
    baseline_confidence: float
    quality_delta: float
    structural_bonus: float
    conflict_penalty: float
    guardrail_penalty: float
    final_confidence: float
    postprocess_state: str
    authoritative_override: bool


STRUCTURAL_BONUS_SIGNALS: Final[frozenset[str]] = frozenset(
    {
        "ev:line_code",
        "ev:section_total",
        "ev:ocr_row_crop_exact",
    }
)

QUALITY_BAND_HIGH_PLUS: Final = 0.04
QUALITY_BAND_MEDIUM_PLUS: Final = 0.02
QUALITY_BAND_NEUTRAL: Final = 0.00
QUALITY_BAND_LOW_MINUS: Final = -0.04
QUALITY_BAND_VERY_LOW_MINUS: Final = -0.08
STRUCTURAL_BONUS: Final = 0.03
GUARDRAIL_PENALTY: Final = -0.08
CONFLICT_PENALTY_STEP: Final = -0.04
CONFLICT_PENALTY_CAP: Final = -0.12

EVIDENCE_PROFILES: Final[dict[ProfileKey, EvidenceProfile]] = {
    (SOURCE_TABLE, MATCH_EXACT, MODE_DIRECT): EvidenceProfile(
        rank=90,
        baseline_confidence=0.92,
        description="Exact metric match in a table row.",
        allowed_signal_whitelist=STRUCTURAL_BONUS_SIGNALS,
    ),
    (SOURCE_TABLE, MATCH_CODE, MODE_DIRECT): EvidenceProfile(
        rank=80,
        baseline_confidence=0.88,
        description="Table candidate supported by a statement line code.",
        allowed_signal_whitelist=STRUCTURAL_BONUS_SIGNALS,
    ),
    (SOURCE_TABLE, MATCH_SECTION, MODE_DIRECT): EvidenceProfile(
        rank=70,
        baseline_confidence=0.80,
        description="Table section total or heading-supported match.",
        allowed_signal_whitelist=STRUCTURAL_BONUS_SIGNALS,
    ),
    (SOURCE_TEXT, MATCH_CODE, MODE_DIRECT): EvidenceProfile(
        rank=60,
        baseline_confidence=0.72,
        description="Text candidate supported by statement line code.",
        allowed_signal_whitelist=STRUCTURAL_BONUS_SIGNALS,
    ),
    (SOURCE_TEXT, MATCH_EXACT, MODE_DIRECT): EvidenceProfile(
        rank=48,
        baseline_confidence=0.66,
        description="Exact textual line match without explicit statement code.",
        allowed_signal_whitelist=STRUCTURAL_BONUS_SIGNALS,
    ),
    (SOURCE_TEXT, MATCH_SECTION, MODE_DIRECT): EvidenceProfile(
        rank=44,
        baseline_confidence=0.64,
        description="Section-total match recovered from structured text.",
        allowed_signal_whitelist=STRUCTURAL_BONUS_SIGNALS,
    ),
    (SOURCE_OCR, MATCH_EXACT, MODE_DIRECT): EvidenceProfile(
        rank=55,
        baseline_confidence=0.70,
        description="OCR candidate with exact structural match.",
        allowed_signal_whitelist=STRUCTURAL_BONUS_SIGNALS,
    ),
    (SOURCE_OCR, MATCH_CODE, MODE_DIRECT): EvidenceProfile(
        rank=50,
        baseline_confidence=0.68,
        description="OCR candidate supported by statement line code.",
        allowed_signal_whitelist=STRUCTURAL_BONUS_SIGNALS,
    ),
    (SOURCE_OCR, MATCH_SECTION, MODE_DIRECT): EvidenceProfile(
        rank=45,
        baseline_confidence=0.64,
        description="OCR candidate supported by section-total structure.",
        allowed_signal_whitelist=STRUCTURAL_BONUS_SIGNALS,
    ),
    (SOURCE_TABLE, MATCH_KEYWORD, MODE_DIRECT): EvidenceProfile(
        rank=40,
        baseline_confidence=0.62,
        description=(
            "Keyword match in a table row; higher than text keyword matches due to "
            "tabular structural prior."
        ),
        allowed_signal_whitelist=STRUCTURAL_BONUS_SIGNALS,
    ),
    (SOURCE_TEXT, MATCH_KEYWORD, MODE_DIRECT): EvidenceProfile(
        rank=30,
        baseline_confidence=0.58,
        description="Keyword match in plain text without stronger structure.",
        allowed_signal_whitelist=frozenset(),
    ),
    (SOURCE_DERIVED, MATCH_NA, MODE_DERIVED): EvidenceProfile(
        rank=20,
        baseline_confidence=0.35,
        description="Value derived from already accepted evidence using an allowed formula.",
        allowed_signal_whitelist=frozenset(),
    ),
    (SOURCE_TABLE, MATCH_EXACT, MODE_APPROXIMATION): EvidenceProfile(
        rank=10,
        baseline_confidence=0.20,
        description="Approximation from table evidence.",
        allowed_signal_whitelist=frozenset(),
    ),
    (SOURCE_TABLE, MATCH_CODE, MODE_APPROXIMATION): EvidenceProfile(
        rank=10,
        baseline_confidence=0.20,
        description="Approximation from code-supported table evidence.",
        allowed_signal_whitelist=frozenset(),
    ),
    (SOURCE_TABLE, MATCH_SECTION, MODE_APPROXIMATION): EvidenceProfile(
        rank=10,
        baseline_confidence=0.20,
        description="Approximation from section-supported table evidence.",
        allowed_signal_whitelist=frozenset(),
    ),
    (SOURCE_TABLE, MATCH_KEYWORD, MODE_APPROXIMATION): EvidenceProfile(
        rank=10,
        baseline_confidence=0.20,
        description="Approximation from keyword-supported table evidence.",
        allowed_signal_whitelist=frozenset(),
    ),
    (SOURCE_TEXT, MATCH_CODE, MODE_APPROXIMATION): EvidenceProfile(
        rank=10,
        baseline_confidence=0.20,
        description="Approximation from code-supported text evidence.",
        allowed_signal_whitelist=frozenset(),
    ),
    (SOURCE_TEXT, MATCH_SECTION, MODE_APPROXIMATION): EvidenceProfile(
        rank=10,
        baseline_confidence=0.20,
        description="Approximation from section-supported text evidence.",
        allowed_signal_whitelist=frozenset(),
    ),
    (SOURCE_TEXT, MATCH_KEYWORD, MODE_APPROXIMATION): EvidenceProfile(
        rank=10,
        baseline_confidence=0.20,
        description="Approximation from keyword-supported text evidence.",
        allowed_signal_whitelist=frozenset(),
    ),
    (SOURCE_OCR, MATCH_EXACT, MODE_APPROXIMATION): EvidenceProfile(
        rank=10,
        baseline_confidence=0.20,
        description="Approximation from OCR exact evidence.",
        allowed_signal_whitelist=frozenset(),
    ),
    (SOURCE_OCR, MATCH_CODE, MODE_APPROXIMATION): EvidenceProfile(
        rank=10,
        baseline_confidence=0.20,
        description="Approximation from OCR code-supported evidence.",
        allowed_signal_whitelist=frozenset(),
    ),
    (SOURCE_OCR, MATCH_SECTION, MODE_APPROXIMATION): EvidenceProfile(
        rank=10,
        baseline_confidence=0.20,
        description="Approximation from OCR section-supported evidence.",
        allowed_signal_whitelist=frozenset(),
    ),
    (SOURCE_ISSUER_FALLBACK, MATCH_NA, MODE_POLICY_OVERRIDE): EvidenceProfile(
        rank=0,
        baseline_confidence=0.95,
        description="Authoritative repo-backed issuer override policy path.",
        allowed_signal_whitelist=frozenset(),
    ),
}


def get_profile(profile_key: ProfileKey) -> EvidenceProfile:
    try:
        return EVIDENCE_PROFILES[profile_key]
    except KeyError as exc:
        raise ValueError(f"Unsupported evidence profile: {profile_key!r}") from exc


def compare_profile_trust(left: ProfileKey, right: ProfileKey) -> int:
    left_profile = get_profile(left)
    right_profile = get_profile(right)
    return (left_profile.rank > right_profile.rank) - (
        left_profile.rank < right_profile.rank
    )


def quality_delta(candidate_quality: int | None) -> float:
    if candidate_quality is None:
        return QUALITY_BAND_NEUTRAL
    if candidate_quality >= 110:
        return QUALITY_BAND_HIGH_PLUS
    if candidate_quality >= 90:
        return QUALITY_BAND_MEDIUM_PLUS
    if candidate_quality >= 75:
        return QUALITY_BAND_NEUTRAL
    if candidate_quality >= 60:
        return QUALITY_BAND_LOW_MINUS
    return QUALITY_BAND_VERY_LOW_MINUS


def structural_bonus(
    signal_flags: list[str] | tuple[str, ...] | frozenset[str]
) -> float:
    if any(flag in STRUCTURAL_BONUS_SIGNALS for flag in signal_flags):
        return STRUCTURAL_BONUS
    return 0.0


def conflict_penalty(conflict_count: int) -> float:
    if conflict_count <= 0:
        return 0.0
    return max(CONFLICT_PENALTY_CAP, conflict_count * CONFLICT_PENALTY_STEP)


def guardrail_penalty(postprocess_state: str) -> float:
    if postprocess_state == POSTPROCESS_GUARDRAIL:
        return GUARDRAIL_PENALTY
    return 0.0


def calculate_confidence(
    profile_key: ProfileKey,
    *,
    candidate_quality: int | None,
    signal_flags: list[str] | tuple[str, ...] | frozenset[str],
    conflict_count: int,
    postprocess_state: str,
) -> float:
    return build_decision_log(
        profile_key,
        candidate_quality=candidate_quality,
        signal_flags=signal_flags,
        conflict_count=conflict_count,
        postprocess_state=postprocess_state,
        authoritative_override=False,
    ).final_confidence


def build_decision_log(
    profile_key: ProfileKey,
    *,
    candidate_quality: int | None,
    signal_flags: list[str] | tuple[str, ...] | frozenset[str],
    conflict_count: int,
    postprocess_state: str,
    authoritative_override: bool,
) -> SemanticsDecisionLog:
    profile = get_profile(profile_key)
    quality_delta_value = quality_delta(candidate_quality)
    structural_bonus_value = structural_bonus(signal_flags)
    conflict_penalty_value = conflict_penalty(conflict_count)
    guardrail_penalty_value = guardrail_penalty(postprocess_state)
    score = profile.baseline_confidence
    score += quality_delta_value
    score += structural_bonus_value
    score += conflict_penalty_value
    score += guardrail_penalty_value
    return SemanticsDecisionLog(
        profile_key=profile_key,
        baseline_confidence=profile.baseline_confidence,
        quality_delta=quality_delta_value,
        structural_bonus=structural_bonus_value,
        conflict_penalty=conflict_penalty_value,
        guardrail_penalty=guardrail_penalty_value,
        final_confidence=max(0.0, min(1.0, round(score, 6))),
        postprocess_state=postprocess_state,
        authoritative_override=authoritative_override,
    )


def infer_profile_key_from_legacy_match(
    match_type: str,
    *,
    is_exact: bool,
) -> ProfileKey:
    if match_type in {"derived", "derived_strong"}:
        return (SOURCE_DERIVED, MATCH_NA, MODE_DERIVED)
    if match_type == "table":
        if is_exact:
            return (SOURCE_TABLE, MATCH_EXACT, MODE_DIRECT)
        return (SOURCE_TABLE, MATCH_KEYWORD, MODE_DIRECT)
    if match_type == "text_regex":
        return (SOURCE_TEXT, MATCH_KEYWORD, MODE_DIRECT)
    return (SOURCE_DERIVED, MATCH_NA, MODE_DERIVED)


def validate_public_metadata_state(metadata: ExtractionMetadata) -> None:
    if metadata.inference_mode == MODE_POLICY_OVERRIDE:
        if metadata.source != SOURCE_ISSUER_FALLBACK:
            raise ValueError("policy_override is only valid for issuer_fallback")
        if metadata.match_semantics != MATCH_NA:
            raise ValueError("issuer_fallback must use not_applicable match semantics")
        if not metadata.authoritative_override:
            raise ValueError("policy_override requires authoritative_override=True")
        if not metadata.reason_code:
            raise ValueError("issuer_fallback policy override requires a reason_code")

    if metadata.inference_mode == MODE_DERIVED and metadata.source != SOURCE_DERIVED:
        raise ValueError("derived inference mode is only valid for source=derived")

    if metadata.source == SOURCE_DERIVED and metadata.inference_mode != MODE_DERIVED:
        raise ValueError("source=derived requires inference_mode=derived")

    if metadata.match_semantics == MATCH_NA and metadata.source not in {
        SOURCE_DERIVED,
        SOURCE_ISSUER_FALLBACK,
    }:
        if metadata.evidence_version != V1:
            raise ValueError(
                "not_applicable match semantics are only valid for derived, issuer_fallback, or v1-normalized metadata"
            )

    if metadata.postprocess_state == POSTPROCESS_GUARDRAIL:
        if not metadata.reason_code:
            raise ValueError("guardrail_adjusted metadata requires a reason_code")
        if not any(flag.startswith("pp:") for flag in metadata.signal_flags):
            raise ValueError("guardrail_adjusted metadata requires a pp:* signal flag")

    if (
        metadata.authoritative_override
        and metadata.inference_mode != MODE_POLICY_OVERRIDE
    ):
        raise ValueError(
            "authoritative_override is only valid for policy_override metadata"
        )


def normalize_legacy_metadata(metadata: ExtractionMetadata) -> ExtractionMetadata:
    if metadata.evidence_version == V2:
        validate_public_metadata_state(metadata)
        return metadata

    if metadata.source == "table_exact":
        normalized = ExtractionMetadata(
            value=metadata.value,
            confidence=metadata.confidence,
            source=SOURCE_TABLE,
            evidence_version=V1,
            match_semantics=MATCH_EXACT,
            inference_mode=MODE_DIRECT,
            postprocess_state=POSTPROCESS_NONE,
            reason_code=None,
            signal_flags=[FLAG_COMPAT_NORMALIZED_FROM_V1],
            candidate_quality=None,
            authoritative_override=False,
        )
    elif metadata.source == "table_partial":
        normalized = ExtractionMetadata(
            value=metadata.value,
            confidence=metadata.confidence,
            source=SOURCE_TABLE,
            evidence_version=V1,
            match_semantics=MATCH_NA,
            inference_mode=MODE_DIRECT,
            postprocess_state=POSTPROCESS_NONE,
            reason_code=REASON_LEGACY_TABLE_PARTIAL_UNRESOLVED,
            signal_flags=[FLAG_COMPAT_NORMALIZED_FROM_V1],
            candidate_quality=None,
            authoritative_override=False,
        )
    elif metadata.source == "text_regex":
        normalized = ExtractionMetadata(
            value=metadata.value,
            confidence=metadata.confidence,
            source=SOURCE_TEXT,
            evidence_version=V1,
            match_semantics=MATCH_NA,
            inference_mode=MODE_DIRECT,
            postprocess_state=POSTPROCESS_NONE,
            reason_code=REASON_LEGACY_TEXT_REGEX_UNRESOLVED,
            signal_flags=[FLAG_COMPAT_NORMALIZED_FROM_V1],
            candidate_quality=None,
            authoritative_override=False,
        )
    elif metadata.source == "issuer_fallback":
        normalized = ExtractionMetadata(
            value=metadata.value,
            confidence=metadata.confidence,
            source=SOURCE_ISSUER_FALLBACK,
            evidence_version=V1,
            match_semantics=MATCH_NA,
            inference_mode=MODE_POLICY_OVERRIDE,
            postprocess_state=POSTPROCESS_NONE,
            reason_code=REASON_ISSUER_REPO_OVERRIDE,
            signal_flags=[FLAG_COMPAT_NORMALIZED_FROM_V1],
            candidate_quality=None,
            authoritative_override=True,
        )
    else:
        normalized = ExtractionMetadata(
            value=metadata.value,
            confidence=metadata.confidence,
            source=SOURCE_DERIVED,
            evidence_version=V1,
            match_semantics=MATCH_NA,
            inference_mode=MODE_DERIVED,
            postprocess_state=POSTPROCESS_NONE,
            reason_code=None,
            signal_flags=[FLAG_COMPAT_NORMALIZED_FROM_V1],
            candidate_quality=None,
            authoritative_override=False,
        )

    validate_public_metadata_state(normalized)
    return normalized


def survives_confidence_filter(
    metadata: ExtractionMetadata,
    threshold: float,
) -> bool:
    normalized = normalize_legacy_metadata(metadata)
    if normalized.value is None:
        return False
    if normalized.authoritative_override:
        return True
    return normalized.confidence >= threshold


def is_authoritative_override(metadata: ExtractionMetadata) -> bool:
    return normalize_legacy_metadata(metadata).authoritative_override


def is_strong_direct_evidence(metadata: ExtractionMetadata) -> bool:
    normalized = normalize_legacy_metadata(metadata)
    if normalized.inference_mode != MODE_DIRECT:
        return False
    return normalized.confidence >= 0.7


def is_replaceable_by_llm(
    metadata: ExtractionMetadata,
    *,
    threshold: float = 0.5,
) -> bool:
    normalized = normalize_legacy_metadata(metadata)
    if normalized.authoritative_override:
        return False
    if normalized.inference_mode == MODE_DERIVED:
        return True
    return not survives_confidence_filter(normalized, threshold=threshold)


__all__ = [
    "EVIDENCE_PROFILES",
    "EvidenceProfile",
    "FLAG_COMPAT_NORMALIZED_FROM_V1",
    "FLAG_POSTPROCESS_GUARDRAIL_ADJUSTED",
    "GUARDRAIL_PENALTY",
    "MATCH_CODE",
    "MATCH_EXACT",
    "MATCH_KEYWORD",
    "MATCH_NA",
    "MATCH_SECTION",
    "MODE_APPROXIMATION",
    "MODE_DERIVED",
    "MODE_DIRECT",
    "MODE_POLICY_OVERRIDE",
    "POSTPROCESS_GUARDRAIL",
    "POSTPROCESS_NONE",
    "REASON_GUARDRAIL_COMPONENT_GT_CURRENT_ASSETS",
    "REASON_GUARDRAIL_CURRENT_ASSETS_GT_TOTAL_ASSETS",
    "REASON_GUARDRAIL_EQUITY_GT_TOTAL_ASSETS",
    "REASON_GUARDRAIL_LIABILITIES_GT_TOTAL_ASSETS",
    "REASON_GUARDRAIL_SHORT_TERM_GT_LIABILITIES",
    "REASON_GUARDRAIL_SHORT_TERM_GT_TOTAL_ASSETS",
    "REASON_ISSUER_REPO_OVERRIDE",
    "REASON_GROSS_PROFIT_TO_EBITDA_APPROXIMATION",
    "REASON_LLM_EXTRACTION",
    "REASON_LEGACY_TABLE_PARTIAL_UNRESOLVED",
    "REASON_LEGACY_TEXT_REGEX_UNRESOLVED",
    "SemanticsDecisionLog",
    "SOURCE_DERIVED",
    "SOURCE_ISSUER_FALLBACK",
    "SOURCE_OCR",
    "SOURCE_TABLE",
    "SOURCE_TEXT",
    "build_decision_log",
    "STRUCTURAL_BONUS_SIGNALS",
    "V1",
    "V2",
    "calculate_confidence",
    "compare_profile_trust",
    "conflict_penalty",
    "get_profile",
    "guardrail_penalty",
    "infer_profile_key_from_legacy_match",
    "is_authoritative_override",
    "is_replaceable_by_llm",
    "is_strong_direct_evidence",
    "normalize_legacy_metadata",
    "quality_delta",
    "structural_bonus",
    "survives_confidence_filter",
    "validate_public_metadata_state",
]
