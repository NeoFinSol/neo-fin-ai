# Autopilot Versions Roadmap

## Цель

Довести `Autopilot` до состояния, когда его можно безопасно использовать в ежедневной разработке, а затем при необходимости выделить в reusable engine.

## Базовая точка

Уже реализовано:

- planner / routing
- config-driven registry и model chooser
- standalone Codex CLI runtime
- zero-cost runtime smoke test
- cheap real exec smoke test
- mini subagent exec test с JSON contract

Также зафиксированы ключевые архитектурные пробелы следующего этапа:

- reviewer / validator loop
- retry controller
- memory / state layer
- execution graph
- mode policy (`cheap` / `full` / `safe`)

## V5 — Execution Contract Foundation

### Цель

Сделать real subagent execution предсказуемым, строго валидируемым и готовым к reviewer loop.

### Что входит

- единый `SubagentFinalOutput` schema
- строгая local validation результатов subagent run
- унификация error categories
- разделение transport failures и model-output failures
- переиспользуемые helpers для output parsing/validation
- isolated diagnostic path для full structured contract

### Критерий готовности

- любой реальный exec path возвращает либо valid structured output, либо typed failure

## V6 — State and Execution Graph

### Цель

Ввести явную модель выполнения, состояния и графа оркестрации.

### Что входит

- `run_id`, `node_id`, `attempt_id`
- run/node/attempt state contracts
- `ExecutionGraph`, `ExecutionNode`, `ExecutionEdge`
- materialization graph из planner output
- storage contract для artifacts, verdicts и history

### Критерий готовности

- execution orchestration описывается graph/state моделями, а не только списком requests

## V7 — Reviewer and Retry Loop

### Цель

Добавить автоматическую проверку результата и управляемые retries.

### Что входит

- reviewer / validator contract
- reviewer verdicts: `accept`, `retry`, `escalate`
- feedback payload и retry instructions
- retry policy engine
- optional stronger-model retry
- stop conditions и escalation rules

### Критерий готовности

- subagent run замыкается в controlled review cycle, а не заканчивается сырой выдачей

## V8 — Mode Policy and Safe Default

### Цель

Разделить execution по стоимости и качеству и сделать безопасный default mode.

### Что входит

- `cheap` mode
- `full` mode
- `safe` mode
- budgets по depth / timeout / retries / subagent count
- default execution policy для ежедневной разработки
- компактный human-readable summary

### Критерий готовности

- режим запуска выбирается осознанно и даёт предсказуемый balance cost/quality

## V9 — Observability and Performance

### Цель

Сделать поведение автопилота прозрачным и снизить runtime overhead.

### Что входит

- structured execution summary
- durations, failure reasons, selected workflow/subagents/models
- reviewer verdict history
- caching config/registry/profiles
- уменьшение числа runtime probes
- сокращение prompt boilerplate
- controlled parallelism
- micro-benchmarks для planner/runtime path

### Критерий готовности

- любой запуск можно быстро разобрать, а planner/runtime path не делают лишний overhead

## V10 — Reliability and Developer UX

### Цель

Довести автопилот до удобного и устойчивого рабочего инструмента для команды.

### Что входит

- planner-only fallback
- cleanup temp artifacts
- защита от oversized/malformed outputs
- graceful degradation policy
- чистый CLI surface
- explain mode
- recommend-only mode
- документация по использованию
- подготовка к возможному future extraction в отдельный reusable project

### Критерий готовности

- автопилот легко запускать, читать и поддерживать

## Порядок реализации

1. `V5`
2. `V6`
3. `V7`
4. `V8`
5. `V9`
6. `V10`
