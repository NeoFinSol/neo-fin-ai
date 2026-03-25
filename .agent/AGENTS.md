# AGENTS.md — Правила работы с проектом NeoFin AI
<!-- Версия: 1.3 | Обновлено: 2026-03-25 -->

> Все вспомогательные файлы агента лежат в `.agent/`. При сомнениях — читай их в первую очередь.

---

## 🎯 Основные принципы

- **Архитектура**: Layered (routers → tasks → analysis pipeline → ai_service → db/crud). Зависимости строго однонаправленные — сверху вниз.
- **Лимит контекста**: при приближении к 90k токенов — предложить сжатие.
- **Коммиты**: после каждой завершённой логической единицы (фича, багфикс, рефакторинг модуля).
- **Язык кода**: английский (имена, комментарии в коде). Документация и мета-файлы — русский.
- **Тесты**: pytest; писать после реализации; обязательны для новых функций в `src/analysis/` и `src/core/`.
- **Приоритет правил при конфликте**: `AGENTS.md` > линтеры (`.flake8`, `ruff`) > устные инструкции > общие best practices.
- **Решение багов**: всегда использовать архитектурно чистое решение. Не хакать симптом — устранять корневую причину. Если есть выбор между быстрым костылём и правильным решением — выбирать правильное, если пользователь явно не указал иное.
- **Правило первой ошибки**: при первой ошибке в сессии — сразу проверить `.agent/local_notes.md` на похожие проблемы. После устранения — занести в `local_notes.md` и `PROJECT_LOG.md`.

---

## 🏗️ Структура проекта

```
src/
├── app.py              → точка входа FastAPI, middleware, lifespan
├── tasks.py            → оркестратор pipeline; RATIO_KEY_MAP; _build_score_payload()
├── analysis/           → чистые функции: pdf_extractor, ratios, scoring, nlp_analysis, recommendations
├── core/               → ai_service (единственная точка входа к AI), gigachat_agent, agent
├── db/                 → database (lazy engine), crud (единственный файл с SQL), models
├── models/             → schemas (Pydantic), settings (env-переменные)
└── routers/            → upload, result, analyze, system

frontend/src/
├── api/                → client.ts (axios), interfaces.ts (ОСНОВНОЙ контракт), types.ts (НЕ ИСПОЛЬЗОВАТЬ)
├── hooks/              → usePdfAnalysis.ts (polling 2000ms)
├── pages/              → Dashboard, DetailedReport, AnalysisHistory, Auth
└── components/         → Layout.tsx, ProtectedRoute.tsx

.agent/                 → инфраструктура для AI-агента (этот файл + мета-документы)
migrations/versions/    → 0001_create_analyses, 0002_add_indexes

Docker (production):
├── Dockerfile.backend        → multi-stage build (build → runtime)
├── frontend/Dockerfile.frontend → multi-stage build (node → nginx)
├── docker-compose.prod.yml   → production-оркестрация (nginx, backend, db, ollama)
├── nginx.conf                → reverse proxy, rate limiting, gzip, security headers
└── scripts/deploy-prod.sh    → скрипт деплоя (validate → build → migrate → start)
```

---

## 📁 Критичные файлы для контекста

| Файл | Зачем держать в контексте |
|------|--------------------------|
| `.agent/overview.md` | Текущий статус: что работает, что в разработке, приоритеты |
| `.agent/local_notes.md` | Известные баги, воркэраунды, архив решённых проблем |
| `.agent/PROJECT_LOG.md` | История изменений — читать последние 3 записи для быстрого вката |
| `.agent/architecture.md` | Слои, data flow, паттерны, жёсткие лимиты |
| `src/tasks.py` | RATIO_KEY_MAP и _build_score_payload() — маппинг данных backend→frontend |
| `frontend/src/api/interfaces.ts` | Контракт данных frontend; менять синхронно с backend |

> ⚠️ Правило: эти файлы обновляются ПЕРЕД сжатием контекста. Не сжимай контекст без обновления `.agent/overview.md` и `.agent/PROJECT_LOG.md`.

---

## 🧠 Как работать с контекстом

### Когда сжимать:
- Контекст > 90k токенов
- Завершена логическая задача (фича, багфикс, рефакторинг)
- Перед долгим перерывом в работе

### Что делать перед сжатием (строго по порядку):
1. Обновить `.agent/overview.md` — статус, что сделано, что дальше
2. Добавить запись в `.agent/PROJECT_LOG.md` (новые записи — сверху)
3. Если были баги → обновить `.agent/local_notes.md`
4. Удалить из контекста исходный код, оставив только мета-файлы из `.agent/`

### Когда расширять контекст:
- Рефакторинг нескольких связанных модулей
- Анализ кросс-модульных багов
- Онбординг в новую подсистему

> ⚠️ Правило: не держи в контексте исходный код больше чем 4–5 файлов одновременно.

---

## 🔔 Автоматические напоминания

- Каждые 5 сообщений → сообщи: «Контекст: ~XXk токенов. Нужно сжать?»
- После 3 коммитов подряд → предложи обновить `.agent/overview.md`
- При первой ошибке в сессии → проверь `.agent/local_notes.md` на похожие проблемы
- При изменении структуры ответа API → напомни обновить `frontend/src/api/interfaces.ts`

---

## 🛠️ Правила кодирования

### Python (backend):
- Стандарт: PEP 8, ruff (`.ruff_cache/`), flake8 (`.flake8`)
- Именование: `snake_case` для функций/переменных, `PascalCase` для классов, `UPPER_CASE` для констант
- Функции: не длиннее 50 строк; если длиннее — выноси в отдельную функцию
- Типизация: обязательна для всех публичных функций (`def foo(x: int) -> str`)
- Логирование: только `logger = logging.getLogger(__name__)`; никаких `print()`
- Async: все I/O операции — `async`; CPU-bound (PDF, расчёты) — `asyncio.to_thread()`

### TypeScript (frontend):
- Стандарт: TypeScript strict mode
- Типы: использовать только `frontend/src/api/interfaces.ts`; `types.ts` — не трогать
- Компоненты: функциональные, с хуками; никаких class-компонентов

### Архитектурные ограничения:

| Правило | Пример нарушения |
|---------|-----------------|
| ❌ `routers/` не содержат бизнес-логику | `upload.py` вызывает `calculate_ratios()` напрямую |
| ❌ `analysis/*` не импортируют FastAPI/SQLAlchemy | `ratios.py` делает `from fastapi import ...` |
| ❌ SQL только в `src/db/crud.py` | `tasks.py` вызывает `session.execute()` |
| ❌ AI только через `src/core/ai_service.py` | `nlp_analysis.py` импортирует `gigachat_agent` напрямую |
| ❌ `ratios.py` не меняет язык ключей | Добавление EN-ключей в `ratios.py` сломает `RATIO_KEY_MAP` |
| ✅ Новые коэффициенты → добавить в `RATIO_KEY_MAP` в `tasks.py` | |
| ✅ Новые поля ответа → синхронно обновить `interfaces.ts` | |

### Жёсткие лимиты (не менять без тестирования всего pipeline):

```
MAX_PDF_PAGES    = 100       # pdf_extractor.py
MAX_FILE_SIZE    = 50MB      # routers/upload.py
AI_TIMEOUT       = 120s      # agent.py, gigachat_agent.py, ai_service.py — менять везде
NLP_TIMEOUT      = 60s       # asyncio.wait_for в tasks.py
REC_TIMEOUT      = 65s       # asyncio.wait_for в tasks.py
POLLING_INTERVAL = 2000ms    # frontend/src/hooks/usePdfAnalysis.ts

# Docker production
DOCKER_BUILD_CACHE = local   # Dockerfile.backend: кеш между сборками
NGINX_RATE_LIMIT   = 10r/s   # nginx.conf: limit_req_zone rate
```

---

## 🎯 Триггеры действий

| Условие | Действие |
|---------|----------|
| Видишь `TODO` в коде | Проверь `.agent/overview.md#Что-будет-дальше` — возможно, задача уже запланирована |
| Ошибка `429 Too Many Requests` | Проверь `SlowAPI` rate limiter в `src/app.py`; лимит в `RATE_LIMIT` env |
| Ошибка `401 Unauthorized` | Проверь `DEV_MODE` в `.env`; при `DEV_MODE=1` auth отключена |
| Меняешь структуру ответа `/result/{id}` | Обязательно обнови `frontend/src/api/interfaces.ts` |
| Добавляешь новый коэффициент в `ratios.py` | Добавь маппинг в `RATIO_KEY_MAP` в `tasks.py` |
| Меняешь `AI_TIMEOUT` | Менять в трёх файлах: `agent.py`, `gigachat_agent.py`, `ai_service.py` |
| Видишь `status` зависший в `"processing"` | BackgroundTask упал; см. `.agent/local_notes.md` — известное ограничение |
| Ошибка SSL при GigaChat | Проверь `GIGACHAT_SSL_VERIFY` env и CA bundle |
| **Production деплой** | Используй `scripts/deploy-prod.sh` или `docker-compose -f docker-compose.prod.yml` |
| **Docker build ошибка** | Проверь `.dockerignore` и `frontend/.dockerignore` — лишние файлы могут сломать сборку |
| **Nginx 502 Bad Gateway** | Backend не запустился; проверь `docker-compose logs backend` и health check |
| **Миграции не применяются** | Запусти вручную: `docker-compose -f docker-compose.prod.yml run --rm backend-migrate` |

---

## ✅ Чеклист перед коммитом

```
[ ] Код соответствует PEP 8 (ruff/flake8 без ошибок)
[ ] Нет print() — только logger.*()
[ ] Все новые публичные функции имеют type hints и docstring
[ ] Нет закомментированных блоков кода (кроме задокументированных в local_notes.md)
[ ] Если менялся backend-ответ → interfaces.ts обновлён
[ ] Если добавлен новый ratio → RATIO_KEY_MAP обновлён
[ ] Тесты для новой логики написаны и проходят (pytest --run)
[ ] .agent/overview.md и .agent/PROJECT_LOG.md обновлены
[ ] Если менялись Docker-файлы → проверь сборку: docker-compose -f docker-compose.prod.yml build
[ ] Если менялись production-файлы → проверь .env.example на наличие новых переменных
```

---

## ⚙️ Режимы работы агента

| Режим | Когда включать | Что делает |
|-------|---------------|------------|
| `🔍 Исследование` | Новый модуль, непонятный баг, онбординг | Читает мета-файлы и исходники, задаёт уточняющие вопросы перед действием |
| `✏️ Кодирование` | Чёткая задача с известным контекстом | Минимум вопросов, максимум кода, следует чеклисту |
| `🧹 Рефакторинг` | Улучшение структуры без изменения поведения | Предлагает изменения, ждёт явного подтверждения перед применением |
| `🗜️ Сжатие` | Конец сессии, контекст > 90k токенов | Обновляет мета-файлы, формирует сводку, чистит контекст |

Переключение: пользователь пишет `Режим: [название]` или агент предлагает сам при наступлении условия.

---

## 💬 Формат ответов на задачи

При предложении решения структурируй ответ:

```
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

```
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
```
тип(scope): краткое описание (до 72 символов)

[опционально] Подробности если нужны.
```
Типы: `feat`, `fix`, `refactor`, `test`, `docs`, `chore`
Примеры:
- `feat(ratios): add quick_ratio and absolute_liquidity coefficients`
- `fix(tasks): update RATIO_KEY_MAP for new ratios keys`
- `docs(agent): update overview.md after NLP pipeline fix`

---

## 🚫 Чего НЕ делать

- ❌ Не меняй архитектуру слоёв без явного запроса пользователя
- ❌ Не удаляй комментарии, объясняющие «почему», а не «что»
- ❌ Не игнорируй `.agent/local_notes.md` при работе с похожим кодом
- ❌ Не предлагай сжатие контекста без обновления мета-файлов
- ❌ Не используй `frontend/src/api/types.ts` — только `interfaces.ts`
- ❌ Не добавляй EN-ключи в `ratios.py` — маппинг только в `tasks.py`
- ❌ Не вызывай `gigachat_agent` или `agent` напрямую — только через `ai_service.py`
- ❌ Не пиши SQL вне `src/db/crud.py`
- ❌ Не меняй один таймаут AI — меняй все три файла сразу
- ❌ Не запускай `npm run dev` или `uvicorn` как блокирующие команды в сессии
- ❌ Не копируй `.env` в Docker-образ (используй `env_file` в docker-compose)
- ❌ Не меняй production Dockerfile без проверки сборки: `docker-compose -f docker-compose.prod.yml build`
- ❌ Не запускай backend от root в Docker (используй `appuser` в Dockerfile.backend)

---

## 🆘 Если что-то непонятно

1. Прочитай `.agent/overview.md` и `.agent/PROJECT_LOG.md` (последние 3 записи)
2. Проверь `.agent/local_notes.md` — возможно, проблема уже описана
3. Если неясно → задай уточняющий вопрос, не предполагай
4. При конфликте правил → приоритет по иерархии выше; сообщи пользователю
