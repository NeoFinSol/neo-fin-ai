# Scoring Freeze Inventory

Derived from typed registries.

## Inventory Entries
- `inv-ambiguity-period-marker-intent`: ambiguity / document / `src.analysis.scoring._detect_period_basis`
- `inv-annualization-q1-h1-markers`: annualization / document / `src.analysis.scoring._detect_period_basis`
- `inv-annualization-revenue-override`: annualization / document / `src.analysis.scoring._detect_period_basis`
- `inv-annualization-key-scope`: annualization / document / `src.analysis.scoring.annualize_metrics_for_period`
- `inv-ambiguity-helper-anomaly-impact`: ambiguity / precomputed / `src.analysis.scoring._normalize_ratio`
- `inv-ambiguity-ru-label-coupling`: ambiguity / precomputed / `src.analysis.scoring.build_score_payload`
- `inv-ambiguity-empty-factors-quirk`: ambiguity / precomputed / `src.analysis.scoring.build_score_payload`
- `inv-data-binding-anomaly-limits`: data_binding / precomputed / `src.analysis.scoring._normalize_ratio`
- `inv-data-binding-profile-benchmark`: data_binding / precomputed / `src.analysis.scoring.calculate_integral_score`
- `inv-data-binding-weights`: data_binding / precomputed / `src.analysis.scoring.calculate_integral_score`
- `inv-guardrails-cap-order`: guardrail / precomputed / `src.analysis.scoring.apply_data_quality_guardrails`
- `inv-guardrails-methodology-merge`: guardrail / precomputed / `src.analysis.scoring.apply_data_quality_guardrails`
- `inv-data-binding-peer-context`: methodology / precomputed / `src.analysis.scoring._apply_profile_peer_context`
- `inv-data-binding-leverage-basis`: methodology / precomputed / `src.analysis.scoring._resolve_leverage_basis`
- `inv-payload-shape-core-keys`: payload_builder / precomputed / `src.analysis.scoring.build_score_payload`
- `inv-payload-normalized-score-domain`: payload_builder / precomputed / `src.analysis.scoring.build_score_payload`
- `inv-payload-factor-construction`: payload_builder / precomputed / `src.analysis.scoring.build_score_payload`

## Ambiguities
- `amb-observed-vs-intent-period-markers`: Intent may be typed period semantics, but observed behavior remains text-marker driven.
- `amb-observed-vs-spec-label-coupling`: Wave specs discourage labels/localization as primary semantic source; current behavior still binds to RU labels.
- `amb-helper-only-normalization-policy`: Behavior is helper-local but materially affects boundary score composition; not a standalone public contract.
- `amb-consumer-visible-empty-factors`: Consumer interpretation of empty factors is visible and can drift during refactor.

## Data Binding
- `binding-weights`: `WEIGHTS`
- `binding-benchmarks-by-profile`: `BENCHMARKS_BY_PROFILE`
- `binding-anomaly-limits`: `_ANOMALY_LIMITS`
- `binding-profile-peer-context`: `_PROFILE_PEER_CONTEXT`
- `binding-profile-leverage-basis`: `_PROFILE_LEVERAGE_BASIS`
- `binding-annualization-factors`: `_ANNUALIZATION_FACTORS`
- `binding-annualized-metric-keys`: `_ANNUALIZED_METRIC_KEYS`
