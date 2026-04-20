from tests.scoring_freeze.fixtures.inventory_registry import AMBIGUITY_INDEX
from tests.scoring_freeze.fixtures.models import ClassificationDecision


CLASSIFICATION_DECISIONS: tuple[ClassificationDecision, ...] = (
    ClassificationDecision(
        classification_id="cls-period-marker-annualization",
        case_id="freeze-case-period-marker-annualization",
        boundary_kind="document",
        observed_behavior_summary=(
            "Boundary annualization decision is currently inferred from textual "
            "Q1/H1 markers plus revenue-presence gate."
        ),
        ambiguity_reason=(
            "Inferred long-term intent may move to typed period semantics, but "
            "current boundary behavior is deterministic and consumer-visible."
        ),
        classification="CANONICAL_EXISTING_BEHAVIOR",
        rationale=(
            "Behavior is stable on canonical boundary and does not require "
            "immediate semantic correction inside Wave 4.5."
        ),
        freeze_action=(
            "Include in admissible canonical baseline with hard behavioral "
            "freezing on boundary outputs."
        ),
        wave5_implication=(
            "Any future migration to typed period semantics must be explicit "
            "semantic change after equivalence baseline is captured."
        ),
    ),
    ClassificationDecision(
        classification_id="cls-ru-label-semantic-coupling",
        case_id="freeze-case-ru-label-semantic-coupling",
        boundary_kind="precomputed",
        observed_behavior_summary=(
            "Core scoring data binding currently depends on RU-labeled ratio "
            "keys in weights and benchmarks."
        ),
        ambiguity_reason=(
            "Wave guidance requires reducing localization-key semantic coupling; "
            "current wiring is a decomposition-risk hotspot."
        ),
        classification="BUG_TO_FIX_BEFORE_FREEZE",
        rationale=(
            "This is a spec-tension behavior with high Wave 5 refactor risk and "
            "must be handled through blocker workflow before canonical inclusion."
        ),
        freeze_action=(
            "Keep as blocker case outside admissible canonical baseline until "
            "formal blocker workflow is completed."
        ),
        wave5_implication=(
            "Wave 5 cannot treat RU labels as canonical semantic identity without "
            "explicitly resolving blocker semantics."
        ),
    ),
    ClassificationDecision(
        classification_id="cls-anomaly-helper-boundary-impact",
        case_id="freeze-case-anomaly-helper-boundary-impact",
        boundary_kind="precomputed",
        observed_behavior_summary=(
            "Helper-level anomaly filtering excludes ratio values by returning "
            "None before weighted scoring."
        ),
        ambiguity_reason=(
            "Behavior originates in helper internals but materially influences "
            "boundary score/payload outcomes."
        ),
        classification="CANONICAL_EXISTING_BEHAVIOR",
        rationale=(
            "Scope requires classifying helper influence as observed "
            "boundary-impacting behavior, not immediate refactor target."
        ),
        freeze_action=(
            "Include in admissible canonical baseline as boundary-impacting "
            "behavior with helper listed only as context."
        ),
        wave5_implication=(
            "Wave 5 extraction must preserve anomaly gating effect on boundary "
            "results even if helper placement changes."
        ),
    ),
    ClassificationDecision(
        classification_id="cls-empty-factors-preserved-quirk",
        case_id="freeze-case-empty-factors-preserved-quirk",
        boundary_kind="precomputed",
        observed_behavior_summary=(
            "Payload may emit empty factors while retaining score and methodology "
            "fields."
        ),
        ambiguity_reason=(
            "Behavior is consumer-visible and potentially undesirable, but stable "
            "and non-fatal for contract parsing."
        ),
        classification="KNOWN_BUG_TO_PRESERVE_TEMPORARILY",
        rationale=(
            "Treat as temporary preserved quirk to avoid mixing behavior changes "
            "with freeze/decomposition preparation."
        ),
        freeze_action=(
            "Preserve in admissible baseline and mark explicitly as temporary "
            "bug for follow-up corrective wave."
        ),
        wave5_implication=(
            "Wave 5 must preserve this quirk unless a dedicated semantic-fix "
            "decision is approved."
        ),
    ),
)

CLASSIFICATION_INDEX: dict[str, ClassificationDecision] = {
    item.classification_id: item for item in CLASSIFICATION_DECISIONS
}

CLASSIFICATION_BY_CASE_ID: dict[str, ClassificationDecision] = {
    item.case_id: item for item in CLASSIFICATION_DECISIONS
}

CLASSIFICATION_TO_AMBIGUITY_ID: dict[str, str] = {
    "cls-period-marker-annualization": "amb-observed-vs-intent-period-markers",
    "cls-ru-label-semantic-coupling": "amb-observed-vs-spec-label-coupling",
    "cls-anomaly-helper-boundary-impact": "amb-helper-only-normalization-policy",
    "cls-empty-factors-preserved-quirk": "amb-consumer-visible-empty-factors",
}

UNLINKED_CLASSIFICATION_IDS: tuple[str, ...] = tuple(
    item.classification_id
    for item in CLASSIFICATION_DECISIONS
    if item.classification_id not in CLASSIFICATION_TO_AMBIGUITY_ID
)

BLOCKER_CASES: tuple[str, ...] = tuple(
    item.case_id
    for item in CLASSIFICATION_DECISIONS
    if item.classification == "BUG_TO_FIX_BEFORE_FREEZE"
)

PRESERVED_TEMPORARY_BUG_CASES: tuple[str, ...] = tuple(
    item.case_id
    for item in CLASSIFICATION_DECISIONS
    if item.classification == "KNOWN_BUG_TO_PRESERVE_TEMPORARILY"
)

PRESENTATION_ONLY_DETAIL_CASES: tuple[str, ...] = tuple(
    item.case_id
    for item in CLASSIFICATION_DECISIONS
    if item.classification == "NON_CONTRACTUAL_PRESENTATION_DETAIL"
)

ADMISSIBLE_CANONICAL_BASELINE_CASES: tuple[str, ...] = tuple(
    item.case_id
    for item in CLASSIFICATION_DECISIONS
    if item.classification != "BUG_TO_FIX_BEFORE_FREEZE"
)

UNCLASSIFIED_AMBIGUITY_IDS: tuple[str, ...] = tuple(
    ambiguity_id
    for ambiguity_id in AMBIGUITY_INDEX
    if ambiguity_id not in set(CLASSIFICATION_TO_AMBIGUITY_ID.values())
)

if UNCLASSIFIED_AMBIGUITY_IDS:
    missing = ", ".join(UNCLASSIFIED_AMBIGUITY_IDS)
    raise RuntimeError(f"Unclassified ambiguities detected: {missing}")

if UNLINKED_CLASSIFICATION_IDS:
    missing = ", ".join(UNLINKED_CLASSIFICATION_IDS)
    raise RuntimeError(f"Classification without ambiguity linkage: {missing}")
