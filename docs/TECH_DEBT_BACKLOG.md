# Tech debt backlog (Math Layer / analysis)

Записи из аудита Phase 5 (ValidityState ↔ outward reasons), **некритичные** пункты — без немедленного исправления в коде.

Сводка закрытия Wave 4 (код + тесты): [MATH_LAYER_V2_WAVE4_CLOSURE.md](MATH_LAYER_V2_WAVE4_CLOSURE.md).

## Wave 4 / документация

- **Нормативный Wave 4 spec в репозитории:** при появлении финального `math_layer_v2_wave4_spec.md` (или аналога) — свернуть комментарии в `emission_guard.py` / `reason_resolution.py` с документом и добавить ссылку из `AGENTS.md` или архитектурной заметки.

- **TD-026** (`.agent/tech_debt_backlog.md`): после Phase 8 — переименование `validate_wave3_contract` / `_WAVE3_*` literal scan в нейтральные имена и синхронизация старых wave3 spec, если появятся в дереве.

## Граница движка

- **`assert_engine_emission_contract`:** сейчас не вызывается из `engine.py`; валидатор `DerivedMetric` уже выполняет ту же проверку. Опционально: явный вызов в конце сборки метрики только для более читаемых stack trace — избыточно по поведению.

## Legacy / поверхности

- **REST/legacy:** `project_legacy_ratios` отдаёт только `float | None`; отдельные тесты «reason не утекает в legacy dict» не обязательны, пока контракт не меняется. При появлении API, отдающего полный `DerivedMetric`, добавить контрактные тесты на outward поля.

## Trace vs outward

- **Расширение:** при появлении API, отдающего полный `DerivedMetric` наружу, явно документировать, что авторитетные outward-поля — на модели; `trace["final_outward"]` — зеркало для отладки (см. `trace_reason_semantics.py`).

## Phase 6 — trace reason alignment (аудит, некритично)

- **`final_outward` опционален для валидатора:** `validate_trace_final_outward_matches_model` не вызывается, если ключа нет (легковесные пробы / тесты). Продуктовые пути (`MathEngine`, `DerivedMetric.invalid`) всегда кладут блок. При необходимости жёсткой гарантии для всех конструкторов — ввести флаг контекста или обязательность ключа только для «сборочных» путей.

- **Порядок merge trace в `_build_computed_metric`:** `computation.trace | trace_body | trace_fragments`. Риск конфликта имён, если вычислитель положит `final_outward` в `computation.trace` до исправления — низкий; при появлении таких кейсов добавить регрессионный тест или явно исключать `final_outward` из `computation.trace`.

- **Переименование ключей во фрагментах trace** (`refusal_candidate_reason_codes`, `resolver_candidate_reason_codes`, и т.д.): внешние потребители сырого JSON trace (вне репозитория) могут требовать миграции — зафиксировать в release notes при публикации API.

- **Comparative / `MetricInputRef.reason_codes`:** имя поля перегружено (comparability-флаги vs declared reasons); семантика описана в docstring `_metric_payload`. Долгосрочно — отдельное поле или типизированный DTO для comparative-входов, если появится путаница в интеграциях.

- **Доказательства для внешних интеграций:** при стабилизации trace-schema — JSON Schema или контрактные тесты на сериализацию полного `DerivedMetric`.

## Расширение семейств reason

- Новые коды в реестре должны попадать в `_PRIORITY_LADDER` в `reason_resolution.py` (иначе tier 999); зафиксировано в docstring — периодически ревью при добавлении токенов.

## Phase 7 — governance test suite (аудит, некритично)

- **AST drift (`test_reason_code_usage`):** не ловит inline через промежуточные переменные, f-strings, `**kwargs`. При усилении governance — расширить обход или точечные исключения.

- **PERIOD proof-of-usage:** сейчас есть `parse_period_label` + comparative `comparability_flags`; нет единого обязательного пути «каждый `PERIOD_*` на `DerivedMetric``» — добавить при продуктовой необходимости.

- **Guard bypass (`model_construct` и т.д.):** не цель Phase 7 suite; при отдельном требовании безопасности — отдельные тесты.

- **Trace test** (`::` / `input:` в `reason_codes`): эвристика против композитов; при появлении легитимных канонических токенов с `:` — пересмотреть.

- **Дублирование:** `validate_reason_code_registry()` вызывается и из `test_reason_codes_registry.py`, и из `test_reason_code_usage.py` — при желании оставить один вызов или общую fixture.
