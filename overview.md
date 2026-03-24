# NeoFin AI — Обзор проекта

## Статус
- **Фаза**: Phase 1 (MVP) — числовой анализ готов, NLP-рекомендации реализованы и подключены
- **Последний коммит**: `f01e45d` — feat: data-driven recommendations (`src/analysis/recommendations.py`, 420 строк, 29 тестов, подключено в `src/tasks.py`) — март 2026
- **Последняя сессия**: 2026-03-24 — создана инфраструктура AI-агента (`.agent/`): `AGENTS.md`, `architecture.md`, `overview.md`, `local_notes.md`, `PROJECT_LOG.md`, шаблоны
- **Контекст**: Полная архитектура в `.agent/architecture.md`. Читать его перед любой разработкой.

---

## Что работает
✅ **POST /upload** — валидация PDF (magic header, ≤50MB), SpooledTemporaryFile, BackgroundTask, немедленный ответ с `task_id`
✅ **GET /result/{task_id}** — polling статуса из БД; frontend поллит каждые 2000ms
✅ **PDF extraction** — PyPDF2 (текст), camelot/pdfplumber (таблицы), pytesseract (OCR для сканов)
✅ **Financial ratios** — 5 коэффициентов (`ratios.py`); RU-ключи → EN через `RATIO_KEY_MAP` в `tasks.py`
✅ **Integral scoring** — скоринг 0–100, risk_level, factors (`scoring.py` + `_build_score_payload()`)
✅ **NLP analysis** — риски и ключевые факторы через `ai_service.py` (GigaChat → Qwen → Ollama → graceful degrade)
✅ **Recommendations** — `src/analysis/recommendations.py`: 3–5 рекомендаций с явными ссылками на метрики; timeout 65s; fallback при недоступности AI; подключено в `tasks.py`
✅ **БД** — PostgreSQL 16, SQLAlchemy async, 2 миграции Alembic (`analyses` + индексы)
✅ **Auth** — X-API-Key header; `DEV_MODE=1` отключает проверку
✅ **CI/CD** — GitHub Actions: lint → test → security → build
✅ **Docker** — backend, frontend/nginx, db, db_test, ollama
✅ **Инфраструктура агента** — `.agent/` с AGENTS.md, мета-файлами и шаблонами

---

## Что разрабатывается
🔄 **frontend/src/components/Layout.tsx** — файл не создан, импортируется в `App.tsx` → приложение не компилируется [CRITICAL]
🔄 **frontend/src/components/ProtectedRoute.tsx** — то же [CRITICAL]
🔄 **AnalysisHistory.tsx** — страница есть, но использует `mockHistory`; реальных API-вызовов нет [HIGH]
🔄 **Auth.tsx** — `handleSubmit` сохраняет API key без валидации на backend [HIGH]
🔄 **nlp_analysis.py** — модуль реализован, но вызов закомментирован в `tasks.py` [MEDIUM]

---

## Что будет дальше
❌ Создать `Layout.tsx` и `ProtectedRoute.tsx` — разблокирует компиляцию frontend (CRITICAL, делать первым)
❌ Подключить `nlp_analysis.py` в `tasks.py` (раскомментировать вызов)
❌ Реализовать реальный API для `AnalysisHistory` (эндпоинт GET /analyses + frontend)
❌ Валидация API key на backend в `Auth.tsx`
❌ Устранить дублирование `types.ts` vs `interfaces.ts` (оставить только `interfaces.ts`)
❌ Celery + Redis вместо BackgroundTasks (для персистентности задач при рестарте)
❌ WebSocket / SSE вместо polling
❌ Trend data в `DetailedReport.tsx` из реального API (сейчас "+2.4%" захардкожено)

---

## Известные ограничения
- BackgroundTasks in-process: задача теряется при рестарте сервера, `status` зависает в `"processing"`
- SlowAPI rate limiter — in-memory, не работает при нескольких инстансах
- Polling 2000ms × N пользователей = N/2 req/s к БД (захардкожено в `usePdfAnalysis.ts`)
- camelot-py + Tesseract + Poppler — ~500MB в Docker-образе, нельзя убрать без замены PDF-стека
- GigaChat требует кастомный SSL CA bundle и российский аккаунт Sber
- `frontend/src/api/types.ts` дублирует `interfaces.ts` с расхождениями — использовать только `interfaces.ts`
- MAX_PDF_PAGES=100, MAX_FILE_SIZE=50MB, AI_TIMEOUT=120s — менять только везде одновременно

---

## Архитектура в двух словах

```
React/Mantine (polling) → FastAPI routers → tasks.py (оркестратор)
  → pdf_extractor → ratios → scoring → recommendations → nlp_analysis
  → ai_service (GigaChat | Qwen | Ollama | None)
  → crud.py → PostgreSQL
```

Детали: `.agent/architecture.md` — структура слоёв, data flow, паттерны, критичные файлы, технический долг.
Ключевой файл оркестрации: `src/tasks.py` — содержит `RATIO_KEY_MAP`, `_build_score_payload()`, порядок вызовов pipeline.
