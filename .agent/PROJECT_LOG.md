# Project Log

## 2026-03-25 — Qwen Regression Fixes: Группа 4 (мелкие нарушения)

### БАГ 12–14: console.log в production, err: any, устаревшая документация

**Изменения:**
- `frontend/src/api/client.ts` — `console.log` в request interceptor и `console.log`/`console.error` в response interceptor обёрнуты в `if (import.meta.env.DEV)`
- `frontend/src/pages/AnalysisHistory.tsx` — два `catch (e: any)` заменены на `catch (e: unknown)` с inline type guard
- `frontend/src/context/AnalysisContext.tsx` — уже был чистым (`err: unknown`), изменений не потребовалось
- `docs/CONFIGURATION.md` — заменены упоминания DeepSeek на HuggingFace (Qwen/Qwen3.5-9B-Instruct); добавлена пометка deprecated для `QWEN_API_KEY`/`QWEN_API_URL`; обновлены дефолты `HF_MODEL` и пример `.env`

---

## 2026-03-25 — Qwen Regression Fixes: Группа 3 (нарушения AGENTS.md)

### БАГ 9–11: f-строки в логах, inline-импорты, версия pdfplumber

**Изменения:**
- `src/app.py` — 3 f-строки в `log_requests` middleware заменены на `%`-форматирование
- `src/tasks.py` — 12 f-строк в `process_pdf` и `process_multi_analysis` заменены на `%`-форматирование; `analyze_narrative`, `generate_recommendations`, `_extract_metrics_with_regex` перенесены с уровня функций на уровень модуля
- `src/utils/retry_utils.py` — 5 f-строк в `retry_with_backoff` заменены на `%`-форматирование
- `requirements.txt` — `pdfplumber~=0.11.9` → `~=0.12.0` (fix known Python 3.10+ compatibility issue, зафиксировано в `local_notes.md`)

**Примечание:** `src/core/ai_service.py` и `src/utils/circuit_breaker.py` уже были чистыми — f-строк не содержали.

---

## 2026-03-25 — Qwen Regression Fixes: Группа 2 (серьёзные баги)

### БАГ 4–8: двойной timeout, asyncio.Lock, фильтр финансовых значений, CORS NameError, mask None

**Изменения:**
- `src/analysis/recommendations.py` — удалён внешний `asyncio.wait_for(timeout=65.0)` из `generate_recommendations`; единственный timeout теперь в `tasks.py`
- `src/utils/circuit_breaker.py` — `threading.Lock` → `asyncio.Lock`; методы `record_success`, `record_failure`, `reset` стали `async`; добавлен комментарий `# NB: не выполнять длительные await внутри with lock`
- `src/core/ai_service.py` — все вызовы `circuit_breaker.record_*` обновлены на `await`
- `src/analysis/pdf_extractor.py` — убран порог `abs(value) < 1000` из `_is_valid_financial_value`; добавлена `_is_year(v)` с безопасным float-сравнением; теперь отклоняются только `None`, годы 1900–2100 и значения `> 1e15`
- `src/app.py` — `default_origins` определён до блока `try/except`; `NameError` при `dev_mode=True` + невалидный CORS устранён
- `src/utils/masking.py` — добавлена константа `MASKED_NONE_VALUE = "—"`; `_mask_number(None)` возвращает `"—"` вместо `None`; сигнатура обновлена: `def _mask_number(value: float | int | None) -> str`

**Тесты:** `test_prop_masking_idempotency` — PASSED; `test_mask_number_numeric_values` — PASSED; все preservation тесты — PASSED.

---

## 2026-03-25 — Qwen Regression Fixes: Группа 1 (критические баги)

### БАГ 3: PeriodInput.file_path добавлен, multi_analysis роутер принимает multipart/form-data

**Изменения:**
- `src/models/schemas.py` — добавлено обязательное поле `file_path: str` в `PeriodInput`
- `src/routers/multi_analysis.py` — роутер переписан: принимает `multipart/form-data` (`files: list[UploadFile]`, `periods: list[str]`); валидация несовпадения количества файлов/меток → HTTP 422; лимит 5 периодов → HTTP 422; каждый файл сохраняется в `tempfile.NamedTemporaryFile`; создаётся `PeriodInput(period_label=label, file_path=tmp.name)`
- `src/tasks.py` — добавлена обработка `FileNotFoundError` в `_process_single_period`; временные файлы очищаются через `_cleanup_temp_file` после обработки каждого периода
- `tests/test_multi_analysis_router.py` — тесты обновлены для multipart/form-data; добавлен тест `test_post_multi_analysis_mismatched_files_and_periods`
- `tests/test_qwen_regression_exploratory.py` — `test_period_input_missing_file_path` обновлён: теперь проверяет, что `ValidationError` поднимается при отсутствии `file_path`, и что валидный экземпляр корректно возвращает `file_path`

**BREAKING CHANGE:** `PeriodInput` теперь требует обязательное поле `file_path`. Клиенты, использующие JSON-тело `MultiAnalysisRequest`, должны перейти на `multipart/form-data`.

**Тесты:** `test_period_input_missing_file_path` — PASSED; 6/6 preservation тестов — PASSED.
