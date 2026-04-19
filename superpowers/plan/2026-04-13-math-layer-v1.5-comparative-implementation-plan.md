Math Layer v1.5 Comparative — Implementation Plan
Suggested path: superpowers/plan/2026-04-13-math-layer-v1.5-comparative-implementation-plan.md

Summary
v1.5 реализует только canonical comparative foundation и runtime-enable только для roa, roe, asset_turnover в multi-period path.
Публичный контракт не меняется: ни API shape, ни frontend interfaces, ни новые public metric ids.
MathEngine остаётся single-period executor. Вся period/comparability semantics появляется до него в одном math-owned entrypoint.
Precondition: если Confirmed Debt Remediation Wave ещё не влита в базовую ветку, она должна быть merged first; v1.5 не должен смешивать comparative work с незавершённым debt cleanup.
Key Changes
Ввести один internal math entrypoint:
run_comparative_math(periods: Sequence[ComparativePeriodInput]) -> list[ComparativeMathResult]
run_comparative_math(...) работает на already basis-normalized metric bags и не владеет annualization policy.
Annualization остаётся upstream concern.
Upstream обязан передавать correct execution-basis inputs.
Comparative lane не должен повторно annualize или угадывать basis.
ComparativePeriodInput должен включать минимум:
period_label: str
metrics: dict[str, Any]
extraction_metadata: dict[str, Any] | None
ComparativeMathResult должен включать:
period_label
derived_metrics
period_ref: PeriodRef | None
comparability_state
comparability_flags
PeriodLinks должен быть immutable value object с nullability contract:
prior_comparable_link: PeriodRef | None
opening_balance_link: PeriodRef | None
отсутствие link выражается через None; incomparability выражается через state/flags, не через sentinel/fake ids.
Canonical linkage может использовать internal chronological ordering, но public response ordering остаётся под контролем существующей orchestration/compatibility logic.
Duplicate period detection — period-set concern и owned by canonical comparative lane, не single-label parser.
Implementation Changes
Canonical model and parser
Создать src/analysis/math/periods.py как узкий модуль vocabulary/value objects:
PeriodClass: FY, Q1, Q2, Q3, Q4, H1, NINE_MONTHS, LTM
ComparabilityState
ComparabilityFlag
RawPeriodParseResult
PeriodRef
PeriodLinks
Parser responsibilities:
парсит single label
не детектит duplicates
не строит set-level linkage
Runtime support в v1.5:
strict comparative linkage разрешён только для FY, Q1, H1
Q2, Q3, Q4, NINE_MONTHS, LTM могут парситься для compatibility ordering/canonical dating, но не runtime-enable strict metrics
Зафиксировать отдельно:
Q4 может парситься для ordering compatibility и canonical dating, но в v1.5 MUST NOT считаться эквивалентом FY для strict comparative linkage или opening-balance derivation, если период явно не source-labeled как FY
partially_comparable остаётся semantic vocabulary, но для strict metrics operationally non-permissive и ведёт к fail-closed
Wave-level assumption:
для Q1 и H1 opening balance берётся как prior FY closing balance, потому что текущий input contract не содержит richer opening snapshot
Centralize one source of truth:
STRICT_AVERAGE_BALANCE_METRICS = frozenset({"roa", "roe", "asset_turnover"})
Comparative lane and reason vocabulary
Создать src/analysis/math/comparative_reasons.py с фиксированным initial vocabulary:
ambiguous_period_label
unsupported_period_class
missing_prior_period
missing_opening_balance
incompatible_period_class
partially_comparable_context
inconsistent_units
inconsistent_currency
average_balance_context_missing
Создать src/analysis/math/comparative.py как public home lane, но internal logic держать разложенной по focused helpers:
set-level normalization
linkage resolution
prepared input construction
status mapping
comparative.py может быть public facade, но не должен стать dense coordinator blob.
Prepared inputs
Comparative prepared inputs должны быть period-scoped, не bespoke per metric.
Naming pattern фиксированный:
opening_<base_metric_key>
closing_<base_metric_key>
average_<base_metric_key>
Для v1.5 реально готовятся:
opening_total_assets, closing_total_assets, average_total_assets
opening_equity, closing_equity, average_equity
Новые average_* / opening_* / closing_* inputs используют тот же internal raw-input structure, который уже принимается normalize_inputs() и превращается в ordinary TypedInputs.
Никакого special-case parsing в MathEngine добавлять нельзя.
Если average-balance context недостаточен:
synthetic average_* input получает value=None и deterministic reason_codes
strict metric fail-closed
частичной деградации до single-period formula не допускается
Registry and engine
В src/analysis/math/registry.py заменить placeholders только для:
roa = net_profit / average_total_assets
roe = net_profit / average_equity
asset_turnover = revenue / average_total_assets
Для них зафиксировать:
averaging_policy = AVERAGE_BALANCE
denominator_policy = STRICT_POSITIVE
suppression_policy = NEVER
Остальные future comparative metrics не трогать.
MathEngine не получает:
label parsing
linkage lookup
duplicate handling
annualization policy
reinterpretation of links
Scoring boundary
Не вводить новый weak boundary dict[str, Any] без типизации.
В src/analysis/scoring.py создать внутренний typed result contract, выровненный с текущим return shape calculate_score_with_context():
ratios_ru
ratios_en
raw_score
score_payload
methodology
Новый helper:
calculate_score_from_precomputed_ratios(...) -> ScoreComputationResult
calculate_score_with_context() становится compatibility wrapper:
resolve methodology
annualize
calculate ratios
delegate в calculate_score_from_precomputed_ratios()
Multi-period path:
resolve methodology upstream
annualize upstream
pass basis-normalized bags into comparative lane
score from precomputed ratios without reconstructing comparative semantics
Tasks / orchestration
process_multi_analysis() сохраняется как outer orchestrator, но меняется на flow:
extraction-only per period
methodology resolution + annualization per successful period
one call into run_comparative_math(...)
scoring from comparative-derived ratios
response assembly
tasks.py orchestrates phase boundaries only; it must not manually call parser/linker/preparer/engine step-by-step.
_process_single_period() разрезать на extraction-only helper; scoring вынести на session-level post-pass.
Single-period path не прогонять через synthetic one-period comparative wrapper.
parse_period_label() и sort_periods_chronologically() оставить как compatibility surface, но перевести на canonical parser under the hood.
Test Plan
Новые тесты:
tests/test_math_periods.py
parse YYYY, Q1..Q4/YYYY, H1/YYYY
Q4 != FY
internal ordering compatibility
tests/test_math_comparative.py
distinct prior_comparable_link vs opening_balance_link
duplicate labels handled by lane, not parser
Q1/H1 -> prior FY opening policy
unsupported classes fail-closed for strict metrics
partially_comparable non-permissive
Обновить:
tests/test_math_engine.py
roa/roe/asset_turnover valid only with average inputs
no fallback to single-period end values
tests/test_math_projection_bridge.py
newly enabled metrics project values when valid, None otherwise
tests/test_ratios.py
single-period path keeps strict metrics fail-closed
tests/test_scoring.py
annualization stays upstream
new typed score helper aligns with existing score context shape
tests/test_tasks.py
multi-period orchestration now extract-first / comparative-second / score-third
progress/cancellation unchanged
tests/test_multi_analysis_router.py
public response shape unchanged
sorted output preserved
no new fields
Mandatory scenarios:
FY + prior FY enables strict metrics
Q1 + prior FY enables strict metrics
H1 + prior FY enables strict metrics
one-period session keeps strict metrics None
Q4 parsed but not treated as FY
duplicate labels do not 422 the request but strict metrics fail-closed on affected periods
Acceptance And Review Gates
No parallel semantic source outside canonical math layer
No hidden annualization inside comparative lane
No hidden single-period fallback for strict metrics
No Q4 -> FY equivalence shortcut
No sentinel/fake links; absent links are None
No public contract expansion
periods.py remains narrow
comparative.py remains internally decomposed
STRICT_AVERAGE_BALANCE_METRICS exists centrally and is reused, not duplicated
Assumptions And Tolerated Technical Debt
v1.5 intentionally does not implement optional shadow metrics
metrics: dict[str, Any] остаётся допустимым временным internal boundary, потому что соответствует текущему shape и не открывает отдельную DTO-wave
extraction_metadata: dict[str, Any] | None остаётся допустимым weak boundary; цель волны — comparative foundation, а не metadata redesign
Currency/unit inconsistency handling is fail-closed only when current metadata already exposes a safety signal
Annualization remains upstream policy, not comparative-lane policy
Internal chronological ordering may differ from output order; public ordering remains compatibility-controlled
comparative.py остаётся главным execution-risk и должен быть удержан как public facade с внутренне декомпозированными focused helpers, а не как 300–500 line coordinator