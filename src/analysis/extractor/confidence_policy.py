from __future__ import annotations

from dataclasses import dataclass
from typing import Final

ProfileKey = tuple[str, str, str]

POSTPROCESS_GUARDRAIL: Final = "guardrail_adjusted"


@dataclass(frozen=True, slots=True)
class EvidenceProfile:
    rank: int
    baseline_confidence: float
    description: str
    allowed_signal_whitelist: frozenset[str]


@dataclass(frozen=True, slots=True)
class QualityBand:
    minimum_quality: int | None
    delta: float


@dataclass(frozen=True, slots=True)
class ConfidenceBreakdown:
    baseline_confidence: float
    quality_delta: float
    structural_bonus: float
    conflict_penalty: float
    guardrail_penalty: float
    final_confidence: float


@dataclass(frozen=True, slots=True)
class ConfidencePolicy:
    name: str
    profiles: dict[ProfileKey, EvidenceProfile]
    quality_bands: tuple[QualityBand, ...]
    structural_bonus_signals: frozenset[str]
    structural_bonus_delta: float
    guardrail_penalty_delta: float
    conflict_penalty_step: float
    conflict_penalty_cap: float
    strong_direct_threshold: float = 0.7

    def get_profile(self, profile_key: ProfileKey) -> EvidenceProfile:
        try:
            return self.profiles[profile_key]
        except KeyError as exc:
            raise ValueError(f"Unsupported evidence profile: {profile_key!r}") from exc

    def compare_profile_trust(self, left: ProfileKey, right: ProfileKey) -> int:
        left_profile = self.get_profile(left)
        right_profile = self.get_profile(right)
        return (left_profile.rank > right_profile.rank) - (
            left_profile.rank < right_profile.rank
        )

    def quality_delta(self, candidate_quality: int | None) -> float:
        if candidate_quality is None:
            return 0.0
        for band in self.quality_bands:
            if (
                band.minimum_quality is None
                or candidate_quality >= band.minimum_quality
            ):
                return band.delta
        return 0.0

    def structural_bonus(
        self,
        profile_key: ProfileKey,
        signal_flags: list[str] | tuple[str, ...] | frozenset[str],
    ) -> float:
        profile = self.get_profile(profile_key)
        if any(
            flag in self.structural_bonus_signals
            and flag in profile.allowed_signal_whitelist
            for flag in signal_flags
        ):
            return self.structural_bonus_delta
        return 0.0

    def conflict_penalty(self, conflict_count: int) -> float:
        if conflict_count <= 0:
            return 0.0
        return max(
            self.conflict_penalty_cap, conflict_count * self.conflict_penalty_step
        )

    def guardrail_penalty(self, postprocess_state: str) -> float:
        if postprocess_state == POSTPROCESS_GUARDRAIL:
            return self.guardrail_penalty_delta
        return 0.0


def build_policy_decision_log(
    policy: ConfidencePolicy,
    profile_key: ProfileKey,
    *,
    metric_key: str,
    candidate_quality: int | None,
    signal_flags: list[str] | tuple[str, ...] | frozenset[str],
    conflict_count: int,
    postprocess_state: str,
    authoritative_override: bool,
    reason_code: str | None,
) -> ConfidenceBreakdown:
    profile = policy.get_profile(profile_key)
    quality_delta_value = policy.quality_delta(candidate_quality)
    structural_bonus_value = policy.structural_bonus(profile_key, signal_flags)
    conflict_penalty_value = policy.conflict_penalty(conflict_count)
    guardrail_penalty_value = policy.guardrail_penalty(postprocess_state)
    score = profile.baseline_confidence
    score += quality_delta_value
    score += structural_bonus_value
    score += conflict_penalty_value
    score += guardrail_penalty_value
    return ConfidenceBreakdown(
        baseline_confidence=profile.baseline_confidence,
        quality_delta=quality_delta_value,
        structural_bonus=structural_bonus_value,
        conflict_penalty=conflict_penalty_value,
        guardrail_penalty=guardrail_penalty_value,
        final_confidence=max(0.0, min(1.0, round(score, 6))),
    )


STRUCTURAL_BONUS_SIGNALS: Final[frozenset[str]] = frozenset(
    {
        "ev:line_code",
        "ev:section_total",
        "ev:ocr_row_crop_exact",
    }
)


def _build_profiles(
    *,
    table_exact: float,
    table_code: float,
    table_section: float,
    text_code: float,
    text_exact: float,
    text_section: float,
    ocr_exact: float,
    ocr_code: float,
    ocr_section: float,
    table_keyword: float,
    text_keyword: float,
    derived: float,
    approximation: float,
    policy_override: float,
) -> dict[ProfileKey, EvidenceProfile]:
    return {
        ("table", "exact", "direct"): EvidenceProfile(
            rank=90,
            baseline_confidence=table_exact,
            description="Exact metric match in a table row.",
            allowed_signal_whitelist=STRUCTURAL_BONUS_SIGNALS,
        ),
        ("table", "code_match", "direct"): EvidenceProfile(
            rank=80,
            baseline_confidence=table_code,
            description="Table candidate supported by a statement line code.",
            allowed_signal_whitelist=STRUCTURAL_BONUS_SIGNALS,
        ),
        ("table", "section_match", "direct"): EvidenceProfile(
            rank=70,
            baseline_confidence=table_section,
            description="Table section total or heading-supported match.",
            allowed_signal_whitelist=STRUCTURAL_BONUS_SIGNALS,
        ),
        ("text", "code_match", "direct"): EvidenceProfile(
            rank=60,
            baseline_confidence=text_code,
            description="Text candidate supported by statement line code.",
            allowed_signal_whitelist=STRUCTURAL_BONUS_SIGNALS,
        ),
        ("text", "exact", "direct"): EvidenceProfile(
            rank=48,
            baseline_confidence=text_exact,
            description="Exact textual line match without explicit statement code.",
            allowed_signal_whitelist=STRUCTURAL_BONUS_SIGNALS,
        ),
        ("text", "section_match", "direct"): EvidenceProfile(
            rank=44,
            baseline_confidence=text_section,
            description="Section-total match recovered from structured text.",
            allowed_signal_whitelist=STRUCTURAL_BONUS_SIGNALS,
        ),
        ("ocr", "exact", "direct"): EvidenceProfile(
            rank=55,
            baseline_confidence=ocr_exact,
            description="OCR candidate with exact structural match.",
            allowed_signal_whitelist=STRUCTURAL_BONUS_SIGNALS,
        ),
        ("ocr", "code_match", "direct"): EvidenceProfile(
            rank=50,
            baseline_confidence=ocr_code,
            description="OCR candidate supported by statement line code.",
            allowed_signal_whitelist=STRUCTURAL_BONUS_SIGNALS,
        ),
        ("ocr", "section_match", "direct"): EvidenceProfile(
            rank=45,
            baseline_confidence=ocr_section,
            description="OCR candidate supported by section-total structure.",
            allowed_signal_whitelist=STRUCTURAL_BONUS_SIGNALS,
        ),
        ("table", "keyword_match", "direct"): EvidenceProfile(
            rank=40,
            baseline_confidence=table_keyword,
            description=(
                "Keyword match in a table row; higher than text keyword matches due to "
                "tabular structural prior."
            ),
            allowed_signal_whitelist=STRUCTURAL_BONUS_SIGNALS,
        ),
        ("text", "keyword_match", "direct"): EvidenceProfile(
            rank=30,
            baseline_confidence=text_keyword,
            description="Keyword match in plain text without stronger structure.",
            allowed_signal_whitelist=frozenset(),
        ),
        ("derived", "not_applicable", "derived"): EvidenceProfile(
            rank=20,
            baseline_confidence=derived,
            description="Value derived from already accepted evidence using an allowed formula.",
            allowed_signal_whitelist=frozenset(),
        ),
        ("table", "exact", "approximation"): EvidenceProfile(
            rank=10,
            baseline_confidence=approximation,
            description="Approximation from table evidence.",
            allowed_signal_whitelist=frozenset(),
        ),
        ("table", "code_match", "approximation"): EvidenceProfile(
            rank=10,
            baseline_confidence=approximation,
            description="Approximation from code-supported table evidence.",
            allowed_signal_whitelist=frozenset(),
        ),
        ("table", "section_match", "approximation"): EvidenceProfile(
            rank=10,
            baseline_confidence=approximation,
            description="Approximation from section-supported table evidence.",
            allowed_signal_whitelist=frozenset(),
        ),
        ("table", "keyword_match", "approximation"): EvidenceProfile(
            rank=10,
            baseline_confidence=approximation,
            description="Approximation from keyword-supported table evidence.",
            allowed_signal_whitelist=frozenset(),
        ),
        ("text", "code_match", "approximation"): EvidenceProfile(
            rank=10,
            baseline_confidence=approximation,
            description="Approximation from code-supported text evidence.",
            allowed_signal_whitelist=frozenset(),
        ),
        ("text", "section_match", "approximation"): EvidenceProfile(
            rank=10,
            baseline_confidence=approximation,
            description="Approximation from section-supported text evidence.",
            allowed_signal_whitelist=frozenset(),
        ),
        ("text", "keyword_match", "approximation"): EvidenceProfile(
            rank=10,
            baseline_confidence=approximation,
            description="Approximation from keyword-supported text evidence.",
            allowed_signal_whitelist=frozenset(),
        ),
        ("ocr", "exact", "approximation"): EvidenceProfile(
            rank=10,
            baseline_confidence=approximation,
            description="Approximation from OCR exact evidence.",
            allowed_signal_whitelist=frozenset(),
        ),
        ("ocr", "code_match", "approximation"): EvidenceProfile(
            rank=10,
            baseline_confidence=approximation,
            description="Approximation from OCR code-supported evidence.",
            allowed_signal_whitelist=frozenset(),
        ),
        ("ocr", "section_match", "approximation"): EvidenceProfile(
            rank=10,
            baseline_confidence=approximation,
            description="Approximation from OCR section-supported evidence.",
            allowed_signal_whitelist=frozenset(),
        ),
        ("issuer_fallback", "not_applicable", "policy_override"): EvidenceProfile(
            rank=0,
            baseline_confidence=policy_override,
            description="Authoritative repo-backed issuer override policy path.",
            allowed_signal_whitelist=frozenset(),
        ),
    }


BASELINE_RUNTIME_CONFIDENCE_POLICY: Final = ConfidencePolicy(
    name="baseline_runtime_v2",
    profiles=_build_profiles(
        table_exact=0.92,
        table_code=0.88,
        table_section=0.80,
        text_code=0.72,
        text_exact=0.66,
        text_section=0.64,
        ocr_exact=0.70,
        ocr_code=0.68,
        ocr_section=0.64,
        table_keyword=0.62,
        text_keyword=0.58,
        derived=0.35,
        approximation=0.20,
        policy_override=0.95,
    ),
    quality_bands=(
        QualityBand(minimum_quality=110, delta=0.04),
        QualityBand(minimum_quality=90, delta=0.02),
        QualityBand(minimum_quality=75, delta=0.00),
        QualityBand(minimum_quality=60, delta=-0.04),
        QualityBand(minimum_quality=None, delta=-0.08),
    ),
    structural_bonus_signals=STRUCTURAL_BONUS_SIGNALS,
    structural_bonus_delta=0.03,
    guardrail_penalty_delta=-0.08,
    conflict_penalty_step=-0.04,
    conflict_penalty_cap=-0.12,
    strong_direct_threshold=0.7,
)


CALIBRATED_RUNTIME_CONFIDENCE_POLICY: Final = ConfidencePolicy(
    name="calibrated_runtime_v2_2026_04",
    profiles=_build_profiles(
        table_exact=0.92,
        table_code=0.88,
        table_section=0.80,
        text_code=0.74,
        text_exact=0.68,
        text_section=0.66,
        ocr_exact=0.56,
        ocr_code=0.60,
        ocr_section=0.58,
        table_keyword=0.60,
        text_keyword=0.56,
        derived=0.35,
        approximation=0.20,
        policy_override=0.95,
    ),
    quality_bands=(
        QualityBand(minimum_quality=110, delta=0.05),
        QualityBand(minimum_quality=90, delta=0.03),
        QualityBand(minimum_quality=75, delta=0.00),
        QualityBand(minimum_quality=60, delta=-0.06),
        QualityBand(minimum_quality=None, delta=-0.10),
    ),
    structural_bonus_signals=STRUCTURAL_BONUS_SIGNALS,
    structural_bonus_delta=0.02,
    guardrail_penalty_delta=-0.10,
    conflict_penalty_step=-0.05,
    conflict_penalty_cap=-0.15,
    strong_direct_threshold=0.7,
)


RUNTIME_CONFIDENCE_POLICY: Final = CALIBRATED_RUNTIME_CONFIDENCE_POLICY


__all__ = [
    "BASELINE_RUNTIME_CONFIDENCE_POLICY",
    "CALIBRATED_RUNTIME_CONFIDENCE_POLICY",
    "ConfidenceBreakdown",
    "ConfidencePolicy",
    "EvidenceProfile",
    "POSTPROCESS_GUARDRAIL",
    "ProfileKey",
    "QualityBand",
    "RUNTIME_CONFIDENCE_POLICY",
    "STRUCTURAL_BONUS_SIGNALS",
    "build_policy_decision_log",
]
