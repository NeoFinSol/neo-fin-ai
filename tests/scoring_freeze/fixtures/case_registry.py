from tests.scoring_freeze.fixtures.classification_registry import (
    ADMISSIBLE_CANONICAL_BASELINE_CASES,
)
from tests.scoring_freeze.fixtures.classification_registry import (
    BLOCKER_CASES as BLOCKER_CASE_IDS,
)
from tests.scoring_freeze.fixtures.classification_registry import CLASSIFICATION_INDEX
from tests.scoring_freeze.fixtures.expectations import EXPECTATION_INDEX
from tests.scoring_freeze.fixtures.input_bundles import INPUT_BUNDLE_INDEX
from tests.scoring_freeze.fixtures.invariant_registry import INVARIANT_INDEX
from tests.scoring_freeze.fixtures.inventory_registry import INVENTORY_INDEX
from tests.scoring_freeze.fixtures.models import FreezeDomain, ScoringFreezeCase
from tests.scoring_freeze.fixtures.payload_rules import PAYLOAD_RULE_SET_INDEX

ALL_FREEZE_CASES: tuple[ScoringFreezeCase, ...] = (
    ScoringFreezeCase(
        case_id="freeze-case-period-marker-annualization",
        boundary_kind="document",
        domain="annualization",
        input_bundle_id="bundle-doc-period-marker",
        primary_payload_class="with_annualization",
        secondary_traits=frozenset({"annualized"}),
        classification_id="cls-period-marker-annualization",
        payload_rule_set_id="prs-with-annualization",
        inventory_entry_id="inv-annualization-q1-h1-markers",
        expectation_id="exp-period-marker-annualization",
        invariant_seed_ids=(
            "seed-period-marker-deterministic",
            "seed-period-marker-anti-coupling",
        ),
    ),
    ScoringFreezeCase(
        case_id="freeze-case-ru-label-semantic-coupling",
        boundary_kind="precomputed",
        domain="regression",
        input_bundle_id="bundle-pre-ru-label-coupling",
        primary_payload_class="degraded_valid",
        secondary_traits=frozenset({"profile_binding_sensitive"}),
        classification_id="cls-ru-label-semantic-coupling",
        payload_rule_set_id="prs-degraded-valid",
        inventory_entry_id="inv-ambiguity-ru-label-coupling",
        expectation_id="exp-ru-label-semantic-coupling",
        invariant_seed_ids=("seed-ru-label-coupling-data-binding",),
    ),
    ScoringFreezeCase(
        case_id="freeze-case-anomaly-helper-boundary-impact",
        boundary_kind="precomputed",
        domain="guardrails",
        input_bundle_id="bundle-pre-anomaly-helper-impact",
        primary_payload_class="degraded_valid",
        secondary_traits=frozenset({"anomaly_filtered"}),
        classification_id="cls-anomaly-helper-boundary-impact",
        payload_rule_set_id="prs-degraded-valid",
        inventory_entry_id="inv-ambiguity-helper-anomaly-impact",
        expectation_id="exp-anomaly-helper-boundary-impact",
        invariant_seed_ids=(
            "seed-anomaly-impact-machine-contract",
            "seed-anomaly-impact-data-binding",
        ),
    ),
    ScoringFreezeCase(
        case_id="freeze-case-empty-factors-preserved-quirk",
        boundary_kind="precomputed",
        domain="payload",
        input_bundle_id="bundle-pre-empty-factors-quirk",
        primary_payload_class="empty_optional_sections",
        secondary_traits=frozenset({"has_empty_optional_sections"}),
        classification_id="cls-empty-factors-preserved-quirk",
        payload_rule_set_id="prs-empty-optional-sections",
        inventory_entry_id="inv-ambiguity-empty-factors-quirk",
        expectation_id="exp-empty-factors-preserved-quirk",
        invariant_seed_ids=(
            "seed-empty-factors-payload-typing",
            "seed-empty-factors-equivalence-preparation",
        ),
    ),
)

CASE_INDEX: dict[str, ScoringFreezeCase] = {
    case.case_id: case for case in ALL_FREEZE_CASES
}

CANONICAL_FREEZE_CASES: tuple[ScoringFreezeCase, ...] = tuple(
    CASE_INDEX[case_id] for case_id in ADMISSIBLE_CANONICAL_BASELINE_CASES
)

BLOCKER_CASES: tuple[ScoringFreezeCase, ...] = tuple(
    CASE_INDEX[case_id] for case_id in BLOCKER_CASE_IDS
)

CASES_BY_DOMAIN: dict[FreezeDomain, tuple[ScoringFreezeCase, ...]] = {
    "annualization": tuple(
        case for case in ALL_FREEZE_CASES if case.domain == "annualization"
    ),
    "guardrails": tuple(
        case for case in ALL_FREEZE_CASES if case.domain == "guardrails"
    ),
    "payload": tuple(case for case in ALL_FREEZE_CASES if case.domain == "payload"),
    "regression": tuple(
        case for case in ALL_FREEZE_CASES if case.domain == "regression"
    ),
    "invariant": tuple(case for case in ALL_FREEZE_CASES if case.domain == "invariant"),
}

CASES_BY_BOUNDARY: dict[str, tuple[ScoringFreezeCase, ...]] = {
    "document": tuple(
        case for case in ALL_FREEZE_CASES if case.boundary_kind == "document"
    ),
    "precomputed": tuple(
        case for case in ALL_FREEZE_CASES if case.boundary_kind == "precomputed"
    ),
}

CASES_WITHOUT_INPUT_BUNDLE: tuple[str, ...] = tuple(
    case.case_id
    for case in ALL_FREEZE_CASES
    if case.input_bundle_id not in INPUT_BUNDLE_INDEX
)
CASES_WITHOUT_CLASSIFICATION: tuple[str, ...] = tuple(
    case.case_id
    for case in ALL_FREEZE_CASES
    if case.classification_id not in CLASSIFICATION_INDEX
)
CASES_WITHOUT_PAYLOAD_RULE_SET: tuple[str, ...] = tuple(
    case.case_id
    for case in ALL_FREEZE_CASES
    if case.payload_rule_set_id not in PAYLOAD_RULE_SET_INDEX
)
CASES_WITHOUT_INVENTORY_LINKAGE: tuple[str, ...] = tuple(
    case.case_id
    for case in ALL_FREEZE_CASES
    if case.inventory_entry_id not in INVENTORY_INDEX
)
CASES_WITHOUT_EXPECTATION: tuple[str, ...] = tuple(
    case.case_id
    for case in ALL_FREEZE_CASES
    if case.expectation_id not in EXPECTATION_INDEX
)
CASES_WITHOUT_INVARIANT_SEEDS: tuple[str, ...] = tuple(
    case.case_id for case in ALL_FREEZE_CASES if not case.invariant_seed_ids
)
CASES_WITH_INVALID_INVARIANT_LINKAGE: tuple[str, ...] = tuple(
    case.case_id
    for case in ALL_FREEZE_CASES
    if any(seed_id not in INVARIANT_INDEX for seed_id in case.invariant_seed_ids)
)
CASES_WITH_DUPLICATE_DOMAIN_ASSIGNMENT: tuple[str, ...] = tuple(
    case.case_id
    for case in ALL_FREEZE_CASES
    if sum(case in CASES_BY_DOMAIN[domain] for domain in CASES_BY_DOMAIN) != 1
)

ORPHAN_CASES: tuple[str, ...] = tuple(
    dict.fromkeys(
        CASES_WITHOUT_INPUT_BUNDLE
        + CASES_WITHOUT_CLASSIFICATION
        + CASES_WITHOUT_PAYLOAD_RULE_SET
        + CASES_WITHOUT_INVENTORY_LINKAGE
        + CASES_WITHOUT_EXPECTATION
        + CASES_WITHOUT_INVARIANT_SEEDS
        + CASES_WITH_INVALID_INVARIANT_LINKAGE
        + CASES_WITH_DUPLICATE_DOMAIN_ASSIGNMENT
    )
)

if ORPHAN_CASES:
    missing = ", ".join(ORPHAN_CASES)
    raise RuntimeError(f"Orphan or invalid case linkage detected: {missing}")
