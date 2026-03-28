
---

# **AGENTS.md** — Правила работы с проектом NeoFin AI

<!-- Версия: 1.7 | Обновлено: 2026-03-28 -->

> Все вспомогательные файлы агентов лежат в `.agent/`. При сомнениях — читай их в первую очередь.
>
> ⚠️ `Autopilot` как отдельный R&D/engine слой перенесён в `E:\codex-autopilot`.
> В `NeoFin AI` не развиваем больше experimental Autopilot runtime/docs; здесь
> держим только продуктовый код и human-readable agent workflow.

---

## 🎯 Основные принципы

* **Архитектура**: Layered (routers → tasks → analysis pipeline → ai_service → db/crud). Зависимости строго однонаправленные — сверху вниз.
* **WebSocket**: используется для real-time обновлений статуса задач (`/ws/{task_id}`). Фронтенд использует гибридную стратегию (WS + Polling fallback).
* **Лимит контекста**: при приближении к 90k токенов — предложить сжатие.
* **Коммиты**: после каждой завершённой логической единицы (фича, багфикс, рефакторинг модуля).
* **Язык кода**: английский (имена, комментарии в коде). Документация и мета-файлы — русский.
* **Тесты**: pytest; писать после реализации; обязательны для новых функций в `src/analysis/` и `src/core/`.
* **Приоритет правил при конфликте**: `AGENTS.md` > линтеры (`.flake8`, `ruff`) > устные инструкции > общие best practices.
* **Решение багов**: всегда использовать архитектурно чистое решение. Не хакать симптом — устранять корневую причину. Если есть выбор между быстрым костылём и правильным решением — выбирать правильное, если пользователь явно не указал иное.
* **Правило первой ошибки**: при первой ошибке в сессии — сразу проверить `.agent/local_notes.md` на похожие проблемы. После устранения — занести в `local_notes.md` и `PROJECT_LOG.md`.

---

## 📚 Вынесенные операционные документы

* `.agent/architecture.md` — подробная структура проекта, жёсткие лимиты, триггеры действий, Docker production notes
* `.agent/checklists.md` — чеклист перед коммитом, validation patterns, deployment checks
* `.agent/modes.md` — режимы работы агента, переключение, поведение каждого режима

---

## 📁 Критичные файлы для контекста

| Файл                             | Зачем держать в контексте                                        |
| -------------------------------- | ---------------------------------------------------------------- |
| `.agent/overview.md`             | Текущий статус: что работает, что в разработке, приоритеты       |
| `.agent/local_notes.md`          | Известные баги, воркэраунды, архив решённых проблем              |
| `.agent/PROJECT_LOG.md`          | История изменений — читать последние 3 записи для быстрого вката |
| `.agent/architecture.md`         | Слои, data flow, паттерны, жёсткие лимиты                        |
| `src/tasks.py`                   | Оркестратор pipeline; декомпозирован на фазы                     |
| `frontend/src/api/interfaces.ts` | Контракт данных frontend; единственный источник правды           |
| `docs/ARCHITECTURE.md`         | Структура архитектуры и важные ограничения                       |
| `docs/BUSINESS_MODEL.md`       | Бизнес-логика, модель данных и ключевые предположения            |
| `docs/CONFIGURATION.md`        | Конфигурация, env переменные, настройки для продакшн             |
| `docs/INSTALL_WINDOWS.md`      | Установка и настройка для Windows среды                          |
| `docs/ROADMAP.md`              | Долгосрочные планы, roadmap, приоритеты для будущих фич          |
| `docs/API.md`                  | Документация по API, описание эндпоинтов и контрактов            |

> ⚠️ Правило: эти файлы обновляются ПЕРЕД сжатием контекста. Не сжимай контекст без обновления `.agent/overview.md` и `.agent/PROJECT_LOG.md`.

---

## 🧠 Как работать с контекстом

### Когда сжимать:

* Контекст > 90k токенов
* Завершена логическая задача (фича, багфикс, рефакторинг)
* Перед долгим перерывом в работе

### Что делать перед сжатием (строго по порядку):

1. Обновить `.agent/overview.md` — статус, что сделано, что дальше
2. Добавить запись в `.agent/PROJECT_LOG.md` (новые записи — сверху)
3. Если были баги → обновить `.agent/local_notes.md`
4. Удалить из контекста исходный код, оставив только мета-файлы из `.agent/`

### Когда расширять контекст:

* Рефакторинг нескольких связанных модулей
* Анализ кросс-модульных багов
* Онбординг в новую подсистему

> ⚠️ Правило: не держи в контексте исходный код больше чем 4–5 файлов одновременно.

---

## 🔔 Автоматические напоминания

* Каждые 5 сообщений → сообщи: «Контекст: ~XXk токенов. Нужно сжать?»
* После 3 коммитов подряд → предложи обновить `.agent/overview.md`
* При первой ошибке в сессии → проверь `.agent/local_notes.md` на похожие проблемы
* При изменении структуры ответа API → напомни обновить `frontend/src/api/interfaces.ts`

---

## 🛠️ Правила кодирования

### Python (backend):

* Стандарт: PEP 8, ruff (`.ruff_cache/`), flake8 (`.flake8`)
* Именование: `snake_case` для функций/переменных, `PascalCase` для классов, `UPPER_CASE` для констант
* Функции: не длиннее 50 строк; если длиннее — выноси в отдельную функцию
* Типизация: обязательна для всех публичных функций (`def foo(x: int) -> str`)
* Логирование: только `logger = logging.getLogger(__name__)`; никаких `print()`
* Async: все I/O операции — `async`; CPU-bound (PDF, расчёты) — `asyncio.to_thread()`

### TypeScript (frontend):

* Стандарт: TypeScript strict mode
* Типы: использовать только `frontend/src/api/interfaces.ts`; `types.ts` — не трогать
* Компоненты: функциональные, с хуками; никаких class-компонентов

### Архитектурные ограничения:

| Правило                                                      | Пример нарушения                                         |
| ------------------------------------------------------------ | -------------------------------------------------------- |
| ❌ `routers/` не содержат бизнес-логику                       | `upload.py` вызывает `calculate_ratios()` напрямую       |
| ❌ `analysis/*` не импортируют FastAPI/SQLAlchemy             | `ratios.py` делает `from fastapi import ...`             |
| ❌ SQL только в `src/db/crud.py`                              | `tasks.py` вызывает `session.execute()`                  |
| ❌ AI только через `src/core/ai_service.py`                   | `nlp_analysis.py` импортирует `gigachat_agent` напрямую  |
| ❌ Маппинг и трансляция ключей в `tasks.py`                   | Перенос `translate_ratios()` из `ratios.py` в `tasks.py` |
| ✅ Новые коэффициенты → добавить в `ratios.py` и `scoring.py` |                                                          |
| ✅ Новые поля ответа → синхронно обновить `interfaces.ts`     |                                                          |

---

## 💬 Формат ответов на задачи

При предложении решения структурируй ответ:

```id="5eicpc"
📋 Задача: [перефразируй одной строкой]
🔍 Анализ: [какие файлы затронуты, какие зависимости]
💡 Решение: [что конкретно делаешь]
🧪 Проверка: [как убедиться что работает: тест, curl, ручная проверка]
⏭️ Дальше: [следующий логичный шаг]
```

Для простых задач (< 10 строк кода) — формат свободный, без шаблона.

---

## ⚖️ Иерархия правил (от высшего к низшему)

1. `AGENTS.md` (этот файл)
2. `.flake8` / `ruff` / TypeScript strict (линтеры)
3. Устные инструкции пользователя в текущей сессии
4. Общие best practices (PEP 8, SOLID, etc.)

> Если правило из уровня 3 противоречит уровню 1 → следуй уровню 1 и явно сообщи пользователю о конфликте.

---

## 🔄 Рабочий процесс (после каждой задачи)

```id="9x9c8u"
Задача выполнена
    ↓
Обнови .agent/overview.md (статус)
    ↓
Запиши в .agent/PROJECT_LOG.md (новая запись сверху)
    ↓
Были баги? → обнови .agent/local_notes.md
    ↓
Коммит: тип(scope): описание
    ↓
Предложи сжать контекст (если > 90k токенов)
```

### Формат коммит-сообщения:

```id="ujpd76"
тип(scope): краткое описание (до 72 символов)

[опционально] Подробности если нужны.
```

Типы: `feat`, `fix`, `refactor`, `test`, `docs`, `chore`
Примеры:

* `feat(ratios): add quick_ratio and absolute_liquidity coefficients`
* `fix(tasks): update RATIO_KEY_MAP for new ratios keys`
* `docs(agent): update overview.md after NLP pipeline fix`

---

## 🚫 Чего НЕ делать

* ❌ Не меняй архитектуру слоёв без явного запроса пользователя
* ❌ Не удаляй комментарии, объясняющие «почему», а не «что»
* ❌ Не игнорируй `.agent/local_notes.md` при работе с похожим кодом
* ❌ Не предлагай сжатие контекста без обновления мета-файлов
* ❌ Не используй `frontend/src/api/types.ts` (удалён) — только `interfaces.ts`
* ❌ Не вызывай `gigachat_agent` или `agent` напрямую — только через `ai_service.py`
* ❌ Не пиши SQL вне `src/db/crud.py`
* ❌ Не меняй один таймаут AI — меняй все три файла сразу
* ❌ Не запускай `npm run dev` или `uvicorn` как блокирующие команды в сессии
* ❌ Не копируй `.env` в Docker-образ (используй `env_file` в docker-compose)
* ❌ Не запускай backend от root в Docker (используй `appuser` в Dockerfile.backend)

---

## 🆘 Если что-то непонятно

1. Прочитай `.agent/overview.md` и `.agent/PROJECT_LOG.md` (последние 3 записи)
2. Проверь `.agent/local_notes.md` — возможно, проблема уже описана
3. Если неясно → задай уточняющий вопрос, не предполагай
4. При конфликте правил → приоритет по иерархии выше; сообщи пользователю о конфликте

## 🤖 Multi-agent orchestration (ОЧЕНЬ ВАЖНО)

### 🚨 Orchestration trigger

Перед началом реализации агент ОБЯЗАН классифицировать задачу:

* `local-low-risk`
* `cross-module`
* `cross-layer`
* `contract-sensitive`
* `bug-investigation`
* `release/security-sensitive`

Если задача НЕ `local-low-risk`, агент ОБЯЗАН перейти в orchestration mode.

> Важно: `orchestration mode` не означает автоматический вызов субагентов.
> Для части задач orchestration может завершиться локальным synthesis без делегации,
> если риск понятен, контракт не меняется и safe path очевиден.

---

### 🔁 Правила orchestration mode

В orchestration mode агент ОБЯЗАН:

1. Выбрать подходящий workflow из `.agent/subagents/README.md`
2. Определить, нужна ли делегация вообще, или достаточно локального lightweight synthesis
3. Если делегация нужна — определить **минимально достаточный** набор релевантных субагентов
4. Запустить нужных субагентов как read-only investigation pass
5. Дождаться результатов всех субагентов
6. Выполнить synthesis:

   * какие файлы менять
   * какие инварианты сохранить
   * какие риски
   * какой минимальный safe path
7. Только после synthesis приступать к реализации

### 🎛️ Lean orchestration policy

По умолчанию оркестратор НЕ должен раздувать fan-out.

- orchestration mode = classify + synthesize discipline; это НЕ означает обязательный внешний fan-out
- `0 external subagents` допустимы, если задача не `local-low-risk`, но surface узкий, путь очевиден и независимый read-only pass не даст новой информации
- стартовый default: `0 или 1` внешний субагент
- обычный upper bound для старта: `1` внешний субагент
- `2` субагента допустимы, только если нужен второй независимый domain pass
- `3` субагента допустимы только если после первого investigation pass остаётся неразрешённый риск
- `4` — жёсткий максимум и только для реального release/security boundary

#### Primary выбор:
- `solution_designer` — если главная неопределённость в выборе safe implementation path
- `debug_investigator` — если главная неопределённость в root cause бага

#### MUST auto-invoke при явном trigger:
- `debug_investigator` — root cause неясен, баг flaky, есть mismatch между слоями
- `contracts_guardian` — меняется публичный API payload / WebSocket flow / status semantics / frontend-consumed fields
- `data_integrity_guardian` — меняется schema / migration / backfill / stored-data invariants / history compatibility
- `security_guardian` — меняется auth / upload / secrets / public boundary / exposed config
- `devops_release` — меняется Docker / nginx / compose / deploy path / migration ordering / production runtime path

#### SHOULD auto-invoke:
- `solution_designer` — если есть 2+ реалистичных пути и выбор safest path неочевиден
- `integration_guardian` — если меняется внешний provider/API/webhook boundary
- `dependency_guardian` — если реально меняются packages / images / provider deps
- `performance_guardian` — только если perf, latency, memory, token-cost или large-input behaviour являются частью задачи

#### MAY invoke по узкому scope:
- `planner_guardian` — если пользователь явно просит план или работа распадается на несколько коммитных фаз
- `runtime_guardian` — если меняются startup/shutdown/health/lifecycle semantics
- `error_monitoring_guardian` — если меняется exception taxonomy, alerting или failure visibility

#### Stop rule:
- если после первого pass safe path выбран, инварианты ясны и validation plan очевиден, новых субагентов больше не добавлять

#### NEVER auto-invoke:
- `code_review` — до появления diff
- `docs_keeper` — в начале задачи
- `policy_guardian` и `compliance_guardian` — без явного policy/regulatory scope
- `api_versioning_guardian` — без breaking compatibility или migration window
- `audit_guardian`, `backup_guardian`, `feature_flag_guardian`, `usability_guardian` — если их surface не является прямой частью задачи
- одновременно `solution_designer` и `debug_investigator` — "на всякий случай"

#### Phase-based вызовы:
- `test_planner`, `code_review`, `docs_keeper` не являются стартовым bundle и обычно вызываются после реализации или на closure stage

#### Special pair rules:
- `security_guardian + devops_release` — нормальная пара только для release/security/runtime surface
- `devops_release + deployment_guardian` — только если кроме release risk реально меняется deploy automation / rollback flow
- `contracts_guardian + api_versioning_guardian` — только когда кроме контракта реально встаёт вопрос версионирования и backward compatibility migration

#### Запрещённый анти-паттерн:
- “задача high-risk, значит запускаем всех субагентов”
- “задача cross-module, значит нужен хотя бы один субагент”
- “задача cross-layer, значит на старте нужны два субагента”

---

### 🔥 Когда orchestration mode обязателен

* меняется API payload или WebSocket flow
* меняется `/result/{task_id}` или status lifecycle
* меняется extraction / OCR / fallback / confidence
* меняется scoring / explainability
* меняется persistence / history / JSON shape
* задача затрагивает backend + frontend
* причина бага неочевидна
* есть риск silent regression
* задача требует investigation перед кодом
* задача связана с release / security / runtime

---

### ⛔ Когда orchestration mode НЕ нужен

* задача затрагивает 1–2 файла
* нет изменения контрактов
* нет cross-layer эффекта
* решение очевидно
* low-risk правка: typo, logger, type hint, локальный фикс

---

### 👥 Доступные субагенты

#### Core orchestration
* `solution_designer` — выбор safest implementation path до кодинга
* `debug_investigator` — расследование багов и поиск root cause
* `contracts_guardian` — HTTP API, WebSocket, payload shape, status transitions, contract surface
* `test_planner` — validation plan, regression checks, fast/local и full/pre-merge проверки

#### Product-domain specialists
* `extractor` — PDF ingestion, OCR, extraction pipeline, confidence, fallback
* `frontend_scout` — frontend consumers, typings, UI states, WebSocket impact
* `scoring_guardian` — ratios, scoring logic, normalization, explainability
* `db_persistence` — persistence, migrations, history, JSON shape, lifecycle статусов
* `api_contracts` — legacy product-contract deep-dive spec; companion к `contracts_guardian`

#### Finish / governance / release guards
* `code_review` — review реализации после изменений
* `docs_keeper` — sync документации, update ritual, knowledge capture
* `planner_guardian` — планирование multi-phase работ, sequencing, checkpoints
* `security_guardian` — auth, upload, config, secrets, exposure, security risks
* `policy_guardian` — внутренние policy/process constraints и governance rules
* `compliance_guardian` — regulatory / compliance constraints
* `runtime_guardian` — runtime behaviour, health, monitoring semantics
* `performance_guardian` — latency, memory, CPU, hotspots
* `error_monitoring_guardian` — exception classes, alerting, error taxonomy
* `audit_guardian` — audit logs, traceability, change accountability
* `integration_guardian` — внешние сервисы, provider APIs, webhooks
* `data_integrity_guardian` — data invariants, consistency, migration safety
* `dependency_guardian` — dependency changes, compatibility, vulnerability surface
* `feature_flag_guardian` — feature flags и rollout control
* `api_versioning_guardian` — versioning, compatibility windows, migration paths
* `backup_guardian` — backup / restore / recoverability
* `devops_release` — Docker, runtime, deploy, nginx, release risks
* `deployment_guardian` — deploy automation, rollback, rollout mechanics
* `usability_guardian` — UX/UI friction, usability impact для frontend flows

Полные правила, зоны ответственности и форматы ответов каждого субагента находятся в `.agent/subagents/`.

---

### 📌 Когда использовать субагентов

Используй субагентов только если задача:

* затрагивает несколько слоёв
* требует исследования до реализации
* связана с неочевидной логикой или риском регрессий
* может быть безопасно декомпозирована на независимые read-only подзадачи

Не использовать субагентов, если задача:

* локальная и low-risk
* требует маленького очевидного изменения
* write-heavy и затрагивает пересекающиеся файлы
* не требует synthesis перед кодом

Дополнительно:

* `cross-module` сам по себе не является trigger на делегацию
* не начинай с более чем 1 субагента без явной причины
* не подключай phase-based субагентов (`test_planner`, `code_review`, `docs_keeper`) в стартовый bundle
* если есть выбор между `solution_designer` и `debug_investigator`, по умолчанию бери одного, а не обоих
* не зови `contracts_guardian`, если внешний контракт не меняется
* governance/release guard-ы без явного scope (`policy_guardian`, `compliance_guardian`, `audit_guardian`, `backup_guardian`, `api_versioning_guardian`) считаются explicit opt-in, а не default helpers
* если orchestration mode уже покрыт локальным synthesis и external read-only pass не даёт новой информации, не зови субагента формально "для галочки"

---

### 🧩 Synthesis обязателен

Перед началом реализации агент ОБЯЗАН сформировать synthesis:

* какие файлы реально затронуты
* какие инварианты должны сохраниться
* какие риски наиболее вероятны
* какие контракты или поля нельзя ломать
* какой минимальный safe path выбран

Без synthesis нельзя переходить к коду.

---

### 🚫 Запрещено

* начинать код до завершения orchestration для сложных задач
* пропускать synthesis
* игнорировать вывод субагентов
* запускать субагентов формально, без использования результатов
* делать частичную реализацию без полного анализа
* делегировать write-heavy реализацию в пересекающихся файлах

---

### 💬 Формат orchestration ответа

```text
🧠 Orchestration:
- workflow:
- используемые субагенты:
- причина выбора:

📊 Findings:
- [subagent]: ...
- [subagent]: ...

🧩 Synthesis:
- затронутые файлы:
- инварианты:
- риски:
- минимальный safe path:

✏️ Implementation:
- что именно меняется

🧪 Validation:
- какие проверки обязательны
```

---

### 🧠 Ключевая директива

Если задача сложнее `local-low-risk`:

**НЕ начинай код сразу.
Сначала: classify → delegate → wait → synthesize → implement.**

```
