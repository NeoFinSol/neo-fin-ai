# Scoring Freeze Payload Matrix

Derived from typed registries.

| payload_rule_set_id | payload_class | field_path | field_type | required | nullable | omission_rule |
| --- | --- | --- | --- | --- | --- | --- |
| prs-degraded-valid | degraded_valid | normalized_scores | dict | True | False | not_applicable |
| prs-degraded-valid | degraded_valid | score | float | True | False | not_applicable |
| prs-empty-optional-sections | empty_optional_sections | factors | list | True | False | empty_container |
| prs-empty-optional-sections | empty_optional_sections | methodology.guardrails | list | True | False | empty_container |
| prs-with-annualization | with_annualization | methodology.period_basis | str | True | False | not_applicable |
| prs-with-annualization | with_annualization | score | float | True | False | not_applicable |
