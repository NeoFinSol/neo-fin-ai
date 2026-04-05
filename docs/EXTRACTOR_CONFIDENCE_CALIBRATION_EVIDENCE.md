# Extractor Confidence Calibration Evidence Pack

- Baseline policy: `baseline_runtime_v2`
- Candidate policy: `calibrated_runtime_v2_2026_04`
- Total decisions: `9`
- Reviewed threshold: `0.50`
- Decision surface counts: `threshold=5`, `winner=2`, `merge=2`

## Operational Metrics

| Policy | Accuracy | False Accepts | False Rejects | Survivors | Boundary Density | ECE | Brier |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| baseline_runtime_v2 | 0.667 | 2 | 0 | 5 | 0.333 | 0.317 | 0.315 |
| calibrated_runtime_v2_2026_04 | 1.000 | 0 | 0 | 3 | 0.333 | 0.414 | 0.278 |

## Decision Quality Guardrails

- Survivor count shift: `-2`
- Acceptance rate shift: `-0.286`
- Mean confidence shift: `+0.022`
- Boundary density shift: `+0.000`

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
| 0.40 | 0.667 | 2 | 0 | 5 | 0.714 |
| 0.45 | 0.667 | 2 | 0 | 5 | 0.714 |
| 0.50 | 0.667 | 2 | 0 | 5 | 0.714 |
| 0.55 | 0.778 | 1 | 1 | 3 | 0.429 |
| 0.60 | 0.778 | 1 | 1 | 3 | 0.429 |

### `calibrated_runtime_v2_2026_04`

| Threshold | Accuracy | False Accepts | False Rejects | Survivors | Acceptance Rate |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 0.40 | 0.667 | 2 | 0 | 5 | 0.714 |
| 0.45 | 0.667 | 2 | 0 | 5 | 0.714 |
| 0.50 | 1.000 | 0 | 0 | 3 | 0.429 |
| 0.55 | 0.889 | 0 | 1 | 2 | 0.286 |
| 0.60 | 0.889 | 0 | 1 | 2 | 0.286 |

## Notable Case Diffs

- `weak_text_keyword_should_not_survive` (threshold): `survive:text` -> `absent` (correct `False` -> `True`)
- `weak_ocr_exact_should_not_survive` (threshold): `survive:ocr` -> `absent` (correct `False` -> `True`)
- `llm_replaces_weak_text_keyword_fallback` (merge): `fallback` -> `llm` (correct `False` -> `True`)

## Shadow Consumer Diffs

- `shadow_relaxed_consumer` accuracy=1.000, survivors=3, false_accepts=0, false_rejects=0
