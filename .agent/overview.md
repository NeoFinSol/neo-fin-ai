# NeoFin AI — Обзор проекта

## Статус
- **Фаза**: Phase 1 (MVP) — neofin-competition-release завершён
- **Последний коммит**: `refactor(analysis): lift analysis state to AnalysisContext; remove usePdfAnalysis hook`
- **Последняя сессия**: 2026-03-25 — docs/ARCHITECTURE.md написан (Task 10 завершён)
- **Контекст**: Полная архитектура в `.agent/architecture.md` и `docs/ARCHITECTURE.md`. Читать перед любой разработкой.

---

## Что работает
✅ **POST /upload** — валидация PDF (magic header, ≤50MB), SpooledTemporaryFile, BackgroundTask, немедленный ответ с `task_id`
✅ **GET /result/{task_id}** — polling статуса из БД; frontend поллит каждые 2000ms; маскировка при `DEMO_MODE=1`
✅ **PDF extraction** — PyPDF2 (текст), camelot/pdfplumber (таблицы), pytesseract (OCR для сканов)
✅ **Financial ratios** — 13 коэффициентов (4 группы: ликвидность, рентабельность, устойчивость, активность); RU-ключи → EN через `RATIO_KEY_MAP` в `tasks.py`
✅ **Integral scoring** — скоринг 0–100, risk_level (пороги 75/50), factors, normalized_scores (`scoring.py` + `_build_score_payload()`)
✅ **NLP analysis** — риски и ключевые факторы через `ai_service.py` (GigaChat → Qwen → Ollama → graceful degrade)
✅ **Recommendations** — `src/analysis/recommendations.py`: 3–5 рекомендаций с явными ссылками на метрики; timeout 65s; fallback при недоступности AI; подключено в `tasks.py`
✅ **GET /analyses** — список анализов с пагинацией (page, page_size ≤ 100), сортировка по created_at DESC, auth X-API-Key
✅ **GET /analyses/{task_id}** — детали анализа по task_id, 404 если не найден, auth X-API-Key
✅ **Masking** — `src/utils/masking.py`: чистая функция `mask_analysis_data(data, demo_mode)`, применяется во всех трёх эндпоинтах при `DEMO_MODE=1`
✅ **AnalysisHistory.tsx** — подключена к реальному API (`GET /analyses`), пагинация Mantine, skeleton/error states, клик → `GET /analyses/{task_id}` → DetailedReport
✅ **DetailedReport.tsx** — BarChart из реальных `result.ratios` (ненулевые значения), цветовое кодирование по порогам, fallback "Недостаточно данных"
✅ **БД** — PostgreSQL 16, SQLAlchemy async, 2 миграции Alembic (`analyses` + индексы)
✅ **Auth.tsx** — pre-flight `GET /api/analyses?page=1&page_size=1` с введённым ключом; 401/403 → «Невалидный ключ»; сетевая ошибка → «Не удалось подключиться»; 8 unit-тестов зелёные
✅ **Vite proxy** — `/api` → `http://localhost:8000`; `apiClient` baseURL → `/api`; CORS больше не задействован в dev
✅ **CI/CD** — GitHub Actions: lint → test → security → build
✅ **Docker** — backend, frontend/nginx, db, db_test, ollama
✅ **Тесты** — backend: property-тесты (hypothesis) + unit; frontend: property-тесты (fast-check) + unit (vitest)

---

## Что разрабатывается
🔄 **nlp_analysis.py** — модуль реализован, вызов подключён в `tasks.py`, но не проверен на реальных данных [MEDIUM]

---

## Что будет дальше
❌ Устранить дублирование `types.ts` vs `interfaces.ts` (оставить только `interfaces.ts`)
❌ Celery + Redis вместо BackgroundTasks (для персистентности задач при рестарте)
❌ WebSocket / SSE вместо polling
❌ Устранить дублирование `types.ts` vs `interfaces.ts` (оставить только `interfaces.ts`)
❌ Celery + Redis вместо BackgroundTasks (для персистентности задач при рестарте)
❌ WebSocket / SSE вместо polling

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
