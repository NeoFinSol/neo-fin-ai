# NeoFin AI — Обзор проекта

## Статус
- **Фаза**: Phase 1 (MVP) — neofin-competition-release завершён; фича llm-financial-extraction реализована полностью
- **Последний коммит**: `fix(pdf): harden OCR fallback extraction`
- **Последняя сессия**: 2026-03-28 — продолжена третья волна product-аудита: после LLM/NLP compaction и OCR hardening добавлен corpus-driven regression pack для сложных table layouts (year columns, note columns, RSBU line codes, garbled labels, OCR pseudo-tables).
- **Последнее обновление документации**: 2026-03-28 — из `AGENTS.md` вынесены операционные блоки в `.agent/architecture.md`, `.agent/checklists.md`, `.agent/modes.md`
- **Контекст**: Полная архитектура в `.agent/architecture.md` и `docs/ARCHITECTURE.md`. Читать перед любой разработкой.

---

✅ **Autopilot migration complete** — reusable Autopilot foundation, runtime diagnostics, machine-readable model selection и roadmap ownership перенесены в отдельный репозиторий `E:\codex-autopilot`.
✅ **NeoFin cleanup** — основной репозиторий больше не хранит experimental Autopilot spike как активный рабочий слой; здесь остаются только продуктовый код, human-readable agent workflow и исторические записи в `PROJECT_LOG.md`.

✅ **Qwen Regression Fixes 2** — исправлены все 10 багов: `_normalize_number` (Unicode-минус), `_extract_first_numeric_cell` (4-значные ячейки), `analyze_narrative` (пустой текст в LLM), `extract_text_from_scanned` (MAX_OCR_PAGES=50), `translate_ratios` (утечка ключей), `_format_metric_value` (отрицательные числа), `_parse_recommendations_response` (дедупликация + f-строки), `generate_recommendations` (timeout=90), `_log_missing_data` (f-строки). 20/20 тестов зелёные.

✅ **Hook System** — 8 хуков: architecture-guard, agents-rules-reminder, python-lint-on-save (flake8 per-file), review-refactor-verify, run-tests-after-task, update-session-docs, generate-commit-message, check-local-notes-before-task

✅ **Scale factor в parse_financial_statements_with_metadata** — `_detect_scale_factor` теперь вызывается внутри функции, scale применяется к монетарным метрикам при сборке результата. Корень ROA=2290329% устранён.
✅ **Scoring аномалии** — `_ANOMALY_LIMITS` в `scoring.py` блокирует аномальные коэффициенты от нормализации в "идеал".
✅ **NLP токены** — `nlp_analysis.py` использует `is_clean_financial_text` + `clean_for_llm` перед LLM.
✅ **Unicode minus** — `_normalize_number` обрабатывает U+2212 и trailing minus.
✅ **Приоритизация источников** — `_raw_set()` заменяет прямые записи в `raw`, table_exact побеждает text_regex.
✅ **OOM при OCR** — постраничная обработка в `extract_text_from_scanned`.
✅ **Audit Wave 1** — закрыты подтверждённые product bugs:
  - frontend `interfaces.ts` синхронизирован с `critical` risk level
  - polling fallback в `AnalysisContext.tsx` снова читает `data` из `/result/{task_id}`
  - `DetailedReport.tsx` и `AnalysisHistory.tsx` корректно отображают `critical`
  - `/analyses/{task_id}` теперь возвращает inner `data`, а не вложенный root payload
  - `tasks.py` снова шлёт промежуточные WebSocket статусы `extracting/scoring/analyzing`
  - `process_multi_analysis()` больше не отдаёт неподдерживаемый статус `completed_with_errors`
  - `pdf_extractor.py` больше не отбрасывает table-extracted малые monetary values и поддерживает mock-friendly OCR fallback
  - `Dockerfile.backend` копирует `entrypoint.sh`, что снимает риск падения `backend-migrate`
✅ **Audit Wave 2** — production Docker hardening:
  - `docker-compose.prod.yml` теперь собирает `nginx` напрямую из `frontend/Dockerfile.frontend`
  - production deploy больше не зависит от локального bind mount `frontend/dist`
  - `frontend/nginx.prod.conf` получил rate limiting, CSP, proxy error page и более жёсткий proxy path
  - `scripts/deploy-prod.sh` переведён на `docker compose` и добавляет `config` validation перед build
  - docs и agent-checklists синхронизированы с новым deploy path
✅ **Audit Wave 3** — LLM token optimization and test hardening:
  - `src/analysis/llm_extractor.py` теперь выкидывает year/page noise, дедуплицирует и ранжирует строки по финансовому сигналу
  - `extract_with_llm()` больше не отказывается от длинного отчёта сразу: вход сначала compact-ится до token budget
  - `chunk_text()` корректно режет монолитные oversized paragraphs
  - `src/analysis/nlp_analysis.py` формирует компактный narrative excerpt до вызова `ai_service`
  - `src/analysis/recommendations.py` переведён на compact JSON prompt context
  - `tests/test_nlp_analysis.py` и связанные LLM tests синхронизированы с актуальным `ai_service` contract
  - `src/analysis/pdf_extractor.py` теперь использует newline-safe keyword-window extraction для section totals и nearby numbers
  - OCR TypeError fallback больше не может молча обойти `MAX_OCR_PAGES`
  - `tests/test_pdf_extractor.py` покрывает anti-merge и fallback page-cap regressions
  - `src/analysis/pdf_extractor.py` пропускает year markers в `_extract_first_numeric_cell()`, чтобы multi-period rows не превращали `2023` в extracted metric
  - `tests/data/pdf_regression_corpus.json` и `tests/test_pdf_regression_corpus.py` фиксируют corpus pack для сложных table layouts

## Что работает
✅ **POST /upload** — валидация PDF (magic header, ≤50MB), SpooledTemporaryFile, BackgroundTask, немедленный ответ с `task_id`
✅ **WebSocket Updates** — real-time уведомления о статусе задач через `/ws/{id}`; внедрён `ConnectionManager` (Singleton)
✅ **PDF extraction** — PyPDF2 (текст), camelot/pdfplumber (таблицы), pytesseract (OCR для сканов); улучшена детекция сканов через проверку `/Image` объектов
✅ **OCR Regression Guard** — multiline-safe numeric helpers и page-cap enforcement в fallback path защищают от silent giant-number regressions
✅ **Complex Table Layout Guard** — corpus pack защищает note/year columns, RSBU line-code layouts, garbled labels и OCR pseudo-tables
✅ **Financial ratios** — 13 коэффициентов (4 группы: ликвидность, рентабельность, устойчивость, активность); RU-ключи → EN через `translate_ratios()`
✅ **Integral scoring** — скоринг 0–100, risk_level (пороги 75/55/35, уровни: low/medium/high/critical), factors, normalized_scores; добавлено поле `confidence_score` для оценки полноты данных
✅ **Scoring factors** — осмысленные описания факторов с ссылками на бенчмарки (вместо просто "Значение: 1.23")
✅ **4-уровневая система риска** — low (≥75) / medium (55–74) / high (35–54) / critical (<35) для более гранулярной оценки
✅ **NLP analysis** — риски и ключевые факторы через `ai_service.py` (GigaChat → DeepSeek → Ollama → graceful degrade)
✅ **AI Agents Refactoring** — внедрён `BaseAIAgent`, исправлена утечка ресурсов в GigaChat (Singleton ClientSession), внедрены экспоненциальные ретраи
✅ **Recommendations** — `src/analysis/recommendations.py`: 3–5 рекомендаций с явными ссылками на метрики; outer timeout 90s; fallback при недоступности AI; подключено в `tasks.py`
✅ **LLM Prompt Budgeting** — extractor/NLP/recommendations используют deterministic prompt compaction: dedupe, ranking по signal, trimming до budget без изменения внешнего API
✅ **GET /analyses** — список анализов с пагинацией (page, page_size ≤ 100), сортировка по created_at DESC, auth X-API-Key
✅ **Masking** — `src/utils/masking.py`: чистая функция `mask_analysis_data(data, demo_mode)`, применяется во всех трёх эндпоинтах при `DEMO_MODE=1`
✅ **AnalysisHistory.tsx** — подключена к реальному API (`GET /analyses`), пагинация Mantine, skeleton/error states
✅ **DetailedReport.tsx** — BarChart из реальных `result.ratios`, цветовое кодирование по порогам, WebSocket-синхронизация
✅ **БД** — PostgreSQL 16, SQLAlchemy async, 2 миграции Alembic (`analyses` + индексы)
✅ **Auth.tsx** — pre-flight `GET /api/analyses` с введённым ключом
✅ **CI/CD** — GitHub Actions: lint → test → security → build
✅ **Docker** — backend, frontend/nginx, db, db_test, ollama
✅ **Regex fallback** — извлечение 15 метрик через regex patterns (перенесено в `analysis` слой), если camelot не извлёк таблицы
✅ **Тесты** — подтверждённые локальные прогоны после audit wave 1:
  - `tests/test_scoring.py`, `tests/test_pdf_extractor.py`, `tests/test_api.py` → 18 passed
  - `tests/test_analyses_router.py`, `tests/test_tasks.py` → 27 passed
  - `tests/test_llm_extractor.py`, `tests/test_llm_extractor_properties.py`, `tests/test_nlp_analysis.py`, `tests/test_nlp_analysis_coverage.py`, `tests/test_recommendations.py` → 128 passed
  - после PDF hardening: `tests/test_pdf_extractor.py` → 8 passed; `tests/test_scoring.py tests/test_pdf_extractor.py tests/test_api.py` → 21 passed
  - после corpus/regression dataset: `tests/test_pdf_regression_corpus.py` → 7 passed; `tests/test_pdf_extractor.py tests/test_pdf_regression_corpus.py tests/test_scoring.py tests/test_api.py` → 28 passed
  - legacy `tests/test_tasks_coverage.py` остаётся устаревшим compatibility-suite и не отражает текущий product contract
✅ **Production Docker** — `Dockerfile.backend` (multi-stage), `Dockerfile.frontend` (multi-stage), `docker-compose.prod.yml`, `nginx.conf`, `scripts/deploy-prod.sh`
✅ **Production Frontend Image** — compose собирает frontend/Nginx образ сам, без внешнего `frontend/dist`
✅ **Code Quality** — полная чистка неиспользуемых импортов, исправление линтера, переход на Pydantic-settings для управления env

---


## Исправления сессии 2026-03-27 (Большой коммит: scoring + LLM extraction + WebSocket + cleanup)
✅ **Коммит `b8ffaef`** — feat(scoring): enhance business model with contextual descriptions and 4-level risk system
✅ **Scoring Model Refinement** — 4-уровневая система риска (low/medium/high/critical), осмысленные описания факторов с ссылками на бенчмарки
✅ **LLM Financial Extraction** — полная реализация llm_extractor.py с chunking, anomaly detection, fallback merging
✅ **WebSocket Integration** — ws_manager.py (ConnectionManager), useAnalysisSocket.ts hook, real-time task updates
✅ **AI Agents Refactoring** — BaseAIAgent с Singleton ClientSession, исправлена утечка ресурсов в GigaChat
✅ **Pipeline Refactoring** — tasks.py декомпозирован на фазы (extraction, scoring, AI, finalize)
✅ **Repository Cleanup** — удалены env/, test scripts, IDE files, hypothesis cache; очищен .gitignore
✅ **Documentation Updates** — BUSINESS_MODEL.md, ROADMAP.md, ARCHITECTURE.md, README.md обновлены
✅ **Kiro Infrastructure** — добавлены .kiro/hooks/, .kiro/specs/, .kiro/steering/ для автоматизации и правил
✅ **Статистика** — 335 файлов изменено, 28177 строк добавлено, 13712 удалено

## Исправления сессии 2026-03-27 (LLM Financial Extraction — таски 4–11 + hotfixes)
✅ **`src/models/settings.py`** — добавлены 4 поля: `llm_extraction_enabled`, `llm_chunk_size`, `llm_max_chunks`, `llm_token_budget` с валидаторами.
✅ **`src/tasks.py`** — интегрирован `_try_llm_extraction`, inline-импорты вынесены на уровень модуля.
✅ **`src/analysis/nlp_analysis.py`** — заменён inline-промпт на `LLM_ANALYSIS_PROMPT`.
✅ **`tests/test_llm_extractor.py`** — 22 unit-теста.
✅ **`tests/data/llm_responses/`** — 5 fixture-файлов.
✅ **`.env.example`** — добавлена секция LLM Extraction.
✅ **`src/analysis/pdf_extractor.py`** — `_is_glyph_encoded()` (детектор кастомных шрифтов → OCR), `_get_poppler_path()` (Windows autodetect), порог `_normalize_number` снижен до 16 цифр, `_is_valid_financial_value` до 1e13.
✅ **`requirements.txt`** — добавлен `ghostscript~=0.8.1`.
✅ **`frontend/src/context/AnalysisContext.tsx`** — `MAX_POLLING_ATTEMPTS` = 600 (20 минут для OCR).
✅ **Agent Hooks** — созданы 4 хука: Python Lint on Save, Run Tests After Task, Architecture Guard, AGENTS.md Rules Reminder.
✅ **Poppler + ghostscript** — установлены локально.

## Исправления сессии 2026-03-27 (LLM Financial Extraction — таски 4-11 + hotfixes)
- src/models/settings.py: 4 новых поля LLM extraction с валидаторами
- src/tasks.py: _try_llm_extraction интегрирован, inline-импорты вынесены
- src/analysis/nlp_analysis.py: inline-промпт заменён на LLM_ANALYSIS_PROMPT
- tests/test_llm_extractor.py: 22 unit-теста
- tests/data/llm_responses/: 5 fixture-файлов
- .env.example: секция LLM Extraction
- src/analysis/pdf_extractor.py: _is_glyph_encoded, _get_poppler_path, порог 16 цифр и 1e13
- requirements.txt: ghostscript~=0.8.1
- frontend/src/context/AnalysisContext.tsx: MAX_POLLING_ATTEMPTS=600
- Agent Hooks: 4 хука созданы
- Poppler + ghostscript установлены локально

## Исправления сессии 2026-03-27 (LLM Financial Extraction — таски 1–3)
✅ **`src/core/prompts.py`** — создан: `LLM_EXTRACTION_PROMPT` (защита от prompt injection, 15 метрик с RU/EN синонимами, правила confidence, OCR-артефакты) и `LLM_ANALYSIS_PROMPT` (российские нормативные пороги, формат JSON-ответа).
✅ **`src/analysis/llm_extractor.py`** — реализован полностью: `_normalize_number_str`, `_apply_anomaly_check`, `parse_llm_extraction_response`, `chunk_text`, `merge_extraction_results`, `extract_with_llm`. Все функции покрыты property-тестами.
✅ **`tests/test_llm_extractor_properties.py`** — 19 property-тестов (Hypothesis): Properties 1–6, 8–11. Все зелёные.
✅ **Checkpoint таска 3** — пройден: 19/19 passed, регрессий нет.

## Исправления сессии 2026-03-27 (OCR + Qwen regression)
✅ **OCR Giant Number Bug** (pdf_extractor.py) — исправлен: паттерн `\d[\d\s,\.]*\d` заменён на строгий `\d{1,3}(?:[ \t\xa0]\d{3})+` (без `\n`), что предотвращает склейку чисел с разных строк OCR-текста в монстров типа `1234567890123344444`.
✅ **_normalize_number guard** (pdf_extractor.py) — добавлена защита: строки с >18 цифрами отклоняются как артефакты парсинга.
✅ **_NUMBER_PATTERN** (pdf_extractor.py) — обновлён: использует `[ \t\xa0]` вместо `\s`, не пересекает переносы строк.
✅ **_is_valid_financial_value порог** (pdf_extractor.py) — поднят с `1e14` до `1e15` (корректный верхний предел).
✅ **_extract_metrics_with_regex алиас** (tasks.py) — добавлен алиас для совместимости с тестами (БАГ 10).
✅ **MAX_POLLING_ATTEMPTS** (AnalysisContext.tsx) — исправлен с 60 на 15 согласно спецификации.
✅ **f-строки в логах** (pdf_extractor.py) — заменены на `%`-форматирование.
✅ **Exploratory тесты** (test_qwen_regression_exploratory.py) — БАГ 1 и БАГ 8 помечены `xfail` (баги исправлены).

✅ **WebSocket** (ws_manager.py + useAnalysisSocket.ts) — внедрена система real-time обновлений.
✅ **Refactoring** (tasks.py) — проведена декомпозиция "God Method" на фазы.
✅ **AI Core** (base_agent.py) — внедрён базовый класс и Singleton-сессии для всех провайдеров.
✅ **Linter & Imports** (app.py, tasks.py, agents) — исправлено более 30 ошибок импортов и предупреждений линтера.
✅ **Config** (settings.py) — централизованная загрузка `.env` через Pydantic.
✅ **БАГ 15** (gigachat_agent.py) — исправлен: внедрён Singleton `ClientSession`, убрана утечка ресурсов.
✅ **БАГ 16** (scoring.py) — улучшен: добавлено поле `confidence_score` для визуализации полноты финансовых данных.
✅ **БАГ 17** (pdf_extractor.py) — исправлен: улучшена детекция сканированных PDF через проверку наличия `/Image`.
✅ **БАГ 18** (analyze.py + pdf_extractor.py) — исправлен: regex-экстракция перенесена в слой анализа.
✅ **ТЕХ. ДОЛГ** (types.ts) — исправлен: удалён дублирующий файл `types.ts` на фронтенде.

---

## Что будет дальше
❌ Celery + Redis вместо BackgroundTasks (для персистентности задач при рестарте)
❌ Интерактивные правки OCR (позволить пользователю корректировать извлечённые данные)
❌ Сравнение с бенчмарками отраслей (OKVED)
❌ Переезд на S3/MinIO для хранения временных PDF
❌ Тестирование production-деплоя на VPS
❌ Настройка HTTPS (SSL-сертификаты)

---

## Известные ограничения
- BackgroundTasks in-process: задача теряется при рестарте сервера, `status` зависает в `"processing"`
- SlowAPI rate limiter — in-memory, не работает при нескольких инстансах
- Polling 2000ms × N пользователей = N/2 req/s к БД (захардкожено в `usePdfAnalysis.ts`)
- camelot-py + Tesseract + Poppler — ~500MB в Docker-образе, нельзя убрать без замены PDF-стека
- GigaChat требует кастомный SSL CA bundle и российский аккаунт Sber
- MAX_PDF_PAGES=100, MAX_FILE_SIZE=50MB, AI_TIMEOUT=120s — менять только везде одновременно
- **Production**: миграции запускаются отдельным сервисом `backend-migrate` перед стартом `backend`

---

## Архитектура в двух словах

```
React/Mantine (polling) → FastAPI routers → tasks.py (оркестратор)
  → pdf_extractor → ratios → scoring → recommendations → nlp_analysis
  → ai_service (GigaChat | DeepSeek | Ollama | None)
  → crud.py → PostgreSQL
```

Детали: `.agent/architecture.md` — структура слоёв, data flow, паттерны, критичные файлы, технический долг.
Ключевой файл оркестрации: `src/tasks.py` — содержит `RATIO_KEY_MAP`, `_build_score_payload()`, порядок вызовов pipeline.

---

## Production Architecture

```
Internet → nginx:80/443 (reverse proxy, rate limiting, gzip)
              ↓
        backend:8000 (internal network only)
         ↓        ↓
    db:5432   ollama:11434 (optional, profile-based)
```

**Сервисы:**
- `nginx` — единственный публичный сервис, reverse proxy, статика frontend
- `backend` — FastAPI, не exposed наружу, health check на `/system/health`
- `db` — PostgreSQL 16, internal only, health check через `pg_isready`
- `backend-migrate` — Alembic миграции, run once перед стартом backend
- `ollama` — local LLM, optional, через `--profile ollama`

**Файлы:**
- `Dockerfile.backend` — multi-stage (build → runtime), non-root user
- `frontend/Dockerfile.frontend` — multi-stage (node → nginx)
- `docker-compose.prod.yml` — production orchestration
- `nginx.conf` — reverse proxy, rate limiting (10r/s), security headers
- `scripts/deploy-prod.sh` — deploy script (validate → build → migrate → start)

