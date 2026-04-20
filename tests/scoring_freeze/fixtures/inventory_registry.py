from dataclasses import dataclass
from typing import Literal

from tests.scoring_freeze.fixtures.models import FreezeInventoryEntry

AmbiguityKind = Literal[
    "observed_vs_inferred_intent",
    "observed_vs_spec",
    "helper_only_behavior",
    "consumer_visible_quirk",
]


@dataclass(frozen=True)
class AmbiguityEntry:
    ambiguity_id: str
    kind: AmbiguityKind
    source_symbol: str
    observed_behavior: str
    ambiguity_summary: str
    freeze_scope_note: str


@dataclass(frozen=True)
class DataBindingEntry:
    binding_id: str
    config_symbol: str
    consumed_by: tuple[str, ...]
    observed_binding: str
    freeze_relevance: str


CANONICAL_PUBLIC_ENTRYPOINTS: tuple[str, ...] = (
    "src.analysis.scoring.calculate_score_with_context",
    "src.analysis.scoring.calculate_score_from_precomputed_ratios",
)

CANONICAL_EXECUTION_PATHS: tuple[tuple[str, str], ...] = (
    (
        "document",
        "calculate_score_with_context -> resolve_scoring_methodology -> "
        "annualize_metrics_for_period -> calculate_ratios/translate_ratios -> "
        "calculate_score_from_precomputed_ratios -> build_score_payload -> "
        "apply_data_quality_guardrails",
    ),
    (
        "precomputed",
        "calculate_score_from_precomputed_ratios -> "
        "_apply_scoring_methodology_adjustments -> calculate_integral_score -> "
        "build_score_payload -> apply_data_quality_guardrails",
    ),
)

PAYLOAD_PRODUCING_BOUNDARY: str = (
    "score_payload returned from calculate_score_from_precomputed_ratios "
    "(directly or through calculate_score_with_context)"
)

FREEZE_RELEVANT_HELPERS: tuple[str, ...] = (
    "src.analysis.scoring.resolve_scoring_methodology",
    "src.analysis.scoring.annualize_metrics_for_period",
    "src.analysis.scoring.build_score_payload",
    "src.analysis.scoring.apply_data_quality_guardrails",
    "src.analysis.scoring._apply_scoring_methodology_adjustments",
    "src.analysis.scoring._normalize_methodology",
    "src.analysis.scoring._normalize_ratio",
)

FREEZE_INVENTORY: tuple[FreezeInventoryEntry, ...] = (
    FreezeInventoryEntry(
        inventory_entry_id="inv-annualization-q1-h1-markers",
        boundary_kind="document",
        source_symbol="src.analysis.scoring._detect_period_basis",
        branch_kind="annualization",
        observable_outcomes=(
            "Q1/H1 marker detection in normalized document context assigns "
            "period_basis annualized_q1/annualized_h1.",
            "Annualized decision changes downstream ratio/scoring path.",
        ),
        ambiguity_reason=None,
    ),
    FreezeInventoryEntry(
        inventory_entry_id="inv-annualization-revenue-override",
        boundary_kind="document",
        source_symbol="src.analysis.scoring._detect_period_basis",
        branch_kind="annualization",
        observable_outcomes=(
            "If revenue is missing, period markers are ignored and period_basis "
            "is forced to reported.",
            "Marker-based annualization can be suppressed by metric availability.",
        ),
        ambiguity_reason=None,
    ),
    FreezeInventoryEntry(
        inventory_entry_id="inv-annualization-key-scope",
        boundary_kind="document",
        source_symbol="src.analysis.scoring.annualize_metrics_for_period",
        branch_kind="annualization",
        observable_outcomes=(
            "Only keys from _ANNUALIZED_METRIC_KEYS are multiplied by "
            "_ANNUALIZATION_FACTORS.",
            "Non-listed metric keys remain unadjusted.",
        ),
        ambiguity_reason=None,
    ),
    FreezeInventoryEntry(
        inventory_entry_id="inv-guardrails-cap-order",
        boundary_kind="precomputed",
        source_symbol="src.analysis.scoring.apply_data_quality_guardrails",
        branch_kind="guardrail",
        observable_outcomes=(
            "Guardrails apply in strict priority: missing core -> missing "
            "supporting -> low confidence.",
            "First matching guardrail defines capped score and risk_level.",
        ),
        ambiguity_reason=None,
    ),
    FreezeInventoryEntry(
        inventory_entry_id="inv-guardrails-methodology-merge",
        boundary_kind="precomputed",
        source_symbol="src.analysis.scoring.apply_data_quality_guardrails",
        branch_kind="guardrail",
        observable_outcomes=(
            "Applied guardrails are merged into methodology.guardrails with "
            "duplicate-safe string accumulation.",
            "Methodology metadata reflects guardrail activation at boundary.",
        ),
        ambiguity_reason=None,
    ),
    FreezeInventoryEntry(
        inventory_entry_id="inv-payload-shape-core-keys",
        boundary_kind="precomputed",
        source_symbol="src.analysis.scoring.build_score_payload",
        branch_kind="payload_builder",
        observable_outcomes=(
            "Payload includes score, risk_level, confidence_score, factors, "
            "normalized_scores, methodology.",
            "Defines consumer-visible scoring payload top-level shape.",
        ),
        ambiguity_reason=None,
    ),
    FreezeInventoryEntry(
        inventory_entry_id="inv-payload-normalized-score-domain",
        boundary_kind="precomputed",
        source_symbol="src.analysis.scoring.build_score_payload",
        branch_kind="payload_builder",
        observable_outcomes=(
            "normalized_scores domain is pre-seeded from RATIO_KEY_MAP values "
            "and filled only for scored ratio names.",
            "Missing/non-scored factors remain None in normalized_scores.",
        ),
        ambiguity_reason=None,
    ),
    FreezeInventoryEntry(
        inventory_entry_id="inv-payload-factor-construction",
        boundary_kind="precomputed",
        source_symbol="src.analysis.scoring.build_score_payload",
        branch_kind="payload_builder",
        observable_outcomes=(
            "Factor entries are constructed from normalized detail values, "
            "friendly names, benchmark-aware descriptions, and impact bands.",
            "Factor content remains consumer-visible boundary behavior.",
        ),
        ambiguity_reason=None,
    ),
    FreezeInventoryEntry(
        inventory_entry_id="inv-data-binding-profile-benchmark",
        boundary_kind="precomputed",
        source_symbol="src.analysis.scoring.calculate_integral_score",
        branch_kind="data_binding",
        observable_outcomes=(
            "Resolved benchmark_profile selects BENCHMARKS_BY_PROFILE branch for "
            "ratio normalization.",
            "Profile wiring affects normalized details and final score.",
        ),
        ambiguity_reason=None,
    ),
    FreezeInventoryEntry(
        inventory_entry_id="inv-data-binding-weights",
        boundary_kind="precomputed",
        source_symbol="src.analysis.scoring.calculate_integral_score",
        branch_kind="data_binding",
        observable_outcomes=(
            "WEIGHTS drive weighted sum and confidence_score from the subset of "
            "ratios with valid normalized values.",
            "Weight wiring controls score contribution and confidence.",
        ),
        ambiguity_reason=None,
    ),
    FreezeInventoryEntry(
        inventory_entry_id="inv-data-binding-anomaly-limits",
        boundary_kind="precomputed",
        source_symbol="src.analysis.scoring._normalize_ratio",
        branch_kind="data_binding",
        observable_outcomes=(
            "_ANOMALY_LIMITS block out-of-range ratios from normalization by "
            "returning None.",
            "Excluded ratios alter factor inclusion and score composition.",
        ),
        ambiguity_reason=None,
    ),
    FreezeInventoryEntry(
        inventory_entry_id="inv-data-binding-peer-context",
        boundary_kind="precomputed",
        source_symbol="src.analysis.scoring._apply_profile_peer_context",
        branch_kind="methodology",
        observable_outcomes=(
            "_PROFILE_PEER_CONTEXT fills methodology.peer_context for active "
            "profile.",
            "Peer context is emitted in methodology payload metadata.",
        ),
        ambiguity_reason=None,
    ),
    FreezeInventoryEntry(
        inventory_entry_id="inv-data-binding-leverage-basis",
        boundary_kind="precomputed",
        source_symbol="src.analysis.scoring._resolve_leverage_basis",
        branch_kind="methodology",
        observable_outcomes=(
            "_PROFILE_LEVERAGE_BASIS selects total-liabilities vs debt-only "
            "leverage basis when debt-only ratio exists.",
            "Leverage basis rewires selected ratio fields and methodology.",
        ),
        ambiguity_reason=None,
    ),
    FreezeInventoryEntry(
        inventory_entry_id="inv-ambiguity-period-marker-intent",
        boundary_kind="document",
        source_symbol="src.analysis.scoring._detect_period_basis",
        branch_kind="ambiguity",
        observable_outcomes=(
            "Period-basis detection remains text-marker driven on boundary.",
        ),
        ambiguity_reason="Potential future typed-period intent mismatch.",
    ),
    FreezeInventoryEntry(
        inventory_entry_id="inv-ambiguity-ru-label-coupling",
        boundary_kind="precomputed",
        source_symbol="src.analysis.scoring.build_score_payload",
        branch_kind="ambiguity",
        observable_outcomes=(
            "RU-label keyed scoring data is part of current boundary behavior.",
        ),
        ambiguity_reason="Spec tension with semantic-key-first target.",
    ),
    FreezeInventoryEntry(
        inventory_entry_id="inv-ambiguity-helper-anomaly-impact",
        boundary_kind="precomputed",
        source_symbol="src.analysis.scoring._normalize_ratio",
        branch_kind="ambiguity",
        observable_outcomes=(
            "Helper anomaly gating materially affects boundary score outcome.",
        ),
        ambiguity_reason="Helper-origin behavior impacts public boundary outputs.",
    ),
    FreezeInventoryEntry(
        inventory_entry_id="inv-ambiguity-empty-factors-quirk",
        boundary_kind="precomputed",
        source_symbol="src.analysis.scoring.build_score_payload",
        branch_kind="ambiguity",
        observable_outcomes=(
            "Empty factors can coexist with populated score/methodology fields.",
        ),
        ambiguity_reason="Consumer-visible quirk with potential refactor drift risk.",
    ),
)

AMBIGUITY_LIST: tuple[AmbiguityEntry, ...] = (
    AmbiguityEntry(
        ambiguity_id="amb-observed-vs-intent-period-markers",
        kind="observed_vs_inferred_intent",
        source_symbol="src.analysis.scoring._detect_period_basis",
        observed_behavior=(
            "Period basis relies on free-text markers in filename/text context."
        ),
        ambiguity_summary=(
            "Intent may be typed period semantics, but observed behavior remains "
            "text-marker driven."
        ),
        freeze_scope_note=(
            "Freeze as observed boundary behavior; classification deferred to "
            "Iteration 2."
        ),
    ),
    AmbiguityEntry(
        ambiguity_id="amb-observed-vs-spec-label-coupling",
        kind="observed_vs_spec",
        source_symbol="src.analysis.scoring.build_score_payload",
        observed_behavior=(
            "WEIGHTS and BENCHMARKS are keyed by Russian ratio labels."
        ),
        ambiguity_summary=(
            "Wave specs discourage labels/localization as primary semantic "
            "source; current behavior still binds to RU labels."
        ),
        freeze_scope_note=(
            "Track as freeze-relevant ambiguity for explicit classification "
            "before decomposition."
        ),
    ),
    AmbiguityEntry(
        ambiguity_id="amb-helper-only-normalization-policy",
        kind="helper_only_behavior",
        source_symbol="src.analysis.scoring._normalize_ratio",
        observed_behavior=(
            "Helper blocks anomalous values and returns None before weighting."
        ),
        ambiguity_summary=(
            "Behavior is helper-local but materially affects boundary score "
            "composition; not a standalone public contract."
        ),
        freeze_scope_note=(
            "Keep helper listed as freeze-relevant support behavior only."
        ),
    ),
    AmbiguityEntry(
        ambiguity_id="amb-consumer-visible-empty-factors",
        kind="consumer_visible_quirk",
        source_symbol="src.analysis.scoring.build_score_payload",
        observed_behavior=(
            "factors list may be empty while score/methodology fields still "
            "exist."
        ),
        ambiguity_summary=(
            "Consumer interpretation of empty factors is visible and can drift "
            "during refactor."
        ),
        freeze_scope_note=(
            "Include in payload freeze inventory as explicit quirk."
        ),
    ),
)

FROZEN_DATA_BINDING_MAP: tuple[DataBindingEntry, ...] = (
    DataBindingEntry(
        binding_id="binding-weights",
        config_symbol="WEIGHTS",
        consumed_by=(
            "src.analysis.scoring.calculate_integral_score",
            "src.analysis.scoring.build_score_payload",
        ),
        observed_binding=(
            "Defines weighted scoring dimensions and implicitly expected ratio "
            "name set for details/payload factors."
        ),
        freeze_relevance="Hard freeze target for scoring contribution wiring.",
    ),
    DataBindingEntry(
        binding_id="binding-benchmarks-by-profile",
        config_symbol="BENCHMARKS_BY_PROFILE",
        consumed_by=(
            "src.analysis.scoring._resolve_scoring_profile",
            "src.analysis.scoring.calculate_integral_score",
            "src.analysis.scoring.build_score_payload",
        ),
        observed_binding=(
            "Selected profile drives normalization targets and factor "
            "description benchmarks."
        ),
        freeze_relevance="Hard freeze target for profile-to-benchmark wiring.",
    ),
    DataBindingEntry(
        binding_id="binding-anomaly-limits",
        config_symbol="_ANOMALY_LIMITS",
        consumed_by=("src.analysis.scoring._normalize_ratio",),
        observed_binding=(
            "Out-of-range ratio values are excluded from scoring through None "
            "normalization path."
        ),
        freeze_relevance="Hard freeze target for anomaly guardrail wiring.",
    ),
    DataBindingEntry(
        binding_id="binding-profile-peer-context",
        config_symbol="_PROFILE_PEER_CONTEXT",
        consumed_by=(
            "src.analysis.scoring.resolve_scoring_methodology",
            "src.analysis.scoring._apply_profile_peer_context",
        ),
        observed_binding=(
            "Profile-specific peer context is attached into methodology payload "
            "metadata."
        ),
        freeze_relevance="Soft freeze target (methodology metadata contract).",
    ),
    DataBindingEntry(
        binding_id="binding-profile-leverage-basis",
        config_symbol="_PROFILE_LEVERAGE_BASIS",
        consumed_by=(
            "src.analysis.scoring._resolve_leverage_basis",
            "src.analysis.scoring._apply_leverage_to_ratios",
        ),
        observed_binding=(
            "Profile mapping determines leverage basis and selected leverage "
            "value in ratios/methodology."
        ),
        freeze_relevance="Hard freeze target for leverage basis selection wiring.",
    ),
    DataBindingEntry(
        binding_id="binding-annualization-factors",
        config_symbol="_ANNUALIZATION_FACTORS",
        consumed_by=("src.analysis.scoring.annualize_metrics_for_period",),
        observed_binding=(
            "Period basis maps to numeric annualization multiplier (Q1/H1)."
        ),
        freeze_relevance="Hard freeze target for annualization multiplier wiring.",
    ),
    DataBindingEntry(
        binding_id="binding-annualized-metric-keys",
        config_symbol="_ANNUALIZED_METRIC_KEYS",
        consumed_by=("src.analysis.scoring.annualize_metrics_for_period",),
        observed_binding=(
            "Only declared metric keys are annualized; remaining metrics remain "
            "reported values."
        ),
        freeze_relevance="Hard freeze target for annualization scope wiring.",
    ),
)

INVENTORY_INDEX: dict[str, FreezeInventoryEntry] = {
    entry.inventory_entry_id: entry for entry in FREEZE_INVENTORY
}
AMBIGUITY_INDEX: dict[str, AmbiguityEntry] = {
    entry.ambiguity_id: entry for entry in AMBIGUITY_LIST
}
DATA_BINDING_INDEX: dict[str, DataBindingEntry] = {
    entry.binding_id: entry for entry in FROZEN_DATA_BINDING_MAP
}
