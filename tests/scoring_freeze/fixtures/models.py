from dataclasses import dataclass
from typing import Any, Literal, Mapping

BoundaryKind = Literal["document", "precomputed"]
FreezeDomain = Literal[
    "annualization", "guardrails", "payload", "regression", "invariant"
]
PayloadClass = Literal[
    "full_success",
    "with_annualization",
    "with_exclusions",
    "degraded_valid",
    "invalid_or_suppressed_factor",
    "empty_optional_sections",
    "refused_payload",
]
ClassificationCategory = Literal[
    "CANONICAL_EXISTING_BEHAVIOR",
    "KNOWN_BUG_TO_PRESERVE_TEMPORARILY",
    "BUG_TO_FIX_BEFORE_FREEZE",
    "NON_CONTRACTUAL_PRESENTATION_DETAIL",
]
FreezeSeverity = Literal["hard-frozen", "soft-frozen", "informational"]
OmissionRule = Literal["absent", "null", "empty_container", "not_applicable"]
InvariantGroup = Literal[
    "deterministic",
    "anti_coupling",
    "machine_contract",
    "data_binding",
    "payload_typing",
    "equivalence_preparation",
]
ResultKind = Literal["payload", "structured_refusal", "fixture_error"]


@dataclass(frozen=True)
class DocumentInputBundle:
    input_bundle_id: str
    metrics: Mapping[str, Any]
    filename: str | None
    text: str | None
    extraction_metadata: Mapping[str, Any] | None
    profile: str | None


@dataclass(frozen=True)
class PrecomputedInputBundle:
    input_bundle_id: str
    metrics: Mapping[str, Any]
    ratios_ru: Mapping[str, Any]
    ratios_en: Mapping[str, Any]
    methodology: Mapping[str, Any]
    extraction_metadata: Mapping[str, Any] | None


@dataclass(frozen=True)
class ScoringFreezeCase:
    case_id: str
    boundary_kind: BoundaryKind
    domain: FreezeDomain
    input_bundle_id: str
    primary_payload_class: PayloadClass
    secondary_traits: frozenset[str]
    classification_id: str
    payload_rule_set_id: str
    inventory_entry_id: str
    expectation_id: str
    invariant_seed_ids: tuple[str, ...]


@dataclass(frozen=True)
class ClassificationDecision:
    classification_id: str
    case_id: str
    boundary_kind: BoundaryKind
    observed_behavior_summary: str
    ambiguity_reason: str
    classification: ClassificationCategory
    rationale: str
    freeze_action: str
    wave5_implication: str


@dataclass(frozen=True)
class PayloadFieldRule:
    payload_rule_set_id: str
    payload_class: PayloadClass
    field_path: str
    field_type: str
    required: bool
    nullable: bool
    omission_rule: OmissionRule
    semantic_meaning: str
    machine_consumed: bool
    freeze_severity: FreezeSeverity


@dataclass(frozen=True)
class FreezeInventoryEntry:
    inventory_entry_id: str
    boundary_kind: BoundaryKind
    source_symbol: str
    branch_kind: Literal[
        "annualization",
        "guardrail",
        "payload_builder",
        "methodology",
        "data_binding",
        "ambiguity",
    ]
    observable_outcomes: tuple[str, ...]
    ambiguity_reason: str | None


@dataclass(frozen=True)
class InvariantSeed:
    seed_id: str
    group: InvariantGroup
    case_id: str
    mutation_kind: str
    expected_checks: tuple[str, ...]


@dataclass(frozen=True)
class BoundaryExpectation:
    expectation_id: str
    expected_status_fields: Mapping[str, Any]
    expected_reason_fields: Mapping[str, Any]
    expected_numeric_fields: Mapping[str, float | int | None]
    expected_annualization_fields: Mapping[str, Any]
    expected_guardrail_fields: Mapping[str, Any]
    soft_presentation_fields: Mapping[str, Any]


@dataclass(frozen=True)
class BoundaryExecutionResult:
    case_id: str
    boundary_kind: BoundaryKind
    result_kind: ResultKind
    payload: Mapping[str, Any] | None
    exception_type: str | None
    exception_message: str | None


@dataclass(frozen=True)
class PayloadClassResolution:
    case_id: str
    primary_payload_class: PayloadClass
    secondary_traits: frozenset[str]
