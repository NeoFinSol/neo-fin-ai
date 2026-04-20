# Tech debt backlog (Math Layer / analysis)

Записи из аудита Phase 5 (ValidityState ↔ outward reasons), **некритичные** пункты — без немедленного исправления в коде.

Сводка закрытия Wave 4 (код + тесты): [MATH_LAYER_V2_WAVE4_CLOSURE.md](MATH_LAYER_V2_WAVE4_CLOSURE.md).

## Wave 4 / документация

- **Нормативный Wave 4 spec в репозитории:** при появлении финального `math_layer_v2_wave4_spec.md` (или аналога) — свернуть комментарии в `emission_guard.py` / `reason_resolution.py` с документом и добавить ссылку из `AGENTS.md` или архитектурной заметки.
- **TD-026** (`.agent/tech_debt_backlog.md`): после Phase 8 — переименование `validate_wave3_contract` / `_WAVE3_`* literal scan в нейтральные имена и синхронизация старых wave3 spec, если появятся в дереве.

## Граница движка

- `**assert_engine_emission_contract`:** сейчас не вызывается из `engine.py`; валидатор `DerivedMetric` уже выполняет ту же проверку. Опционально: явный вызов в конце сборки метрики только для более читаемых stack trace — избыточно по поведению.

## Legacy / поверхности

- **REST/legacy:** `project_legacy_ratios` отдаёт только `float | None`; отдельные тесты «reason не утекает в legacy dict» не обязательны, пока контракт не меняется. При появлении API, отдающего полный `DerivedMetric`, добавить контрактные тесты на outward поля.

## Trace vs outward

- **Расширение:** при появлении API, отдающего полный `DerivedMetric` наружу, явно документировать, что авторитетные outward-поля — на модели; `trace["final_outward"]` — зеркало для отладки (см. `trace_reason_semantics.py`).

## Phase 6 — trace reason alignment (аудит, некритично)

- `**final_outward` опционален для валидатора:** `validate_trace_final_outward_matches_model` не вызывается, если ключа нет (легковесные пробы / тесты). Продуктовые пути (`MathEngine`, `DerivedMetric.invalid`) всегда кладут блок. При необходимости жёсткой гарантии для всех конструкторов — ввести флаг контекста или обязательность ключа только для «сборочных» путей.
- **Порядок merge trace в `_build_computed_metric`:** `computation.trace | trace_body | trace_fragments`. Риск конфликта имён, если вычислитель положит `final_outward` в `computation.trace` до исправления — низкий; при появлении таких кейсов добавить регрессионный тест или явно исключать `final_outward` из `computation.trace`.
- **Переименование ключей во фрагментах trace** (`refusal_candidate_reason_codes`, `resolver_candidate_reason_codes`, и т.д.): внешние потребители сырого JSON trace (вне репозитория) могут требовать миграции — зафиксировать в release notes при публикации API.
- **Comparative / `MetricInputRef.reason_codes`:** имя поля перегружено (comparability-флаги vs declared reasons); семантика описана в docstring `_metric_payload`. Долгосрочно — отдельное поле или типизированный DTO для comparative-входов, если появится путаница в интеграциях.
- **Доказательства для внешних интеграций:** при стабилизации trace-schema — JSON Schema или контрактные тесты на сериализацию полного `DerivedMetric`.

## Расширение семейств reason

- Новые коды в реестре должны попадать в `_PRIORITY_LADDER` в `reason_resolution.py` (иначе tier 999); зафиксировано в docstring — периодически ревью при добавлении токенов.

## Phase 7 — governance test suite (аудит, некритично)

- **AST drift (`test_reason_code_usage`):** не ловит inline через промежуточные переменные, f-strings, `**kwargs`. При усилении governance — расширить обход или точечные исключения.
- **PERIOD proof-of-usage:** сейчас есть `parse_period_label` + comparative `comparability_flags`; нет единого обязательного пути «каждый `PERIOD_`* на `DerivedMetric``» — добавить при продуктовой необходимости.
- **Guard bypass (`model_construct` и т.д.):** не цель Phase 7 suite; при отдельном требовании безопасности — отдельные тесты.
- **Trace test** (`::` / `input:` в `reason_codes`): эвристика против композитов; при появлении легитимных канонических токенов с `:` — пересмотреть.
- **Дублирование:** `validate_reason_code_registry()` вызывается и из `test_reason_codes_registry.py`, и из `test_reason_code_usage.py` — при желании оставить один вызов или общую fixture.

## Wave 4.5 / Iteration 5 — annualization golden suite (некритично)

- **TD-041 (MAJOR):** Для текущего набора scoring-факторов material score change от annualization-path (Q1/H1 vs reported) в boundary payload не проявляется как различие итогового `score`; кейс зафиксирован как observed behavior, но потребуется расширение machine-visible signal при Wave 5/6.
- **TD-042 (MINOR):** Boundary payload не экспонирует transformed annualized source-values напрямую (только `methodology.period_basis` + derived outputs), из-за чего transformed-values проверяются косвенно через machine fields.
- **TD-043 (MINOR):** В annualization freeze тестах currently-affected vs unaffected factors фиксируются по observed normalized/factors payload; при появлении новых annualization-sensitive факторов нужна явная registry-driven матрица affectedness.

## Wave 4.5 / Iteration 6 — guardrails golden + regressions (некритично)

- **TD-044 (MAJOR):** Mandatory guardrail case `invalid factor causing score refusal` покрыт как observed non-refusal behavior, но refusal-boundary не зафиксирован отдельным typed canonical case/exception governance; нужен явный refusal-path freeze либо formalized typed-preserved exception.
- **TD-045 (MAJOR):** Iteration 6 suites обходят общий freeze harness/pipeline (`boundary_runner`, `case_assertions`, typed registries) через локальные runners и ad hoc assertions; требуется привязка к registry-first assertion pipeline для equivalence readiness.
- **TD-046 (MINOR):** Regression check на data-binding rewiring проверяет наличие constants, а не boundary-level wiring behavior; требуется behavioral contract check profile/methodology -> dataset binding -> outcome.
- **TD-047 (MINOR):** Дублирование setup (base metrics/runner helpers) между `test_scoring_guardrails_golden.py` и `test_scoring_regressions.py` повышает drift risk; нужен shared fixture/helper слой.

## Wave 4.5 / Iteration 7 — payload matrix + payload snapshots (некритично)

- **TD-048 (MAJOR):** Payload matrix coverage остаётся неполным по mandatory classes (`full_success`, `with_exclusions`, `invalid_or_suppressed_factor`, `refused_payload`); требуется расширение typed rule sets до полного mandatory class coverage.
- **TD-049 (MAJOR):** Hard-contract payload assertions пока закрывают только текущие rule sets и не дают полного field-level governance для required/optional/nullability/omission по всем mandatory payload classes.
- **TD-050 (MINOR):** Known quirk (`empty factors` при наличии score/methodology) зафиксирован и покрыт, но требует более полного matrix-level documentation depth (семантические поля/contract grid) после расширения payload classes.

## Wave 4.5 / Iteration 8 — invariants + docs sync (некритично)

- **TD-051 (MAJOR):** Invariant governance неполный: `InvariantSeed.expected_checks` используются как metadata/grouping, но не исполняются как machine-enforced check contract; нужен явный seed-check dispatch и обязательное сопоставление каждого expected_check с конкретной проверкой.
- **TD-052 (MAJOR):** Data-binding invariants недостаточно строгие: текущие проверки “same run -> same output” не доказывают требуемые binding invariants (`same profile -> same benchmark binding`, `same methodology -> same annualization binding`, `same anomaly path -> same anomaly-limit binding`) через controlled mutations.
- **TD-053 (MAJOR):** Anti-coupling enforcement неполный: нет достаточной исполнимой защиты от prose/label-first assertions для guardrails и RU-label anchor risk; нужны отдельные проверки semantic independence от display/prose perturbations.
- **TD-054 (MAJOR):** Separation status/reason/explanation проверяется поверхностно (в основном shape/type checks), без достаточной semantic independence валидации machine status/reason относительно explanation layer.
- **TD-055 (MINOR):** Minor clean-code debt в invariant suite: неиспользуемый импорт и локальная читаемость intent checks; требуется небольшой cleanup без изменения semantics.

## Wave 4.5 / Iteration 9 — final handoff (некритично)

- **TD-056 (MINOR):** Handoff doc drift-protection не закреплён отдельным docs-sync тестом: `docs/WAVE_4_5_SCORING_FREEZE.md` корректно derived сейчас, но parity с `render_wave_handoff_md()` не enforced автоматически; добавить проверку в `test_scoring_docs_sync.py`.