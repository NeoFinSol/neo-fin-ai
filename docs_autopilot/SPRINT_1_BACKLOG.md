# Sprint 1 Backlog

## Sprint

`Sprint 1 — Stable Execution Contract`

## Статус

- `Task 1.1 — Typed Failure Model` — выполнен
- `Task 1.2 — Unified Runtime Helpers` — выполнен
- `Task 1.3 — Full Subagent Output Contract` — следующий

## Цель

Подготовить execution layer автопилота к регулярному использованию без неструктурированных ответов и без разрозненной логики обработки ошибок.

## Граница Sprint 1

Sprint 1 остаётся foundational-спринтом. Он должен завершить contract/runtime слой,
но сознательно не включает:

- reviewer / validator agent
- retry controller
- memory / state layer
- execution graph
- mode policy `cheap` / `full` / `safe`

Эти направления вынесены в следующие спринты, чтобы не смешивать завершение execution contract
с новой orchestration architecture.

## Основной результат спринта

К концу Sprint 1 любой реальный subagent execution path должен возвращать:

- либо valid structured output
- либо typed failure с понятной категорией ошибки

## Порядок реализации

### 1. Ввести единый execution contract

**Файл:**
- `E:\\neo-fin-ai\\.agent\\autopilot.py`

**Что сделать:**
- добавить `SubagentFinalOutput`
- добавить typed failure model / error categories
- ввести единый envelope для результата реального subagent execution

**Результат:**
- все реальные execution paths начинают работать через один контракт

**Статус:**
- выполнено частично в рамках `Task 1.1`:
  - добавлены `FailureCode`, `FailureStage`, `ExecutionMode`, `ExecutionFailure`
  - typed failure подключён к probe/smoke/subprocess paths без ломки legacy `error`

### 2. Вынести общую runtime/validation base

**Файл:**
- `E:\\neo-fin-ai\\.agent\\autopilot.py`

**Что сделать:**
- выделить общие helpers для:
  - temp workspace
  - schema file generation
  - one-shot `codex exec`
  - output reading
  - stdout/stderr normalization
  - success/failure envelope building

**Результат:**
- меньше дублирования между diagnostic modes и будущим full exec path

**Статус:**
- выполнено в рамках `Task 1.2`:
  - добавлены общие helpers для runtime setup, temp workspace,
    schema file generation, one-shot `codex exec`, output reading
    и success/failure result building
  - `exec_smoke_test_runtime()` и `mini_subagent_exec_test()`
    переведены на общую runtime основу
  - добавлены regression tests на stdout fallback, missing output
    и helper-level success paths

### 3. Добавить strict full subagent output schema

**Файл:**
- `E:\\neo-fin-ai\\.agent\\autopilot.py`

**Что сделать:**
- определить минимальный `SubagentFinalOutput` contract
- добавить schema builder для full subagent execution
- добавить strict local validation
- сделать contract review-ready, чтобы его можно было позже
  подавать в reviewer loop без повторного redesign

**Минимальный contract v1:**
- `subagent`
- `status`
- `summary`
- `findings`
- `risks`
- `files_to_change`

**Результат:**
- full exec path становится contract-driven, а не text-driven

### 4. Нормализовать typed failures

**Файл:**
- `E:\\neo-fin-ai\\.agent\\autopilot.py`

**Что сделать:**
- ввести error categories:
  - `runtime_unavailable`
  - `timeout`
  - `nonzero_exit`
  - `missing_output`
  - `invalid_json`
  - `schema_mismatch`
  - `unexpected_output`

**Результат:**
- ошибки можно безопасно логировать, агрегировать и использовать в fallback logic

### 5. Добавить isolated full subagent diagnostic mode

**Файл:**
- `E:\\neo-fin-ai\\.agent\\autopilot.py`

**Что сделать:**
- добавить отдельный режим вроде `full_subagent_exec_test()`
- использовать synthetic prompt, но уже full structured output contract
- не вызывать planner pipeline

**Результат:**
- появляется мост между diagnostic modes и будущими
  `run_safe`, reviewer loop и graph execution path

### 6. Обновить CLI surface для Sprint 1

**Файл:**
- `E:\\neo-fin-ai\\.agent\\autopilot.py`

**Что сделать:**
- добавить CLI-флаг для full-contract diagnostic run
- привести названия режимов к единой логике

**Результат:**
- CLI становится готовым к расширению в следующих спринтах

### 7. Обновить документацию и мета-файлы

**Файлы:**
- `E:\\neo-fin-ai\\docs_autopilot\\SPRINTS.md`
- `E:\\neo-fin-ai\\docs_autopilot\\VERSIONS.md`
- `E:\\neo-fin-ai\\.agent\\overview.md`
- `E:\\neo-fin-ai\\.agent\\PROJECT_LOG.md`

**Что сделать:**
- зафиксировать завершённые части Sprint 1
- синхронизировать новый execution contract

## Обязательные тесты

### Contract tests

- valid full subagent JSON
- invalid JSON
- missing required keys
- extra keys
- wrong field types
- wrong `subagent`

### Runtime failure tests

- runtime unavailable
- timeout
- nonzero exit
- missing output file
- empty output

### Isolation tests

- `full_subagent_exec_test()` не вызывает:
  - `build_execution_plan`
  - `prepare_execution_requests`
  - `execute_plan`

### Regression tests

- existing `smoke_test_runtime()`
- existing `exec_smoke_test_runtime()`
- existing `mini_subagent_exec_test()`

### CLI tests

- новый флаг работает без positional `task`
- dispatch идёт в нужный diagnostic path

## Первый коммит

Рекомендуемый первый коммит Sprint 1:

```text
refactor(autopilot): unify execution contract and typed failures
```

## Definition of Done

- full exec path использует structured contract
- failures typed и читаемы
- общая validation/runtime base вынесена
- diagnostic modes не сломаны
- обязательные тесты зелёные
