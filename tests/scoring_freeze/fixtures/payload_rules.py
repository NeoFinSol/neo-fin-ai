from collections import defaultdict

from tests.scoring_freeze.fixtures.models import PayloadClass, PayloadFieldRule

PAYLOAD_FIELD_RULES: tuple[PayloadFieldRule, ...] = (
    PayloadFieldRule(
        payload_rule_set_id="prs-with-annualization",
        payload_class="with_annualization",
        field_path="score",
        field_type="float",
        required=True,
        nullable=False,
        omission_rule="not_applicable",
        semantic_meaning="final_score",
        machine_consumed=True,
        freeze_severity="hard-frozen",
    ),
    PayloadFieldRule(
        payload_rule_set_id="prs-with-annualization",
        payload_class="with_annualization",
        field_path="methodology.period_basis",
        field_type="str",
        required=True,
        nullable=False,
        omission_rule="not_applicable",
        semantic_meaning="annualization_basis",
        machine_consumed=True,
        freeze_severity="hard-frozen",
    ),
    PayloadFieldRule(
        payload_rule_set_id="prs-degraded-valid",
        payload_class="degraded_valid",
        field_path="score",
        field_type="float",
        required=True,
        nullable=False,
        omission_rule="not_applicable",
        semantic_meaning="degraded_score",
        machine_consumed=True,
        freeze_severity="hard-frozen",
    ),
    PayloadFieldRule(
        payload_rule_set_id="prs-degraded-valid",
        payload_class="degraded_valid",
        field_path="normalized_scores",
        field_type="dict",
        required=True,
        nullable=False,
        omission_rule="not_applicable",
        semantic_meaning="normalized_score_map",
        machine_consumed=True,
        freeze_severity="hard-frozen",
    ),
    PayloadFieldRule(
        payload_rule_set_id="prs-empty-optional-sections",
        payload_class="empty_optional_sections",
        field_path="factors",
        field_type="list",
        required=True,
        nullable=False,
        omission_rule="empty_container",
        semantic_meaning="factor_collection",
        machine_consumed=True,
        freeze_severity="soft-frozen",
    ),
    PayloadFieldRule(
        payload_rule_set_id="prs-empty-optional-sections",
        payload_class="empty_optional_sections",
        field_path="methodology.guardrails",
        field_type="list",
        required=True,
        nullable=False,
        omission_rule="empty_container",
        semantic_meaning="guardrail_metadata",
        machine_consumed=True,
        freeze_severity="hard-frozen",
    ),
)

PAYLOAD_RULE_SET_INDEX: dict[str, tuple[PayloadFieldRule, ...]] = {}
for rule in PAYLOAD_FIELD_RULES:
    PAYLOAD_RULE_SET_INDEX.setdefault(rule.payload_rule_set_id, tuple())
    PAYLOAD_RULE_SET_INDEX[rule.payload_rule_set_id] += (rule,)

_rules_by_class: dict[PayloadClass, list[PayloadFieldRule]] = defaultdict(list)
for rule in PAYLOAD_FIELD_RULES:
    _rules_by_class[rule.payload_class].append(rule)

PAYLOAD_RULES_BY_CLASS: dict[PayloadClass, tuple[PayloadFieldRule, ...]] = {
    payload_class: tuple(items) for payload_class, items in _rules_by_class.items()
}
