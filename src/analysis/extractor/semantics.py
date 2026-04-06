from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Iterable

from .confidence_policy import (
    BASELINE_RUNTIME_CONFIDENCE_POLICY,
    CALIBRATED_RUNTIME_CONFIDENCE_POLICY,
    RUNTIME_CONFIDENCE_POLICY,
    STRUCTURAL_BONUS_SIGNALS,
    ConfidencePolicy,
    EvidenceProfile,
    build_policy_decision_log,
)
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
REASON_GUARDRAIL_CURRENT_ASSETS_CANDIDATE_LT_COMPONENT_DROPPED: Final = (
    "guardrail_current_assets_candidate_lt_component_dropped"
)
REASON_GUARDRAIL_CURRENT_ASSETS_CANDIDATE_LT_COMPONENT_REPLACED: Final = (
    "guardrail_current_assets_candidate_lt_component_replaced"
)
REASON_SANITY_PNL_CONFLICT_DROP_REVENUE: Final = "sanity_pnl_conflict_drop_revenue"
REASON_SANITY_PNL_CONFLICT_DROP_NET_PROFIT: Final = (
    "sanity_pnl_conflict_drop_net_profit"
)
REASON_SANITY_PNL_REPLACED_REVENUE_WITH_CODE: Final = (
    "sanity_pnl_replaced_revenue_with_code"
)
REASON_SANITY_PNL_REPLACED_NET_PROFIT_WITH_CODE: Final = (
    "sanity_pnl_replaced_net_profit_with_code"
)

FLAG_COMPAT_NORMALIZED_FROM_V1: Final = "compat:normalized_from_v1"
FLAG_POSTPROCESS_GUARDRAIL_ADJUSTED: Final = "pp:guardrail_adjusted"

EVENT_ANNOTATED: Final = "ANNOTATED"
EVENT_REPLACED: Final = "REPLACED"
EVENT_DROPPED: Final = "DROPPED"
EVENT_INVALIDATED: Final = "INVALIDATED"

ProfileKey = tuple[str, str, str]


@dataclass(frozen=True, slots=True)
class ReasonDefinition:
    category: str
    final_state_eligible: bool
    event_action: str
    public_reason_priority: int


@dataclass(frozen=True, slots=True)
class SemanticsDecisionLog:
    metric_key: str
    profile_key: ProfileKey
    baseline_confidence: float
    quality_delta: float
    structural_bonus: float
    conflict_penalty: float
    guardrail_penalty: float
    final_confidence: float
    postprocess_state: str
    authoritative_override: bool
    reason_code: str | None
    signal_flags: list[str]
    candidate_quality: int | None


@dataclass(frozen=True, slots=True)
class GuardrailEvent:
    metric_key: str
    stage: str
    action: str
    reason_code: str
    before_value: float | None
    after_value: float | None
    before_profile_key: ProfileKey | None
    after_profile_key: ProfileKey | None


@dataclass(frozen=True, slots=True)
class ExtractionDebugTrace:
    metadata: dict[str, ExtractionMetadata]
    decision_logs: dict[str, SemanticsDecisionLog]
    guardrail_events: list[GuardrailEvent]


SEMANTIC_SIGNAL_FLAGS: Final[frozenset[str]] = frozenset(
    {
        FLAG_POSTPROCESS_GUARDRAIL_ADJUSTED,
    }
)
ACTIVE_CONFIDENCE_POLICY: Final[ConfidencePolicy] = RUNTIME_CONFIDENCE_POLICY
EVIDENCE_PROFILES: Final[dict[ProfileKey, EvidenceProfile]] = (
    ACTIVE_CONFIDENCE_POLICY.profiles
)

REASON_REGISTRY: Final[dict[str, ReasonDefinition]] = {
    REASON_ISSUER_REPO_OVERRIDE: ReasonDefinition(
        category="policy",
        final_state_eligible=True,
        event_action=EVENT_ANNOTATED,
        public_reason_priority=500,
    ),
    REASON_LLM_EXTRACTION: ReasonDefinition(
        category="llm",
        final_state_eligible=True,
        event_action=EVENT_ANNOTATED,
        public_reason_priority=120,
    ),
    REASON_GROSS_PROFIT_TO_EBITDA_APPROXIMATION: ReasonDefinition(
        category="approximation",
        final_state_eligible=True,
        event_action=EVENT_ANNOTATED,
        public_reason_priority=110,
    ),
    REASON_LEGACY_TABLE_PARTIAL_UNRESOLVED: ReasonDefinition(
        category="compat",
        final_state_eligible=True,
        event_action=EVENT_ANNOTATED,
        public_reason_priority=20,
    ),
    REASON_LEGACY_TEXT_REGEX_UNRESOLVED: ReasonDefinition(
        category="compat",
        final_state_eligible=True,
        event_action=EVENT_ANNOTATED,
        public_reason_priority=20,
    ),
    REASON_GUARDRAIL_CURRENT_ASSETS_GT_TOTAL_ASSETS: ReasonDefinition(
        category="guardrail",
        final_state_eligible=True,
        event_action=EVENT_INVALIDATED,
        public_reason_priority=400,
    ),
    REASON_GUARDRAIL_LIABILITIES_GT_TOTAL_ASSETS: ReasonDefinition(
        category="guardrail",
        final_state_eligible=True,
        event_action=EVENT_INVALIDATED,
        public_reason_priority=400,
    ),
    REASON_GUARDRAIL_EQUITY_GT_TOTAL_ASSETS: ReasonDefinition(
        category="guardrail",
        final_state_eligible=True,
        event_action=EVENT_INVALIDATED,
        public_reason_priority=400,
    ),
    REASON_GUARDRAIL_SHORT_TERM_GT_TOTAL_ASSETS: ReasonDefinition(
        category="guardrail",
        final_state_eligible=True,
        event_action=EVENT_INVALIDATED,
        public_reason_priority=400,
    ),
    REASON_GUARDRAIL_COMPONENT_GT_CURRENT_ASSETS: ReasonDefinition(
        category="guardrail",
        final_state_eligible=True,
        event_action=EVENT_INVALIDATED,
        public_reason_priority=400,
    ),
    REASON_GUARDRAIL_SHORT_TERM_GT_LIABILITIES: ReasonDefinition(
        category="guardrail",
        final_state_eligible=True,
        event_action=EVENT_INVALIDATED,
        public_reason_priority=400,
    ),
    REASON_GUARDRAIL_CURRENT_ASSETS_CANDIDATE_LT_COMPONENT_DROPPED: ReasonDefinition(
        category="guardrail",
        final_state_eligible=False,
        event_action=EVENT_DROPPED,
        public_reason_priority=0,
    ),
    REASON_GUARDRAIL_CURRENT_ASSETS_CANDIDATE_LT_COMPONENT_REPLACED: ReasonDefinition(
        category="guardrail",
        final_state_eligible=True,
        event_action=EVENT_REPLACED,
        public_reason_priority=200,
    ),
    REASON_SANITY_PNL_CONFLICT_DROP_REVENUE: ReasonDefinition(
        category="sanity",
        final_state_eligible=False,
        event_action=EVENT_DROPPED,
        public_reason_priority=0,
    ),
    REASON_SANITY_PNL_CONFLICT_DROP_NET_PROFIT: ReasonDefinition(
        category="sanity",
        final_state_eligible=False,
        event_action=EVENT_DROPPED,
        public_reason_priority=0,
    ),
    REASON_SANITY_PNL_REPLACED_REVENUE_WITH_CODE: ReasonDefinition(
        category="sanity",
        final_state_eligible=True,
        event_action=EVENT_REPLACED,
        public_reason_priority=300,
    ),
    REASON_SANITY_PNL_REPLACED_NET_PROFIT_WITH_CODE: ReasonDefinition(
        category="sanity",
        final_state_eligible=True,
        event_action=EVENT_REPLACED,
        public_reason_priority=300,
    ),
}


def get_profile(profile_key: ProfileKey) -> EvidenceProfile:
    return ACTIVE_CONFIDENCE_POLICY.get_profile(profile_key)


def compare_profile_trust(left: ProfileKey, right: ProfileKey) -> int:
    return ACTIVE_CONFIDENCE_POLICY.compare_profile_trust(left, right)


def get_reason_definition(reason_code: str) -> ReasonDefinition:
    try:
        return REASON_REGISTRY[reason_code]
    except KeyError as exc:
        raise ValueError(f"Unsupported extractor reason_code: {reason_code!r}") from exc


def select_preferred_reason_code(*reason_codes: str | None) -> str | None:
    best_reason: str | None = None
    best_priority = float("-inf")
    for reason_code in reason_codes:
        if not reason_code:
            continue
        definition = get_reason_definition(reason_code)
        if not definition.final_state_eligible:
            continue
        if definition.public_reason_priority > best_priority:
            best_reason = reason_code
            best_priority = definition.public_reason_priority
    return best_reason


def is_semantic_signal_flag(flag: str) -> bool:
    return flag in SEMANTIC_SIGNAL_FLAGS


def semantic_signal_delta(
    before_flags: Iterable[str],
    after_flags: Iterable[str],
) -> list[str]:
    before = set(before_flags)
    return [
        flag
        for flag in after_flags
        if flag not in before and is_semantic_signal_flag(flag)
    ]


def guardrail_events_for_metric(
    guardrail_events: Iterable[GuardrailEvent],
    metric_key: str,
) -> list[GuardrailEvent]:
    return [event for event in guardrail_events if event.metric_key == metric_key]


def quality_delta(candidate_quality: int | None) -> float:
    return ACTIVE_CONFIDENCE_POLICY.quality_delta(candidate_quality)


def structural_bonus(
    signal_flags: list[str] | tuple[str, ...] | frozenset[str]
) -> float:
    if any(
        flag in ACTIVE_CONFIDENCE_POLICY.structural_bonus_signals
        for flag in signal_flags
    ):
        return ACTIVE_CONFIDENCE_POLICY.structural_bonus_delta
    return 0.0


def conflict_penalty(conflict_count: int) -> float:
    return ACTIVE_CONFIDENCE_POLICY.conflict_penalty(conflict_count)


def guardrail_penalty(postprocess_state: str) -> float:
    return ACTIVE_CONFIDENCE_POLICY.guardrail_penalty(postprocess_state)


def calculate_confidence(
    profile_key: ProfileKey,
    *,
    candidate_quality: int | None,
    signal_flags: list[str] | tuple[str, ...] | frozenset[str],
    conflict_count: int,
    postprocess_state: str,
    confidence_policy: ConfidencePolicy | None = None,
) -> float:
    return build_decision_log(
        profile_key,
        metric_key="",
        candidate_quality=candidate_quality,
        signal_flags=signal_flags,
        conflict_count=conflict_count,
        postprocess_state=postprocess_state,
        authoritative_override=False,
        reason_code=None,
        confidence_policy=confidence_policy,
    ).final_confidence


def build_decision_log(
    profile_key: ProfileKey,
    *,
    metric_key: str = "",
    candidate_quality: int | None,
    signal_flags: list[str] | tuple[str, ...] | frozenset[str],
    conflict_count: int,
    postprocess_state: str,
    authoritative_override: bool,
    reason_code: str | None = None,
    confidence_policy: ConfidencePolicy | None = None,
) -> SemanticsDecisionLog:
    policy = confidence_policy or ACTIVE_CONFIDENCE_POLICY
    breakdown = build_policy_decision_log(
        policy,
        profile_key,
        metric_key=metric_key,
        candidate_quality=candidate_quality,
        signal_flags=signal_flags,
        conflict_count=conflict_count,
        postprocess_state=postprocess_state,
        authoritative_override=authoritative_override,
        reason_code=reason_code,
    )
    return SemanticsDecisionLog(
        metric_key=metric_key,
        profile_key=profile_key,
        baseline_confidence=breakdown.baseline_confidence,
        quality_delta=breakdown.quality_delta,
        structural_bonus=breakdown.structural_bonus,
        conflict_penalty=breakdown.conflict_penalty,
        guardrail_penalty=breakdown.guardrail_penalty,
        final_confidence=breakdown.final_confidence,
        postprocess_state=postprocess_state,
        authoritative_override=authoritative_override,
        reason_code=reason_code,
        signal_flags=list(signal_flags),
        candidate_quality=candidate_quality,
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
    return normalized.confidence >= ACTIVE_CONFIDENCE_POLICY.strong_direct_threshold


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


def format_metric_decision_trace(
    decision_log: SemanticsDecisionLog,
    guardrail_events: Iterable[GuardrailEvent],
) -> str:
    profile = "/".join(decision_log.profile_key)
    lines = [
        (
            f"{decision_log.metric_key}: profile={profile} "
            f"reason={decision_log.reason_code or 'none'} "
            f"postprocess={decision_log.postprocess_state} "
            f"override={decision_log.authoritative_override}"
        ),
        (
            "  "
            f"baseline={decision_log.baseline_confidence:.2f} "
            f"quality={decision_log.quality_delta:+.2f} "
            f"structural={decision_log.structural_bonus:+.2f} "
            f"conflict={decision_log.conflict_penalty:+.2f} "
            f"guardrail={decision_log.guardrail_penalty:+.2f} "
            f"final={decision_log.final_confidence:.2f}"
        ),
    ]
    for event in guardrail_events_for_metric(
        guardrail_events,
        decision_log.metric_key,
    ):
        before_profile = (
            "/".join(event.before_profile_key)
            if event.before_profile_key is not None
            else "none"
        )
        after_profile = (
            "/".join(event.after_profile_key)
            if event.after_profile_key is not None
            else "none"
        )
        lines.append(
            (
                f"  {event.action} stage={event.stage} reason={event.reason_code} "
                f"before={event.before_value} ({before_profile}) "
                f"after={event.after_value} ({after_profile})"
            )
        )
    return "\n".join(lines)


__all__ = [
    "EVIDENCE_PROFILES",
    "EVENT_ANNOTATED",
    "EVENT_DROPPED",
    "EVENT_INVALIDATED",
    "EVENT_REPLACED",
    "EvidenceProfile",
    "ExtractionDebugTrace",
    "FLAG_COMPAT_NORMALIZED_FROM_V1",
    "FLAG_POSTPROCESS_GUARDRAIL_ADJUSTED",
    "GuardrailEvent",
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
    "REASON_GUARDRAIL_CURRENT_ASSETS_CANDIDATE_LT_COMPONENT_DROPPED",
    "REASON_GUARDRAIL_CURRENT_ASSETS_CANDIDATE_LT_COMPONENT_REPLACED",
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
    "REASON_REGISTRY",
    "REASON_SANITY_PNL_CONFLICT_DROP_NET_PROFIT",
    "REASON_SANITY_PNL_CONFLICT_DROP_REVENUE",
    "REASON_SANITY_PNL_REPLACED_NET_PROFIT_WITH_CODE",
    "REASON_SANITY_PNL_REPLACED_REVENUE_WITH_CODE",
    "ReasonDefinition",
    "SEMANTIC_SIGNAL_FLAGS",
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
    "format_metric_decision_trace",
    "get_reason_definition",
    "get_profile",
    "guardrail_events_for_metric",
    "guardrail_penalty",
    "infer_profile_key_from_legacy_match",
    "is_authoritative_override",
    "is_replaceable_by_llm",
    "is_semantic_signal_flag",
    "is_strong_direct_evidence",
    "normalize_legacy_metadata",
    "quality_delta",
    "select_preferred_reason_code",
    "semantic_signal_delta",
    "structural_bonus",
    "survives_confidence_filter",
    "validate_public_metadata_state",
]
