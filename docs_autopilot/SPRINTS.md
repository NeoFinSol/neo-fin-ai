# Autopilot Sprint Plan

## Принцип пересборки плана

Текущий план пересобран после появления новых требований к архитектуре:

- нужен reviewer / validator loop, а не только raw subagent execution
- нужен retry controller с явной policy
- нужен memory / state layer
- нужен execution graph вместо плоского списка шагов
- нужны режимы `cheap` и `full`, а не один усреднённый execution mode

Sprint 1 не отменяется: он остаётся foundational и доводит execution contract до состояния,
на котором уже можно строить reviewer/state/graph слой без переписывания runtime ещё раз.

## Sprint 1 — Execution Contract Foundation

### Цель

Довести execution layer до contract-driven состояния и подготовить базу для reviewer loop.

### Что входит

1. Typed failure foundation.
2. Unified runtime helpers для diagnostic exec paths.
3. `SubagentFinalOutput` contract для full execution path.
4. Strict local validation и parser для full structured output.
5. Isolated diagnostic mode для full contract.
6. Единый CLI surface для diagnostic contract modes.

### Что сознательно не входит

- reviewer / validator agent
- retry controller
- memory / state persistence
- execution graph orchestration
- `cheap` / `full` mode policy

### Definition of Done

- full exec path выдаёт typed structured result
- diagnostic modes используют общую runtime основу
- ошибки классифицированы и читаемы
- нет “сырого текста” как основного execution interface

## Sprint 2 — State and Execution Graph Foundations

### Цель

Ввести явное состояние выполнения и graph-модель, на которой потом строятся review и retries.

### Задачи

1. Добавить `run state` model:
   - `run_id`
   - `status`
   - `mode`
   - `created_at`
   - `updated_at`
2. Добавить `node state` / `attempt state`:
   - `node_id`
   - `subagent`
   - `attempt`
   - `input`
   - `output`
   - `artifacts`
   - `failure`
3. Описать `ExecutionGraph` / `ExecutionNode` / `ExecutionEdge`.
4. Разделить planner output и execution graph materialization.
5. Подготовить storage contract для in-memory first implementation.

### Definition of Done

- запуск имеет явный state object
- subagent execution описывается graph-узлами, а не только list requests
- есть база для review/retry orchestration без повторной смены контрактов

## Sprint 3 — Reviewer Loop and Controlled Retries

### Цель

Добавить closed-loop execution: проверка результата, feedback и решение о retry/accept/escalate.

### Задачи

1. Ввести reviewer / validator agent contract.
2. Ввести reviewer verdict:
   - `accept`
   - `retry`
   - `escalate`
3. Добавить feedback payload:
   - `summary`
   - `issues`
   - `retry_instructions`
4. Реализовать retry controller:
   - max attempts
   - retryable / non-retryable failures
   - same-model retry
   - optional stronger-model retry
5. Зафиксировать stop conditions и escalation policy.

### Definition of Done

- subagent output может быть проверен автоматически
- retry управляется policy, а не ad-hoc логикой
- reviewer loop не ломает typed execution contract

## Sprint 4 — Execution Modes and Safe Default

### Цель

Разделить execution policy по стоимости и качеству: `cheap`, `full` и безопасный режим по умолчанию.

### Задачи

1. Ввести mode policy:
   - `cheap`
   - `full`
   - `safe`
2. Для каждого режима задать:
   - allowed subagents
   - model tier
   - max depth
   - retry budget
   - timeout budget
3. Добавить `run_safe()` / `--run-safe`.
4. Добавить compact summary для safe/cheap runs.
5. Синхронизировать mode policy с planner и execution graph.

### Definition of Done

- существует понятный default mode для ежедневной разработки
- `cheap` минимизирует вызовы и стоимость
- `full` максимизирует качество и глубину проверки

## Sprint 5 — Observability, Performance and Reliability

### Цель

Сделать автопилот прозрачным, быстрым и устойчивым в реальной работе.

### Задачи

1. Добавить structured execution summary и tracing:
   - task type
   - workflow
   - selected subagents
   - reviewer verdicts
   - retries
   - durations
2. Добавить caching:
   - `.codex/config.toml`
   - `.codex/agents/*.toml`
   - parsed planner/runtime config
3. Убрать лишние repeated probes внутри одного run.
4. Добавить cleanup policy для temp artifacts.
5. Добавить planner-only fallback и graceful degradation.
6. Подготовить manual live verification checklist.

### Definition of Done

- любой запуск можно быстро разобрать постфактум
- transient failures деградируют контролируемо
- runtime overhead остаётся приемлемым

## Рекомендуемый порядок

1. Sprint 1
2. Sprint 2
3. Sprint 3
4. Sprint 4
5. Sprint 5

## Точка готовности для реального использования

Автопилот считается пригодным для регулярной разработки, когда:

- execution graph и state layer стабильны
- reviewer loop и retries работают по policy
- `safe` mode стабилен как default path
- `cheap` и `full` modes предсказуемо различаются по cost/quality
- diagnostic/live smoke modes остаются зелёными
- ошибки typed и наблюдаемы
