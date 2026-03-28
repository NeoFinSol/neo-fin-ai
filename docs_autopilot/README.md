# Docs Autopilot

Документация по развитию `Autopilot` как рабочего инструмента для разработки.

## Содержимое

- `VERSIONS.md` — roadmap по версиям и целевым capability
- `SPRINTS.md` — спринт-план с очередностью, задачами и definition of done
- `SPRINT_1_BACKLOG.md` — implementation backlog для Sprint 1
- `TASKS_SPRINT_1.md` — детальная декомпозиция Sprint 1 на рабочие задачи

## Текущее состояние

На текущий момент в автопилоте уже есть:

- rule-based planner и routing
- config-driven chooser моделей
- `Codex-only` runtime adapter
- `smoke_test_runtime()`
- `exec_smoke_test_runtime()`
- `mini_subagent_exec_test()`
- `full_subagent_exec_test()` с CLI-флагом `--full-subagent-exec-test`

Пока ещё отсутствуют как отдельные системные слои:

- reviewer / validator agent для оценки результата subagent run
- retry controller с явной policy
- memory / state layer для run/node/attempt history
- execution graph как отдельная модель выполнения
- mode policy уровня `cheap` / `full`

## Принцип планирования

Приоритеты развития автопилота:

1. Стабильность execution contract
2. State + execution graph foundations
3. Reviewer loop и управляемые retries
4. Режимы исполнения (`cheap` / `full` / safe default)
5. Наблюдаемость, производительность и удобство реальной разработки
