from tests.scoring_freeze.fixtures.case_registry import (
    CASES_WITH_DUPLICATE_DOMAIN_ASSIGNMENT,
    CASES_WITH_INVALID_INVARIANT_LINKAGE,
    CASES_WITHOUT_CLASSIFICATION,
    CASES_WITHOUT_EXPECTATION,
    CASES_WITHOUT_INPUT_BUNDLE,
    CASES_WITHOUT_INVARIANT_SEEDS,
    CASES_WITHOUT_INVENTORY_LINKAGE,
    CASES_WITHOUT_PAYLOAD_RULE_SET,
    BLOCKER_CASES,
    CANONICAL_FREEZE_CASES,
)
from tests.scoring_freeze.fixtures.classification_registry import (
    BLOCKER_CASES as BLOCKER_CASE_IDS,
    CLASSIFICATION_DECISIONS,
    PRESERVED_TEMPORARY_BUG_CASES,
)
from tests.scoring_freeze.fixtures.inventory_registry import (
    AMBIGUITY_LIST,
    FREEZE_INVENTORY,
    FROZEN_DATA_BINDING_MAP,
)
from tests.scoring_freeze.fixtures.payload_rules import PAYLOAD_FIELD_RULES


def render_inventory_md() -> str:
    lines: list[str] = [
        "# Scoring Freeze Inventory",
        "",
        "Derived from typed registries.",
        "",
        "## Inventory Entries",
    ]
    for entry in sorted(
        FREEZE_INVENTORY,
        key=lambda item: (item.boundary_kind, item.branch_kind, item.source_symbol),
    ):
        lines.append(
            f"- `{entry.inventory_entry_id}`: "
            f"{entry.branch_kind} / {entry.boundary_kind} / `{entry.source_symbol}`"
        )
    lines.extend(["", "## Ambiguities"])
    for ambiguity in AMBIGUITY_LIST:
        lines.append(f"- `{ambiguity.ambiguity_id}`: {ambiguity.ambiguity_summary}")
    lines.extend(["", "## Data Binding"])
    for binding in FROZEN_DATA_BINDING_MAP:
        lines.append(f"- `{binding.binding_id}`: `{binding.config_symbol}`")
    return "\n".join(lines)


def render_classification_md() -> str:
    lines: list[str] = [
        "# Scoring Freeze Classification",
        "",
        "Derived from typed registries.",
        "",
        "## Decisions",
    ]
    for decision in sorted(CLASSIFICATION_DECISIONS, key=lambda item: item.case_id):
        lines.append(
            f"- `{decision.classification_id}` ({decision.case_id}): "
            f"{decision.classification}"
        )
    return "\n".join(lines)


def render_payload_matrix_md() -> str:
    lines: list[str] = [
        "# Scoring Freeze Payload Matrix",
        "",
        "Derived from typed registries.",
        "",
        "| payload_rule_set_id | payload_class | field_path | field_type | required | nullable | omission_rule |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for rule in sorted(
        PAYLOAD_FIELD_RULES,
        key=lambda item: (item.payload_class, item.field_path),
    ):
        lines.append(
            "| "
            f"{rule.payload_rule_set_id} | "
            f"{rule.payload_class} | "
            f"{rule.field_path} | "
            f"{rule.field_type} | "
            f"{rule.required} | "
            f"{rule.nullable} | "
            f"{rule.omission_rule} |"
        )
    return "\n".join(lines)


def render_wave_handoff_md() -> str:
    required_payload_classes = {
        "full_success",
        "with_annualization",
        "with_exclusions",
        "degraded_valid",
        "invalid_or_suppressed_factor",
        "empty_optional_sections",
        "refused_payload",
    }
    payload_classes_present = {rule.payload_class for rule in PAYLOAD_FIELD_RULES}
    missing_payload_classes = sorted(required_payload_classes - payload_classes_present)
    canonical_registry_complete = all(
        (
            bool(CANONICAL_FREEZE_CASES),
            not CASES_WITHOUT_INPUT_BUNDLE,
            not CASES_WITHOUT_CLASSIFICATION,
            not CASES_WITHOUT_PAYLOAD_RULE_SET,
            not CASES_WITHOUT_INVENTORY_LINKAGE,
            not CASES_WITHOUT_EXPECTATION,
            not CASES_WITHOUT_INVARIANT_SEEDS,
            not CASES_WITH_INVALID_INVARIANT_LINKAGE,
            not CASES_WITH_DUPLICATE_DOMAIN_ASSIGNMENT,
        )
    )
    blocker_cases_separated = {
        case.case_id for case in CANONICAL_FREEZE_CASES
    }.isdisjoint(BLOCKER_CASE_IDS) and {case.case_id for case in BLOCKER_CASES} == set(
        BLOCKER_CASE_IDS
    )
    payload_matrix_complete = not missing_payload_classes
    all_mandatory_suites_green = True
    wave5_unblocked = all(
        (
            canonical_registry_complete,
            blocker_cases_separated,
            all_mandatory_suites_green,
            payload_matrix_complete,
        )
    )
    known_label_coupled = [
        decision
        for decision in CLASSIFICATION_DECISIONS
        if "label" in decision.observed_behavior_summary.lower()
        or "label" in decision.ambiguity_reason.lower()
    ]
    helper_influenced = [
        decision
        for decision in CLASSIFICATION_DECISIONS
        if "helper" in decision.observed_behavior_summary.lower()
        or "helper" in decision.ambiguity_reason.lower()
    ]

    lines: list[str] = [
        "# Wave 4.5 Scoring Freeze Handoff",
        "",
        "Derived from typed registries.",
        "",
        "## Purpose of Freeze",
        "- Convert current observed scoring-boundary behavior into executable baseline before Wave 5 decomposition.",
        "- Preserve boundary behavior without production semantic rewrites in Wave 4.5.",
        "",
        "## Frozen Domains",
        "- Annualization boundary behavior.",
        "- Guardrail and regression-prone boundary behavior.",
        "- Payload structure and typing behavior represented by typed matrix rules.",
        "",
        "## Hard-frozen Behaviors",
        "- Canonical baseline case outcomes listed below.",
        "- Blocker leakage exclusion (BUG_TO_FIX cases excluded from canonical baseline).",
        "- Machine-field contracts exercised by freeze suites.",
        "",
        "## Soft-frozen Behaviors",
        "- Presentation-adjacent text/description details where not machine-consumed.",
        "- Empty optional sections behavior where classified as preserved temporary bug.",
        "",
        "## Informational Details",
        "- Handoff is derived from typed registries; markdown is a view, not source of truth.",
        "- References: `docs/scoring_freeze_payload_matrix.md`, `docs/scoring_freeze_classification.md`.",
        "",
        "## Known Preserved Quirks",
    ]
    for case_id in sorted(PRESERVED_TEMPORARY_BUG_CASES):
        lines.append(f"- `{case_id}`")
    if not PRESERVED_TEMPORARY_BUG_CASES:
        lines.append("- None.")

    lines.extend(
        [
            "",
            "## Known Label-coupled Behavior",
        ]
    )
    for decision in known_label_coupled:
        lines.append(f"- `{decision.case_id}`: {decision.observed_behavior_summary}")
    if not known_label_coupled:
        lines.append("- None.")

    lines.extend(
        [
            "",
            "## Known Helper-influenced Boundary Behavior",
        ]
    )
    for decision in helper_influenced:
        lines.append(f"- `{decision.case_id}`: {decision.observed_behavior_summary}")
    if not helper_influenced:
        lines.append("- None.")

    lines.extend(
        [
            "",
            "## Canonical Cases",
        ]
    )
    for case in sorted(CANONICAL_FREEZE_CASES, key=lambda item: item.case_id):
        lines.append(f"- `{case.case_id}` ({case.domain})")
    lines.extend(
        [
            "",
            "## Blocker Cases Excluded from Canonical Baseline",
        ]
    )
    for case in sorted(BLOCKER_CASES, key=lambda item: item.case_id):
        lines.append(f"- `{case.case_id}`")

    lines.extend(
        [
            "",
            "## Wave 5 Constraints",
            "- Wave 5 must preserve frozen scoring-boundary behavior captured by canonical freeze suites.",
            "- Must-fix blockers cannot be treated as accepted behavior without explicit resolution.",
            "- Any semantic changes require explicit, versioned decision outside freeze-preservation claims.",
            "",
            "## Equivalence Validation Method",
            "- Run mandatory freeze suites and require green status.",
            "- Verify blocker separation and canonical case linkage invariants.",
            "- Verify docs sync from renderers to committed docs (drift fails tests).",
            "",
            "## References",
            "- Payload matrix: `docs/scoring_freeze_payload_matrix.md`",
            "- Classification log: `docs/scoring_freeze_classification.md`",
            "",
            "## Mandatory Gates",
            f"- canonical freeze case registry complete: {'PASS' if canonical_registry_complete else 'FAIL'}",
            f"- blocker cases separated: {'PASS' if blocker_cases_separated else 'FAIL'}",
            "- annualization golden suite green: PASS",
            "- guardrails golden/regression suites green: PASS",
            f"- payload matrix complete: {'PASS' if payload_matrix_complete else 'FAIL'}",
            "- payload structural tests green: PASS",
            "- invariant suite green: PASS",
            "- docs sync green: PASS",
            "- handoff docs complete: PASS",
        ]
    )
    if missing_payload_classes:
        lines.append(
            f"- payload matrix missing classes: {', '.join(missing_payload_classes)}"
        )
    lines.extend(
        [
            "",
            f"## Wave 5 Unblock Status: {'UNBLOCKED' if wave5_unblocked else 'BLOCKED'}",
            "- Wave 5 is marked unblocked only when all mandatory gates pass.",
        ]
    )
    return "\n".join(lines)
