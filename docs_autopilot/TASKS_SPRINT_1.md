# Sprint 1 Tasks

## Общий принцип

Задачи ниже расположены в рекомендуемом порядке реализации.

## Что не входит в Sprint 1

Чтобы не расползался scope, Sprint 1 сознательно не включает:

- reviewer / validator agent
- retry controller
- memory / state layer
- execution graph
- mode policy `cheap` / `full` / `safe`

Эти слои теперь относятся к следующим спринтам и не должны
маскироваться под “мелкие доработки” внутри Task 1.3/1.4.

## Task 1.1 — Typed Failure Model

### Статус

Выполнено

### Цель

Создать единый словарь типов ошибок для execution layer.

### Файлы

- `E:\\neo-fin-ai\\.agent\\autopilot.py`

### Что реализовать

- typed error categories
- единый failure envelope
- mapper из runtime/model-output ошибок в typed failure

### Обязательные тесты

- timeout → typed failure
- nonzero exit → typed failure
- invalid JSON → typed failure
- missing output → typed failure

### Выход задачи

- execution layer больше не опирается только на “сырые” `error strings`

### Фактический результат

- добавлены `FailureCode`, `FailureStage`, `ExecutionMode`
- добавлен `ExecutionFailure`
- typed failure внедрён в:
  - `RuntimeProbeResult`
  - `RuntimeSmokeTestResult`
  - `RuntimeExecSmokeTestResult`
  - `MiniSubagentExecTestResult`
  - `SubagentExecutionResult`
- legacy поля `error` сохранены для обратной совместимости
- добавлены тесты на:
  - missing binary
  - timeout
  - nonzero exit
  - JSON serialization

## Task 1.2 — Unified Runtime Helpers

### Статус

Выполнено

### Цель

Убрать дублирование между реальными и diagnostic execution modes.

### Файлы

- `E:\\neo-fin-ai\\.agent\\autopilot.py`

### Что реализовать

- helper для temp workspace
- helper для schema file
- helper для one-shot `codex exec`
- helper для чтения output file
- helper для success/failure result building

### Обязательные тесты

- success helper path
- missing output file
- invalid output payload

### Выход задачи

- `exec_smoke_test_runtime()` и `mini_subagent_exec_test()` используют общую основу

### Фактический результат

- в `.agent/autopilot.py` добавлены общие helpers для:
  - runtime setup
  - temp workspace
  - schema file generation
  - one-shot `codex exec`
  - output reading
  - success/failure result building
- `exec_smoke_test_runtime()` и `mini_subagent_exec_test()`
  переведены на общую runtime основу без изменения публичных result contract
- mode-specific validation/result builders сохранены раздельными,
  чтобы не смешивать smoke token validation и mini JSON validation

### Верификация

- success helper path
- missing output file
- invalid output payload
- `$env:PYTHONPATH='E:\\neo-fin-ai'; python -m pytest tests\\test_choose_model_for_subagent.py tests\\test_agent_autopilot.py` → `41 passed`
- `python -m flake8 --isolated --max-line-length=100 .agent\\autopilot.py .agent\\choose_model_for_subagent.py tests\\test_choose_model_for_subagent.py tests\\test_agent_autopilot.py`

## Task 1.3 — Full Subagent Output Contract

### Цель

Подготовить contract-driven и review-ready path для реального subagent execution.

### Файлы

- `E:\\neo-fin-ai\\.agent\\autopilot.py`
- `E:\\neo-fin-ai\\tests\\test_agent_autopilot.py`

### Что реализовать

- `SubagentFinalOutput`
- schema builder для full exec
- strict validator
- минимальный structured output contract
- форма результата должна быть пригодна для будущего reviewer loop
  без второго redesign контракта

### Обязательные тесты

- valid structured output
- wrong keys
- wrong field types
- wrong subagent name
- extra keys

### Выход задачи

- full subagent execution имеет стабильный машинно-валидируемый контракт
- contract совместим с будущим reviewer/state/graph layer

## Task 1.4 — Full Diagnostic Exec Mode

### Цель

Добавить diagnostic режим, который использует full contract, но не трогает orchestration.

### Файлы

- `E:\\neo-fin-ai\\.agent\\autopilot.py`
- `E:\\neo-fin-ai\\tests\\test_agent_autopilot.py`

### Что реализовать

- `full_subagent_exec_test()`
- CLI-флаг для запуска
- synthetic prompt с full structured output
- planner isolation

### Обязательные тесты

- режим не вызывает:
  - `build_execution_plan`
  - `prepare_execution_requests`
  - `execute_plan`
- CLI dispatch
- success/failure execution path

### Выход задачи

- есть безопасный diagnostic bridge между mini mode,
  будущим `run_safe` и future reviewer loop

## Порядок выполнения

1. `Task 1.1`
2. `Task 1.2`
3. `Task 1.3`
4. `Task 1.4`

## Точка завершения Sprint 1

Sprint 1 считается завершённым, когда:

- `Task 1.1–1.4` реализованы
- contract tests и regression tests зелёные
- новый execution contract зафиксирован в документации
