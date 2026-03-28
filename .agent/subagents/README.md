# 🤖 Система субагентов NeoFin AI

> `Autopilot` как runtime / engine foundation вынесен в `E:\codex-autopilot`.
> В этом репозитории `.agent/subagents/*.md` и `.agent/subagents/*.toml` —
> это **human-readable orchestration kit**, а не скрытый runtime.

## Что хранится в этой папке

- `*.md` — подробные role-specs для продуктовых доменных субагентов
- `*.toml` — лёгкие манифесты оркестрации: preferred model, prompt, auto-triggers, anti-triggers
- `README.md` — правила выбора bundle-ов, max fan-out и phase-based orchestration

## Базовые правила оркестрации

1. Сначала классифицируй задачу.
2. Если задача `local-low-risk`, не зови субагентов.
3. Если задача не `local-low-risk`, сначала выбери **одного primary** субагента:
   - `solution_designer` — если главная проблема в выборе safe path
   - `debug_investigator` — если главная проблема в root cause
4. Затем при необходимости добавь **одного** доменного субагента.
5. Дождись результатов, сделай synthesis, и только потом переходи к коду.
6. Phase-based субагенты (`test_planner`, `code_review`, `docs_keeper`) подключай позже, а не в стартовый fan-out.

## Ограничение fan-out

- `0` субагентов для `local-low-risk`
- `1` primary для большинства `cross-module` / `contract-sensitive` / `bug-investigation`
- `2` субагента — нормальный стартовый bundle для `cross-layer` или средне-рисковой задачи
- `3` субагента — только если после первого pass остаётся неразрешённый риск
- `4` — жёсткий верхний предел и только для реального release/security boundary

> Анти-паттерн: “задача сложная, значит запускаем всех”.

## Категории субагентов

### 1. Core orchestration

Эти роли используются чаще всего и дают наибольшую пользу при минимальном overhead.

| Субагент | Модель | Когда основной выбор |
|---|---|---|
| `solution_designer` | `gpt-5.4` | есть несколько путей реализации |
| `debug_investigator` | `gpt-5.4` | причина бага неочевидна |
| `contracts_guardian` | `gpt-5.4-mini` | API / WS / payload / status surface |
| `test_planner` | `gpt-5.4-mini` | нужно спланировать validation после изменений |

### 2. Product-domain specialists

Эти роли уже существуют как подробные `.md`-спеки и зовутся только по зоне влияния.

| Субагент | Где полезен |
|---|---|
| `extractor` | OCR, PDF ingestion, fallback, confidence |
| `frontend_scout` | frontend consumers, hooks, UI-state impact |
| `scoring_guardian` | ratios, scoring, explainability |
| `db_persistence` | persistence, history, migrations, JSON shape |
| `api_contracts` | legacy product-contract spec; глубокий companion для `contracts_guardian` |

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
| Новый cross-layer feature | `solution_designer` + 1 доменный агент | не добавлять `code_review`/`docs_keeper` в начале |
| Неочевидный баг | `debug_investigator` + 1 доменный агент | не звать `solution_designer` одновременно без причины |
| API / WS / payload / status change | `contracts_guardian` + `frontend_scout` только при реальном UI impact | не добавлять сразу `api_versioning_guardian`, если версия API не меняется |
| Extraction / scoring change | `extractor` или `scoring_guardian` | не связывать их автоматически в каждую задачу |
| Persistence / migration / history change | `db_persistence` или `data_integrity_guardian` | не звать оба без явного риска |
| Release / Docker / nginx / deploy | `security_guardian` + `devops_release` | не тянуть `deployment_guardian`, если нет automation/rollback задачи |
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
- Не звать `security_guardian`, `policy_guardian`, `compliance_guardian` пачкой без явного regulatory/security scope.
- Не звать `devops_release` и `deployment_guardian` вместе, если нет одновременно release risk и deploy automation work.
- Не раздувать orchestration на simple bugfix, typo, local refactor.

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
