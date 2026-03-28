# 🤖 Система субагентов NeoFin AI

> `Autopilot` как runtime / engine foundation вынесен в `E:\codex-autopilot`.
> В этом репозитории `.agent/subagents/*.md` и `.agent/subagents/*.toml` —
> это **human-readable orchestration kit**, а не скрытый runtime.

## Что хранится в этой папке

- `*.md` — подробные role-specs для продуктовых доменных субагентов
- `*.toml` — registry-backed манифесты оркестрации: preferred model, prompt, auto-triggers, anti-triggers
- `README.md` — правила выбора bundle-ов, max fan-out и phase-based orchestration

Важно:
- `.toml` — это registry entry для оркестратора
- `.md` — это deep role-spec, который тоже можно вызывать по имени роли
- отсутствие `.toml` не означает, что роль нельзя использовать; это означает, что у неё пока нет registry-backed manifest
- `default` / `explorer` / `worker` — это только tool/runtime carrier; они не являются заменой project-role

## Role identity vs runtime carrier

Оркестратор должен различать два уровня:

- **project-role**: `solution_designer`, `contracts_guardian`, `data_integrity_guardian`, `extractor` и т.д.
- **runtime carrier**: `default`, `explorer`, `worker`

Правильный порядок такой:

1. выбрать project-role по manifest / role-spec
2. взять её `preferred_model`, `reasoning_effort`, prompt и trigger policy
3. только потом выбрать carrier как технический способ исполнения

Неправильно:

- запускать просто `explorer` и писать ему “действуй как solution_designer”
- в отчёте писать, что был вызван `explorer`, не называя реальную роль
- считать, что carrier автоматически определяет обязанности субагента

## Hard invocation protocol

Внешний вызов считается валидным только если оркестратор до запуска явно определил:

1. `project-role`
2. source of truth:
   - `.toml` manifest
   - или `.md` role-spec
3. `preferred_model`
4. `reasoning_effort`
5. `runtime carrier`

Если один из пунктов отсутствует, вызов нельзя считать role-bound delegation.

Практическое следствие:

- нельзя сначала запустить generic carrier, а потом “додумать”, какой это был субагент
- нельзя использовать findings такого вызова как findings role-level субагента
- в сомнительном случае правильный fallback — локальный synthesis без внешней делегации

## Базовые правила оркестрации

1. Сначала классифицируй задачу.
2. Если задача `local-low-risk`, не зови субагентов.
3. Если задача не `local-low-risk`, сначала реши, нужен ли вообще внешний read-only pass:
   - если path очевиден и риск узкий, достаточно internal orchestration + synthesis без внешних субагентов
   - если нужен независимый investigation pass, тогда выбирай субагента
4. Если нужен внешний pass, сначала выбери **одного primary** субагента:
   - `solution_designer` — если главная проблема в выборе safe path
   - `debug_investigator` — если главная проблема в root cause
5. Затем при необходимости добавь **одного** доменного субагента, но только если есть второй независимый риск.
6. Дождись результатов, сделай synthesis, и только потом переходи к коду.
7. Phase-based субагенты (`test_planner`, `code_review`, `docs_keeper`) подключай позже, а не в стартовый fan-out.

## Когда orchestration не требует делегации

Orchestration mode обязателен для задач выше `local-low-risk`, но вызов субагента обязателен не всегда.

Можно обойтись без делегации, если одновременно верны все условия:

- внешний HTTP / WS / persisted contract не меняется
- root cause уже ясен или бага вообще нет
- migration/data invariant риска нет
- release/security/runtime boundary не меняется
- safe path можно сформулировать локально в 2-3 шага

## Ограничение fan-out

- `0` субагентов для `local-low-risk`
- `0` внешних субагентов также допустимы для non-local задачи, если external pass не добавляет новой информации
- `0-1` внешний субагент — нормальный старт для большинства `cross-module`
- `1` внешний субагент — нормальный старт для большинства `contract-sensitive` / `bug-investigation` / `cross-layer`
- `2` субагента — только если нужен второй независимый domain pass
- `3` субагента — только если после первого pass остаётся неразрешённый риск
- `4` — жёсткий верхний предел и только для реального release/security boundary

> Анти-паттерн: “задача сложная, значит запускаем всех”.

### Правило независимого риска

- один риск → один агент
- два независимых риска → максимум два агента
- второй агент не добавляется “для уверенности”, если primary уже покрывает основной риск

### Stop rule

Если после первого pass уже понятны:

- минимальный safe path
- инварианты
- validation plan

то fan-out закрывается, и новые субагенты не добавляются.

## Deep synthesis ladder

Для very-complex задач разрешён не fan-out ради количества, а staged synthesis:

### Stage 1. Primary pass

- один primary subagent по главной неопределённости

### Stage 2. Independent cross-check

- максимум один дополнительный subagent по другому риску
- только если этот риск реально независим

### Stage 3. Cross-synthesis checkpoint

Оркестратор обязан ответить себе:

- findings согласуются или конфликтуют?
- инварианты уже ясны?
- нужен ли ещё один pass?

Если ответы уже получены, orchestration останавливается.

### Stage 4. Pre-implementation gate

До кода должны быть явно названы:

- minimal safe path
- validation plan
- failure/rollback expectations

Это и есть правильный “дополнительный слой синтеза” для сложных задач.

## Invocation budget

### 1. Core-auto

Автоматически допустимые кандидаты, но только по явному trigger.

| Субагент | Вызывать когда |
|---|---|
| `debug_investigator` | root cause бага неясен или есть flaky / cross-layer mismatch |
| `solution_designer` | есть 2+ реалистичных safe path и нужен выбор |
| `contracts_guardian` | меняется публичный HTTP/WS/status/payload surface |

### 2. Domain-auto

Авто-кандидаты только по узкому техническому surface.

| Субагент | Вызывать когда |
|---|---|
| `data_integrity_guardian` | schema/migration/backfill/history/invariants |
| `security_guardian` | auth/upload/secrets/public boundary |
| `integration_guardian` | внешние APIs/providers/webhooks |
| `dependency_guardian` | packages/images/provider deps реально меняются |
| `performance_guardian` | perf/memory/token-cost/large-input behaviour — часть задачи |

### 3. Phase-gated

Не стартовые агенты. Подключаются только после diff или ближе к closure/release.

| Субагент | Вызывать когда |
|---|---|
| `test_planner` | после medium/high-risk diff |
| `code_review` | когда уже есть реализация |
| `docs_keeper` | при закрытии логической единицы |
| `devops_release` | когда реально меняется release/deploy/runtime path |
| `deployment_guardian` | когда меняется deploy automation / rollback |
| `runtime_guardian` | когда меняется lifecycle/health semantics |
| `error_monitoring_guardian` | когда меняется error taxonomy / alerting |
| `usability_guardian` | когда меняется user journey, а не просто frontend код |

### 4. Manual-explicit

Не auto-invoke. Только по прямому scope или явному запросу.

| Субагент | Когда допустим |
|---|---|
| `planner_guardian` | пользователь явно просит план / roadmap / sequencing |
| `policy_guardian` | нужен разбор внутренних policy/process constraints |
| `compliance_guardian` | задача прямо затрагивает regulatory/legal требования |
| `api_versioning_guardian` | есть breaking compatibility или migration window |
| `audit_guardian` | требуется auditability / traceability как цель задачи |
| `backup_guardian` | затрагиваются backup/restore/recovery guarantees |
| `feature_flag_guardian` | задача реально меняет rollout flags / kill-switches |

Практическое правило: если роль нельзя обосновать одной отдельной фразой риска, её не надо вызывать.

## Failure diagnostics

Если orchestration-pass завершился плохо, оркестратор должен не “дозвать всех”, а сначала диагностировать тип сбоя:

- role-binding был нарушен
- ответ неполный
- findings противоречат друг другу
- timeout / invalid completion
- pass не дал новой информации

Только после этого допустим один следующий шаг:

- узкий retry того же role-bound subagent
- compensating pass другого subagent
- локальный synthesis с явным описанием остаточной неопределённости

`Failure diagnostics` нужен для качества оркестрации, а не для раздувания fan-out.

## Adaptive review

Система orchestration должна адаптироваться, но только через manual documentation hardening.

Триггеры для review:

- повторяющиеся misfire случаи
- новые типы задач
- изменение архитектуры проекта
- повторяющиеся diagnostic failures

Что обновляется:

- trigger policy
- bundle recommendations
- anti-rules
- deep-synthesis guidance

Что не делается:

- не добавляется скрытый runtime-слой
- не возвращается Autopilot foundation
- не вводится автономная self-modifying логика

### Формат вызова ролей

- если у роли есть `.toml`, оркестратор использует его как основной registry entry
- если у роли есть только `.md`, оркестратор использует `.md` как source of truth для зоны ответственности и expected output
- `.toml` отвечает за invocation policy, `.md` отвечает за deep role-spec
- при фактическом вызове в отчёте должны явно фигурировать оба слоя:
  - project-role
  - runtime carrier
- project-role всегда указывается первой и считается source of truth; carrier описывает только технику исполнения
- prompt должен опираться на уже выбранную роль, а не создавать её формулой `act as ...`

## Категории субагентов

### 1. Core orchestration

Эти роли используются чаще всего и дают наибольшую пользу при минимальном overhead.

| Субагент | Модель | Когда основной выбор |
|---|---|---|
| `solution_designer` | `gpt-5.4` | есть несколько путей реализации |
| `debug_investigator` | `gpt-5.4` | причина бага неочевидна |
| `contracts_guardian` | `gpt-5.4` | API / WS / payload / status surface |
| `test_planner` | `gpt-5.4-mini` | нужно спланировать validation после изменений |

### 2. Product-domain specialists

Эти роли сейчас живут как подробные `.md`-спеки без `.toml`-manifest. Их можно вызывать по имени роли, но source of truth для вызова и expected output у них находится в `.md`.

| Субагент | Где полезен |
|---|---|
| `extractor` (`.md` only) | OCR, PDF ingestion, fallback, confidence |
| `frontend_scout` (`.md` only) | frontend consumers, hooks, UI-state impact |
| `scoring_guardian` (`.md` only) | ratios, scoring, explainability |
| `db_persistence` (`.md` only) | persistence, history, migrations, JSON shape |
| `api_contracts` (`.md` only) | legacy product-contract spec; глубокий companion для `contracts_guardian` |

### 3. Governance / release / specialized guards

Вызываются по явным trigger-ам, а не “по умолчанию”.

| Субагент | Модель | Вызывать когда |
|---|---|---|
| `code_review` | `gpt-5.4` | после medium/high-risk реализации |
| `docs_keeper` | `gpt-5.4-mini` | на закрытии логической единицы |
| `planner_guardian` | `gpt-5.4-mini` | пользователь просит план/дорожную карту |
| `security_guardian` | `gpt-5.4` | auth, upload, public surface, secrets |
| `policy_guardian` | `gpt-5.4` | internal policy/process constraints |
| `compliance_guardian` | `gpt-5.4` | legal/regulatory constraints |
| `runtime_guardian` | `gpt-5.4-mini` | health/runtime behaviour/monitoring |
| `performance_guardian` | `gpt-5.4-mini` | perf, latency, memory, CPU |
| `error_monitoring_guardian` | `gpt-5.4-mini` | exception classes, alerting, error taxonomy |
| `audit_guardian` | `gpt-5.4-mini` | audit trails and change traceability |
| `integration_guardian` | `gpt-5.4-mini` | external APIs, providers, webhooks |
| `data_integrity_guardian` | `gpt-5.4` | invariants, consistency, backfills, migrations |
| `dependency_guardian` | `gpt-5.3-codex` | dependency updates, compatibility, vuln surface |
| `feature_flag_guardian` | `gpt-5.4-mini` | rollout flags and activation logic |
| `api_versioning_guardian` | `gpt-5.4` | versioning, backward compatibility, migrations |
| `backup_guardian` | `gpt-5.4-mini` | backup / restore / recoverability |
| `devops_release` | `gpt-5.3-codex` | release readiness, deploy risk |
| `deployment_guardian` | `gpt-5.3-codex` | deploy automation, rollback, rollout mechanics |
| `usability_guardian` | `gpt-5.4-mini` | UX/UI friction and user flows |

## Рекомендуемые bundle-ы

| Ситуация | Стартовый bundle | Не делать |
|---|---|---|
| Новый cross-layer feature | `solution_designer` или `0 external`, если path уже очевиден | не добавлять `code_review`/`docs_keeper` в начале |
| Неочевидный баг | `debug_investigator` + максимум 1 доменный агент | не звать `solution_designer` одновременно без причины |
| API / WS / payload / status change | `contracts_guardian`; `frontend_scout` только при реальном UI impact | не добавлять сразу `api_versioning_guardian`, если версия API не меняется |
| Extraction / scoring change | `extractor` или `scoring_guardian` | не связывать их автоматически в каждую задачу |
| Persistence / migration / history change | `data_integrity_guardian` или `db_persistence` | не звать оба без явного риска |
| Release / Docker / nginx / deploy | `devops_release`; `security_guardian` только при trust-boundary impact | не тянуть `deployment_guardian`, если меняется не automation, а общий release/runtime risk |
| Большая программа работ / roadmap | `planner_guardian` + `solution_designer` | не путать planning с реализацией |
| Финал medium/high-risk задачи | `test_planner` → `code_review` → `docs_keeper` | не делать их стартовым investigation bundle |

## Phase-based правила

### До реализации

- `solution_designer`
- `debug_investigator`
- `contracts_guardian`
- domain specialists
- `planner_guardian` — только если реально нужен план

### Во время реализации

- Обычно без новых субагентов
- Эскалация только если synthesis оказался недостаточным

### После реализации

- `test_planner` — почти всегда для medium/high-risk
- `code_review` — для critical paths, contracts, persistence, release-sensitive changes
- `docs_keeper` — при закрытии логической единицы и docs drift

## Минимальные anti-rules

- Не запускать и `solution_designer`, и `debug_investigator` одновременно “на всякий случай”.
- Не запускать `code_review` до появления diff.
- Не запускать `docs_keeper` в начале задачи.
- Не вызывать субагентов только потому, что задача `cross-module`.
- Не считать `cross-layer` автоматическим основанием для двух агентов.
- Не запускать `contracts_guardian`, если меняется только внутренняя реализация при том же outward contract.
- Не звать `security_guardian`, `policy_guardian`, `compliance_guardian` пачкой без явного regulatory/security scope.
- Не звать `devops_release` и `deployment_guardian` вместе, если нет одновременно release risk и deploy automation work.
- Не трактовать `orchestration mode` как обязательство позвать хотя бы одного внешнего субагента.
- Не раздувать orchestration на simple bugfix, typo, local refactor.
- Не подменять выбранную роль generic carrier-агентом с prompt’ом “act as ...”.
- Не считать role-binding “подразумеваемым”, если он не был явно зафиксирован.

## Как читать TOML manifests

Каждый `.toml` хранит:

- идентификатор роли
- предпочитаемую модель
- phase
- auto-triggers
- anti-triggers
- prompt для вызова субагента

Это **не runtime engine** и не возвращение foundation-слоя Autopilot.
Это удобный и единообразный человеко-читаемый registry для оркестратора.
