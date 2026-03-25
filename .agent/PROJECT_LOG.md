# Project Log

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
