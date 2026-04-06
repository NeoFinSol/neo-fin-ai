# Extractor Confidence Calibration Evidence Pack

- Baseline policy: `baseline_runtime_v2`
- Candidate policy: `calibrated_runtime_v2_2026_04`
- Suites: `fast, gated`
- Reviewed threshold: `0.50`

## Aggregate Operational Metrics

| Policy | Accuracy | False Accepts | False Rejects | Survivors | Boundary Density | ECE | Brier |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| baseline_runtime_v2 | 0.656 | 2 | 1 | 23 | 0.438 | 0.086 | 0.215 |
| calibrated_runtime_v2_2026_04 | 0.625 | 0 | 8 | 14 | 0.406 | 0.144 | 0.188 |

## Per-Suite Summary

| Suite | Baseline Accuracy | Candidate Accuracy | Baseline Survivors | Candidate Survivors |
| --- | ---: | ---: | ---: | ---: |
| fast | 0.750 | 1.000 | 5 | 4 |
| gated | 0.625 | 0.500 | 18 | 10 |

## Coverage Audit

- `fast` missing required surfaces: none
- `fast` under-anchored required surfaces: none
- `gated` missing required surfaces: none
- `gated` under-anchored required surfaces: none
- `all` missing required surfaces: none
- `all` under-anchored required surfaces: none

## Source Mismatch Audit

- Baseline advisory mismatches: gated_magnit_2023_ifrs_boundary_anchor::equity, gated_magnit_2023_ifrs_boundary_anchor::net_profit, gated_magnit_2023_ifrs_boundary_anchor::revenue, gated_magnit_2023_ifrs_boundary_anchor::total_assets
- Baseline critical mismatches: gated_magnit_2025_h1_debt_components_anchor::long_term_borrowings, gated_magnit_2025_h1_debt_components_anchor::long_term_lease_liabilities, gated_magnit_2025_h1_debt_components_anchor::short_term_borrowings, gated_magnit_2025_h1_debt_components_anchor::short_term_lease_liabilities
- Candidate advisory mismatches: none
- Candidate critical mismatches: gated_magnit_2025_h1_debt_components_anchor::long_term_borrowings, gated_magnit_2025_h1_debt_components_anchor::long_term_lease_liabilities, gated_magnit_2025_h1_debt_components_anchor::short_term_borrowings, gated_magnit_2025_h1_debt_components_anchor::short_term_lease_liabilities

## Policy Diffs

- `profile:text/code_match/direct`: `0.72` -> `0.74`
- `profile:text/exact/direct`: `0.66` -> `0.68`
- `profile:text/section_match/direct`: `0.64` -> `0.66`
- `profile:ocr/exact/direct`: `0.70` -> `0.56`
- `profile:ocr/code_match/direct`: `0.68` -> `0.60`
- `profile:ocr/section_match/direct`: `0.64` -> `0.58`
- `profile:table/keyword_match/direct`: `0.62` -> `0.60`
- `profile:text/keyword_match/direct`: `0.58` -> `0.56`
- `quality_band>=110`: `0.04` -> `0.05`
- `quality_band>=90`: `0.02` -> `0.03`
- `quality_band>=60`: `-0.04` -> `-0.06`
- `quality_band<fallback`: `-0.08` -> `-0.10`
- `structural_bonus_delta`: `0.03` -> `0.02`
- `guardrail_penalty_delta`: `-0.08` -> `-0.10`
- `conflict_penalty_step`: `-0.04` -> `-0.05`
- `conflict_penalty_cap`: `-0.12` -> `-0.15`

## Trust-Order Invariant Checks

- `PASS` trust_order:('table', 'exact', 'direct')>('table', 'code_match', 'direct'): baseline=1, candidate=1, left_rank=90, right_rank=80
- `PASS` trust_order:('table', 'code_match', 'direct')>('table', 'section_match', 'direct'): baseline=1, candidate=1, left_rank=80, right_rank=70
- `PASS` trust_order:('table', 'section_match', 'direct')>('text', 'code_match', 'direct'): baseline=1, candidate=1, left_rank=70, right_rank=60
- `PASS` trust_order:('text', 'code_match', 'direct')>('ocr', 'exact', 'direct'): baseline=1, candidate=1, left_rank=60, right_rank=55
- `PASS` trust_order:('ocr', 'exact', 'direct')>('ocr', 'code_match', 'direct'): baseline=1, candidate=1, left_rank=55, right_rank=50
- `PASS` trust_order:('ocr', 'code_match', 'direct')>('ocr', 'section_match', 'direct'): baseline=1, candidate=1, left_rank=50, right_rank=45
- `PASS` trust_order:('ocr', 'section_match', 'direct')>('table', 'keyword_match', 'direct'): baseline=1, candidate=1, left_rank=45, right_rank=40
- `PASS` trust_order:('table', 'keyword_match', 'direct')>('text', 'keyword_match', 'direct'): baseline=1, candidate=1, left_rank=40, right_rank=30
- `PASS` trust_order:('text', 'keyword_match', 'direct')>('derived', 'not_applicable', 'derived'): baseline=1, candidate=1, left_rank=30, right_rank=20
- `PASS` trust_order:('derived', 'not_applicable', 'derived')>('table', 'exact', 'approximation'): baseline=1, candidate=1, left_rank=20, right_rank=10
- `PASS` policy_override_confidence_unchanged: baseline=0.95, candidate=0.95
- `PASS` strong_direct_threshold_unchanged: baseline=0.70, candidate=0.70

## Threshold Sweep

### `baseline_runtime_v2`

| Threshold | Accuracy | False Accepts | False Rejects | Survivors | Acceptance Rate |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 0.40 | 0.656 | 2 | 1 | 23 | 0.885 |
| 0.45 | 0.656 | 2 | 1 | 23 | 0.885 |
| 0.50 | 0.656 | 2 | 1 | 23 | 0.885 |
| 0.55 | 0.469 | 1 | 12 | 11 | 0.423 |
| 0.60 | 0.469 | 1 | 16 | 7 | 0.269 |

### `calibrated_runtime_v2_2026_04`

| Threshold | Accuracy | False Accepts | False Rejects | Survivors | Acceptance Rate |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 0.40 | 0.656 | 2 | 1 | 23 | 0.885 |
| 0.45 | 0.656 | 2 | 1 | 23 | 0.885 |
| 0.50 | 0.625 | 0 | 8 | 14 | 0.538 |
| 0.55 | 0.500 | 0 | 12 | 10 | 0.385 |
| 0.60 | 0.469 | 0 | 17 | 5 | 0.192 |

## Notable Case Diffs

### `fast`

- `fast_llm_replacement` (merge): `fallback|text|authoritative_override=False` -> `llm|text|authoritative_override=False|reason_code=llm_extraction` (correct `False` -> `True`)
- `fast_weak_text_keyword_absent` (threshold): `survive:text` -> `absent` (correct `False` -> `True`)

### `gated`

- `gated_cloudflare_expected_absent_anchor` (threshold): `survive:ocr` -> `absent` (correct `False` -> `True`)
- `gated_cloudflare_merge_anchor` (merge): `fallback|text|authoritative_override=False` -> `llm|text|authoritative_override=False|reason_code=llm_extraction` (correct `False` -> `True`)
- `gated_cloudflare_threshold_survival::cash_and_equivalents` (winner): `survive:text` -> `absent` (correct `True` -> `False`)
- `gated_corvel_parse_anchor::revenue` (winner): `survive:text` -> `absent` (correct `True` -> `False`)
- `gated_magnit_2023_ifrs_boundary_anchor::equity` (winner): `survive:text` -> `absent` (correct `False` -> `False`)
- `gated_magnit_2023_ifrs_boundary_anchor::net_profit` (winner): `survive:text` -> `absent` (correct `True` -> `False`)
- `gated_magnit_2023_ifrs_boundary_anchor::revenue` (winner): `survive:text` -> `absent` (correct `False` -> `False`)
- `gated_magnit_2023_ifrs_boundary_anchor::total_assets` (winner): `survive:text` -> `absent` (correct `True` -> `False`)
- `gated_magnit_q1_scanned_inventory_blind_spot::inventory` (winner): `survive:text` -> `absent` (correct `True` -> `False`)

## Shadow Consumer Diffs

- `shadow_relaxed_consumer` accuracy=0.625, survivors=14, false_accepts=0, false_rejects=8
