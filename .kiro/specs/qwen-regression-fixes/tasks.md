# Implementation Plan

## Фаза 0 — Exploratory тесты (воспроизвести баги ДО исправления)

- [x] 1. Write bug condition exploration tests
  - **Property 1: Bug Condition** - Qwen Regression Bugs
  - **CRITICAL**: Эти тесты ДОЛЖНЫ ПАДАТЬ на незафиксированном коде — падение подтверждает существование багов
  - **DO NOT attempt to fix the tests or the code when they fail**
  - **GOAL**: Воспроизвести баги и задокументировать контрпримеры
  - **Scoped PBT Approach**: Для детерминированных багов — конкретные входные данные
  - Написать `tests/test_qwen_regression_exploratory.py`:
    - `test_polling_uses_wrong_endpoint`: вызвать `analyze(file)` с моком `apiClient` → убедиться, что делается запрос к `/analyze/pdf/file` вместо `/upload`
    - `test_period_input_missing_file_path`: создать `PeriodInput(period_label="2023")` → обратиться к `.file_path` → ожидать `AttributeError`
    - `test_is_valid_financial_value_rejects_small`: `_is_valid_financial_value(0.15)` → ожидать `False` (баг)
    - `test_mask_number_none_returns_none`: `_mask_number(None)` → ожидать `None` (баг, нарушение типа `-> str`)
  - Запустить тесты на незафиксированном коде
  - **EXPECTED OUTCOME**: Тесты ПАДАЮТ (это правильно — подтверждает существование багов)
  - Задокументировать контрпримеры для понимания root cause
  - Отметить задачу выполненной когда тесты написаны, запущены и падение задокументировано
  - _Requirements: 1.1, 1.7, 1.13, 1.17_


## Фаза 1 — Preservation тесты (ПЕРЕД исправлением)

- [x] 2. Write preservation property tests (BEFORE implementing fixes)
  - **Property 2: Preservation** - Existing Behavior Unchanged
  - **IMPORTANT**: Следовать observation-first методологии
  - Наблюдать поведение незафиксированного кода для входных данных, НЕ попадающих под Bug_Condition
  - Написать `tests/test_qwen_regression_preservation.py`:
    - `prop_financial_value_filter`: для всех `v` в `(0, 1e15)` кроме целых 1900–2100 — `_is_valid_financial_value(v)` возвращает `True` (Hypothesis)
    - `prop_masking_idempotency`: `mask_analysis_data(mask_analysis_data(data, True), True) == mask_analysis_data(data, True)` для любого словаря с числовыми значениями (Hypothesis)
    - `prop_circuit_breaker_state_machine`: для любой последовательности `record_success/record_failure` переходы состояний соответствуют автомату CLOSED→OPEN→HALF_OPEN→CLOSED (Hypothesis)
    - `prop_polling_termination`: для любой последовательности ответов сервера polling завершается за ≤ 15 шагов (Hypothesis)
    - `test_large_financial_values_accepted`: `_is_valid_financial_value(1_000_000)` → `True` (крупный бизнес)
    - `test_mask_number_numeric_values`: `_mask_number(1234567.89)` → корректная маскировка (не None)
    - `test_cors_valid_config`: запуск с валидным `CORS_ALLOW_ORIGINS` → корректная настройка без ошибок
    - `test_recommendations_fallback`: `generate_recommendations` без AI → `FALLBACK_RECOMMENDATIONS`
  - Запустить тесты на незафиксированном коде
  - **EXPECTED OUTCOME**: Тесты ПРОХОДЯТ (подтверждает baseline-поведение для сохранения)
  - Отметить задачу выполненной когда тесты написаны, запущены и проходят на незафиксированном коде
  - _Requirements: 3.1, 3.2, 3.4, 3.5, 3.6, 3.7, 3.11, 3.12_


## Группа 1 — Критические баги (БАГ 1–3)

- [x] 3. Fix БАГ 1 — AnalysisContext.tsx: polling flow

  - [x] 3.0 Verify backend endpoints for polling
    - Проверить, что `POST /upload` в `src/routers/pdf_tasks.py` возвращает `{"task_id": "..."}` и ставит задачу в BackgroundTask
    - Проверить, что `GET /result/{task_id}` возвращает `{"status": "processing"|"completed"|"failed", ...}`
    - Если эндпоинты отсутствуют или сломаны — зафиксировать их перед работой над фронтендом
    - _Prerequisite: задача 3.1 не начинается до прохождения этой проверки_

  - [x] 3.1 Реализовать правильный polling flow в `frontend/src/context/AnalysisContext.tsx`
    - Заменить `POST /analyze/pdf/file` на `POST /upload` для получения `task_id`
    - Добавить константы `MAX_POLLING_ATTEMPTS = 15` и `POLLING_INTERVAL = 2000`
    - Реализовать рекурсивный polling через `setTimeout` со счётчиком попыток и флагом `cancelled`
    - HTTP 404 → остановить polling, показать "Задача не найдена"
    - HTTP 5xx → retry (считается как попытка), `setTimeout(poll, POLLING_INTERVAL)`
    - Сетевые ошибки → retry (считается как попытка), `setTimeout(poll, POLLING_INTERVAL)`
    - Добавить `useRef<ReturnType<typeof setTimeout>>` для `timeoutId`; в cleanup `useEffect` вызывать `clearTimeout(timeoutId.current)` и `cancelled = true`
    - Заменить `err: any` на `err: unknown` с type guard (см. также БАГ 13)
    - _Bug_Condition: context.endpoint == "/analyze/pdf/file" AND context.hasPolling == False_
    - _Expected_Behavior: POST /upload → task_id → polling GET /result/{task_id} каждые 2000ms, завершение за ≤ 15 попыток_
    - _Preservation: single-period анализ через /upload → polling продолжает работать; status "completed" останавливает polling_
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 3.3, 3.11_

  - [x] 3.2 Verify bug condition exploration test now passes
    - **Property 1: Expected Behavior** - Polling Flow Fix
    - **IMPORTANT**: Перезапустить ТЕСТ ИЗ ЗАДАЧИ 1 — не писать новый тест
    - Запустить `test_polling_uses_wrong_endpoint` из задачи 1
    - **EXPECTED OUTCOME**: Тест ПРОХОДИТ (подтверждает исправление бага)
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5_

  - [x] 3.3 Verify preservation tests still pass
    - **Property 2: Preservation** - Polling Termination
    - **IMPORTANT**: Перезапустить ТЕСТЫ ИЗ ЗАДАЧИ 2 — не писать новые тесты
    - Запустить `prop_polling_termination` из задачи 2
    - **EXPECTED OUTCOME**: Тесты ПРОХОДЯТ (нет регрессий)

- [x] 4. Fix БАГ 2 — pdf_extractor.py: Tesseract хардкод

  - [x] 4.1 Убрать хардкод Windows-пути и добавить graceful degradation в `src/analysis/pdf_extractor.py`
    - Удалить блок `_tesseract_path = os.path.expandvars(r"C:\Program Files\...")`
    - Добавить опциональную поддержку `TESSERACT_CMD` из env: `_tesseract_cmd = os.getenv("TESSERACT_CMD"); if _tesseract_cmd: pytesseract.pytesseract.tesseract_cmd = _tesseract_cmd`
    - Добавить `_check_tesseract_available() -> bool` с `try/except pytesseract.get_tesseract_version()`
    - Добавить `TESSERACT_AVAILABLE = _check_tesseract_available()` на уровне модуля
    - В `extract_text_from_scanned` проверять `TESSERACT_AVAILABLE` перед вызовом OCR
    - При недоступности Tesseract: `logger.warning("OCR недоступен: установите tesseract-ocr или задайте TESSERACT_CMD")`, вернуть только текстовый слой
    - _Bug_Condition: context.hasHardcodedWindowsPath == True_
    - _Expected_Behavior: путь к Tesseract только через TESSERACT_CMD или системный PATH; graceful degradation при отсутствии_
    - _Preservation: OCR на Windows с установленным Tesseract продолжает работать через PATH или TESSERACT_CMD_
    - _Requirements: 2.6, 2.7, 2.8, 3.2_

  - [x] 4.2 Verify bug condition exploration test now passes
    - **Property 1: Expected Behavior** - Tesseract No Hardcode
    - Запустить `test_tesseract_no_hardcode` и `test_tesseract_graceful_degradation` из задачи 1
    - **EXPECTED OUTCOME**: Тесты ПРОХОДЯТ

  - [x] 4.3 Verify preservation tests still pass
    - **Property 2: Preservation** - Tesseract Windows PATH
    - Запустить preservation тесты из задачи 2
    - **EXPECTED OUTCOME**: Тесты ПРОХОДЯТ (нет регрессий)

- [x] 5. Fix БАГ 3 — schemas.py + multi_analysis.py: file_path (BREAKING CHANGE)

  - [x] 5.0 Audit: найти все создания PeriodInput в кодовой базе
    - Выполнить: `grep -r "PeriodInput(" src/ --include="*.py"`
    - Зафиксировать все места создания объектов `PeriodInput` — они потребуют обновления после добавления обязательного поля `file_path`
    - _Prerequisite: задачи 5.1–5.2 не начинаются до завершения аудита_

  - [x] 5.1 Добавить `file_path` в `PeriodInput` в `src/models/schemas.py`
    - Добавить поле `file_path: str = Field(description="Путь к временному PDF-файлу для этого периода")`
    - Убедиться, что `period_label: str = Field(min_length=1, max_length=20)` сохранено
    - _Bug_Condition: "file_path" NOT IN PeriodInput.fields_
    - _Expected_Behavior: PeriodInput принимает file_path; AttributeError устранён_
    - _Requirements: 2.9, 2.10, 2.11_

  - [x] 5.2 Обновить роутер `src/routers/multi_analysis.py` для приёма multipart/form-data
    - Изменить сигнатуру: `files: list[UploadFile] = File(...)`, `periods: list[str] = Form(...)`
    - Валидация: `len(files) != len(periods)` → HTTP 422; `len(files) > 5` → HTTP 422
    - Сохранить каждый файл во временный файл через `tempfile.NamedTemporaryFile`
    - Создать `PeriodInput(period_label=label, file_path=tmp.name)` для каждого периода
    - Очищать временные файлы в `process_multi_analysis` через `_cleanup_temp_file`
    - _Bug_Condition: multi-period запрос → AttributeError при обращении к period.file_path_
    - _Expected_Behavior: корректная передача file_path; HTTP 422 при несовпадении количества файлов_
    - _Preservation: multi-period анализ при успешном завершении возвращает результаты хронологически_
    - _Requirements: 2.9, 2.10, 2.11, 3.8_

  - [x] 5.2.1 Обновить `process_multi_analysis` в `src/tasks.py`
    - Заменить вызов `_process_single_period(period.period_label, ...)` на `_process_single_period(period.file_path, period.period_label)` — убедиться, что `file_path` передаётся первым аргументом согласно сигнатуре функции
    - Добавить обработку `FileNotFoundError`: если файл не найден → `logger.warning("Period '%s' file not found: %s", period.period_label, period.file_path)` и вернуть `{"period_label": period.period_label, "error": "file_not_found"}` вместо краша
    - Обновить все места создания `PeriodInput`, найденные в задаче 5.0, добавив `file_path`
    - _Requirements: 2.9, 2.10, 3.8_

  - [x] 5.3 Verify bug condition exploration test now passes
    - **Property 1: Expected Behavior** - PeriodInput file_path
    - Запустить `test_period_input_missing_file_path` из задачи 1
    - **EXPECTED OUTCOME**: Тест ПРОХОДИТ (AttributeError устранён)

  - [x] 5.4 Verify preservation tests still pass
    - **Property 2: Preservation** - Multi-period Analysis
    - Запустить preservation тесты из задачи 2
    - **EXPECTED OUTCOME**: Тесты ПРОХОДЯТ (нет регрессий)

- [x] 5.5 Патчноут и коммит — Группа 1 (критические баги)
  - Обновить `.agent/PROJECT_LOG.md`: добавить запись сверху с описанием исправлений БАГ 1–3
  - Обновить `.agent/overview.md`: отметить БАГ 1–3 как исправленные
  - Выполнить коммит:
    ```
    git add -A
    git commit -m "fix(critical): restore polling flow, remove Tesseract hardcode, add file_path to PeriodInput

    - БАГ 1: AnalysisContext.tsx — POST /upload + polling GET /result/{task_id}, MAX_POLLING_ATTEMPTS=15
    - БАГ 2: pdf_extractor.py — убран хардкод C:\Program Files\Tesseract-OCR, graceful degradation
    - БАГ 3: PeriodInput.file_path добавлен, multi_analysis роутер принимает multipart/form-data

    BREAKING CHANGE: PeriodInput теперь требует обязательное поле file_path"
    ```
  - Отправить в GitHub: `git push`

- [x] 6. Fix БАГ 4 — recommendations.py: двойной timeout

  - [x] 6.1 Удалить внешний `asyncio.wait_for` из `src/analysis/recommendations.py`
    - Удалить обёртку `asyncio.wait_for(timeout=65.0)` из `generate_recommendations`
    - Оставить только `ai_service.invoke(timeout=60)` внутри функции
    - Внешний `asyncio.wait_for` в `tasks.py` остаётся без изменений
    - _Bug_Condition: context.hasOuterWaitFor == True AND context.hasInnerWaitFor == True_
    - _Expected_Behavior: ровно один asyncio.wait_for на стеке вызовов — в tasks.py_
    - _Preservation: generate_recommendations без AI возвращает FALLBACK_RECOMMENDATIONS_
    - _Requirements: 2.12, 2.13, 3.7, 3.12_

  - [x] 6.2 Verify bug condition exploration test now passes
    - **Property 1: Expected Behavior** - Single Timeout Control
    - Запустить `test_recommendations_no_outer_wait_for` из задачи 1
    - **EXPECTED OUTCOME**: Тест ПРОХОДИТ

  - [x] 6.3 Verify preservation tests still pass
    - **Property 2: Preservation** - Recommendations Fallback
    - Запустить `test_recommendations_fallback` из задачи 2
    - **EXPECTED OUTCOME**: Тест ПРОХОДИТ (нет регрессий)

- [x] 7. Fix БАГ 5 — circuit_breaker.py: threading.Lock → asyncio.Lock

  - [x] 7.1 Заменить `threading.Lock` на `asyncio.Lock` в `src/utils/circuit_breaker.py`
    - Заменить `from threading import Lock` на `import asyncio`
    - Изменить `self._lock = Lock()` на `self._lock = asyncio.Lock()`
    - Сделать `record_success`, `record_failure`, `reset` async-методами с `async with self._lock`
    - Убрать lock из синхронных свойств `is_available`, `state` (read-only, атомарные операции)
    - Добавить комментарий `# NB: не выполнять длительные await внутри with lock`
    - _Bug_Condition: context.lockType == "threading.Lock"_
    - _Expected_Behavior: asyncio.Lock; record_success/failure/reset — async методы_
    - _Preservation: circuit breaker в CLOSED без contention пропускает запросы без задержек_
    - _Requirements: 2.14, 2.15, 3.4_

  - [x] 7.2 Найти и обновить ВСЕ вызовы circuit_breaker в кодовой базе
    - Выполнить: `grep -r "circuit_breaker\.record_" src/ --include="*.py"` — найти все места вызова `record_success()` и `record_failure()`
    - Обновить ВСЕ найденные вызовы на `await`: `await ai_circuit_breaker.record_success()`, `await ai_circuit_breaker.record_failure()`
    - Убедиться, что все вызывающие функции являются `async` — если нет, сделать их `async`
    - _Requirements: 2.14_

  - [x] 7.3 Verify bug condition exploration test now passes
    - **Property 1: Expected Behavior** - asyncio.Lock
    - Запустить `test_circuit_breaker_uses_asyncio_lock` из задачи 1
    - **EXPECTED OUTCOME**: Тест ПРОХОДИТ

  - [x] 7.4 Verify preservation tests still pass
    - **Property 2: Preservation** - Circuit Breaker State Machine
    - Запустить `prop_circuit_breaker_state_machine` из задачи 2
    - **EXPECTED OUTCOME**: Тест ПРОХОДИТ (нет регрессий)

- [x] 8. Fix БАГ 6 — pdf_extractor.py: _is_valid_financial_value

  - [x] 8.1 Исправить `_is_valid_financial_value` в `src/analysis/pdf_extractor.py`
    - Добавить вспомогательную функцию `_is_year(v: float) -> bool` с безопасным float-сравнением
    - Убрать проверку `abs(value) < 1000` из `_is_valid_financial_value`
    - Заменить `if value == int(value) and int(value) in _YEAR_RANGE` на `if _is_year(value)`
    - Оставить фильтр переполнения: `if abs(value) > 1e15: return False`
    - _Bug_Condition: abs(context.value) < 1000 AND value NOT IN year_range(1900, 2101)_
    - _Expected_Behavior: _is_valid_financial_value(v) == True для v в (0, 1e15) кроме целых 1900–2100_
    - _Preservation: крупные финансовые показатели (> 1000) продолжают приниматься_
    - _Requirements: 2.16, 2.17, 3.1_

  - [x] 8.2 Verify bug condition exploration test now passes
    - **Property 1: Expected Behavior** - Financial Value Filter
    - Запустить `test_is_valid_financial_value_rejects_small` из задачи 1
    - **EXPECTED OUTCOME**: Тест ПРОХОДИТ (`_is_valid_financial_value(0.15)` → `True`)

  - [x] 8.3 Verify preservation tests still pass
    - **Property 2: Preservation** - Financial Value Filter (large values)
    - Запустить `prop_financial_value_filter` и `test_large_financial_values_accepted` из задачи 2
    - **EXPECTED OUTCOME**: Тесты ПРОХОДЯТ (нет регрессий)

- [x] 9. Fix БАГ 7 — app.py: NameError в CORS

  - [x] 9.1 Переместить `default_origins` до блока `try/except` в `src/app.py`
    - Определить `default_origins = ["http://localhost", "http://localhost:80", ...]` ДО блока `try/except`
    - Убедиться, что `except ValueError` использует уже определённую переменную
    - _Bug_Condition: context.dev_mode == True AND context.corsOrigins IS INVALID_
    - _Expected_Behavior: default_origins доступна в except ValueError при любом dev_mode_
    - _Preservation: запуск с валидным CORS_ALLOW_ORIGINS и dev_mode=False работает без ошибок_
    - _Requirements: 2.18, 3.6_

  - [x] 9.2 Verify bug condition exploration test now passes
    - **Property 1: Expected Behavior** - CORS No NameError
    - Запустить `test_cors_no_name_error` из задачи 1
    - **EXPECTED OUTCOME**: Тест ПРОХОДИТ (NameError устранён)

  - [x] 9.3 Verify preservation tests still pass
    - **Property 2: Preservation** - CORS Valid Config
    - Запустить `test_cors_valid_config` из задачи 2
    - **EXPECTED OUTCOME**: Тест ПРОХОДИТ (нет регрессий)

- [-] 10. Fix БАГ 8 — masking.py: _mask_number None

  - [x] 10.1 Исправить `_mask_number` в `src/utils/masking.py`
    - Добавить константу `MASKED_NONE_VALUE = "—"` на уровне модуля
    - Обновить сигнатуру: `def _mask_number(value: float | int | None) -> str`
    - Заменить `return None` на `return MASKED_NONE_VALUE`
    - _Bug_Condition: context.input == None AND context.returnType != "str"_
    - _Expected_Behavior: _mask_number(None) → "—" (str, не None)_
    - _Preservation: _mask_number с числовыми значениями продолжает корректно маскировать_
    - _Requirements: 2.19, 2.20, 3.5_

  - [x] 10.2 Verify bug condition exploration test now passes
    - **Property 1: Expected Behavior** - Mask None Returns Dash
    - Запустить `test_mask_number_none_returns_none` из задачи 1
    - **EXPECTED OUTCOME**: Тест ПРОХОДИТ (`_mask_number(None)` → `"—"`)

  - [x] 10.3 Verify preservation tests still pass
    - **Property 2: Preservation** - Masking Idempotency
    - Запустить `prop_masking_idempotency` и `test_mask_number_numeric_values` из задачи 2
    - **EXPECTED OUTCOME**: Тесты ПРОХОДЯТ (нет регрессий)

- [x] 10.4 Патчноут и коммит — Группа 2 (серьёзные баги)
  - Обновить `.agent/PROJECT_LOG.md`: добавить запись сверху с описанием исправлений БАГ 4–8
  - Обновить `.agent/overview.md`: отметить БАГ 4–8 как исправленные
  - Выполнить коммит:
    ```
    git add -A
    git commit -m "fix(reliability): remove double timeout, asyncio.Lock, fix financial filter, CORS NameError, mask None

    - БАГ 4: recommendations.py — удалён внешний asyncio.wait_for, единственный timeout в tasks.py
    - БАГ 5: circuit_breaker.py — threading.Lock → asyncio.Lock, record_* методы стали async
    - БАГ 6: pdf_extractor.py — убран порог 1000, добавлен _is_year() с безопасным float-сравнением
    - БАГ 7: app.py — default_origins определён до try/except, NameError устранён
    - БАГ 8: masking.py — _mask_number(None) возвращает MASKED_NONE_VALUE='—' вместо None"
    ```
  - Отправить в GitHub: `git push`


## Группа 3 — Нарушения AGENTS.md (БАГ 9–11)

- [x] 11. Fix БАГ 9 — f-строки в логах (5 файлов)

  - [x] 11.1 Заменить f-строки на `%`-форматирование в `src/app.py`
    - Заменить все `logger.info(f"...")`, `logger.warning(f"...")`, `logger.error(f"...")` на `%`-форматирование
    - Пример: `logger.info(f"msg {var}")` → `logger.info("msg %s", var)`
    - _Requirements: 2.21_

  - [x] 11.2 Заменить f-строки на `%`-форматирование в `src/tasks.py`
    - Аналогично 11.1
    - _Requirements: 2.21_

  - [x] 11.3 Заменить f-строки на `%`-форматирование в `src/core/ai_service.py`
    - Аналогично 11.1
    - _Requirements: 2.21_

  - [x] 11.4 Заменить f-строки на `%`-форматирование в `src/utils/circuit_breaker.py`
    - Аналогично 11.1 (выполнить вместе с задачей 7.1)
    - _Requirements: 2.21_

  - [x] 11.5 Заменить f-строки на `%`-форматирование в `src/utils/retry_utils.py`
    - Аналогично 11.1
    - _Requirements: 2.21_

- [x] 12. Fix БАГ 10 — tasks.py: импорты на уровень модуля

  - [x] 12.1 Перенести inline-импорты на уровень модуля в `src/tasks.py`
    - Перенести `from src.analysis.nlp_analysis import analyze_narrative` на уровень модуля
    - Перенести `from src.analysis.recommendations import generate_recommendations` на уровень модуля
    - Проверить существование `src/controllers/analyze.py` и `_extract_metrics_with_regex`
    - Если файл существует — перенести импорт на уровень модуля; если нет — удалить вызов
    - _Requirements: 2.22_

- [x] 13. Fix БАГ 11 — requirements.txt: pdfplumber версия

  - [x] 13.1 Обновить версию `pdfplumber` в `requirements.txt`
    - Заменить `pdfplumber~=0.11.9` на `pdfplumber~=0.12.0`
    - _Requirements: 2.23_

- [x] 13.2 Патчноут и коммит — Группа 3 (нарушения AGENTS.md)
  - Обновить `.agent/PROJECT_LOG.md`: добавить запись сверху с описанием исправлений БАГ 9–11
  - Обновить `.agent/overview.md`: отметить БАГ 9–11 как исправленные
  - Выполнить коммит:
    ```
    git add -A
    git commit -m "refactor(code-style): fix f-strings in loggers, move imports to module level, bump pdfplumber

    - БАГ 9: заменены f-строки на %-форматирование в app.py, tasks.py, ai_service.py, circuit_breaker.py, retry_utils.py
    - БАГ 10: tasks.py — импорты nlp_analysis и recommendations перенесены на уровень модуля
    - БАГ 11: requirements.txt — pdfplumber 0.11.9 → 0.12.0 (fix known compatibility issue)"
    ```
  - Отправить в GitHub: `git push`


## Группа 4 — Мелкие нарушения (БАГ 12–14)

- [x] 14. Fix БАГ 12 — client.ts: console.log условный

  - [x] 14.1 Обернуть `console.log` в `if (import.meta.env.DEV)` в `frontend/src/api/client.ts`
    - Обернуть `console.log` в request interceptor в `if (import.meta.env.DEV)`
    - Обернуть `console.log` и `console.error` в response interceptor в `if (import.meta.env.DEV)`
    - _Requirements: 2.24_

- [x] 15. Fix БАГ 13 — TypeScript err: any → unknown

  - [x] 15.1 Заменить `err: any` на `err: unknown` в `frontend/src/context/AnalysisContext.tsx`
    - (Выполнить вместе с задачей 3.1 если ещё не сделано)
    - _Requirements: 2.25_

  - [x] 15.2 Заменить `err: any` на `err: unknown` в `frontend/src/pages/AnalysisHistory.tsx`
    - Аналогично 15.1
    - _Requirements: 2.25_

- [x] 16. Fix БАГ 14 — docs/CONFIGURATION.md: документация

  - [x] 16.1 Обновить `docs/CONFIGURATION.md`
    - Заменить упоминания "DeepSeek" на "HuggingFace (Qwen/Qwen3.5-9B-Instruct)"
    - Добавить переменные `HF_TOKEN`, `HF_MODEL` с актуальными дефолтами
    - Добавить `QWEN_API_KEY`, `QWEN_API_URL` как deprecated-провайдер
    - _Requirements: 2.26_

- [x] 16.2 Патчноут и коммит — Группа 4 (мелкие нарушения)
  - Обновить `.agent/PROJECT_LOG.md`: добавить запись сверху с описанием исправлений БАГ 12–14
  - Обновить `.agent/overview.md`: отметить БАГ 12–14 как исправленные
  - Выполнить коммит:
    ```
    git add -A
    git commit -m "fix(frontend): conditional console.log, err: unknown, update CONFIGURATION.md

    - БАГ 12: client.ts — console.log/error обёрнуты в if (import.meta.env.DEV)
    - БАГ 13: AnalysisContext.tsx, AnalysisHistory.tsx — err: any → err: unknown с type guard
    - БАГ 14: docs/CONFIGURATION.md — актуализированы AI-провайдеры (HuggingFace/Qwen, deprecated Qwen API)"
    ```
  - Отправить в GitHub: `git push`


## Группа 5 — Тесты (Fix + Integration)

- [x] 17. Write fix verification tests

  - [x] 17.1 Написать unit-тесты для верификации исправлений в `tests/test_qwen_regression_fixes.py`
    - `test_polling_uses_upload_endpoint`: POST /upload → task_id → polling
    - `test_polling_stops_on_404`: HTTP 404 → остановить polling
    - `test_polling_retries_on_5xx`: HTTP 5xx → retry, не останавливать
    - `test_polling_retries_on_network_error`: сетевая ошибка → retry
    - `test_polling_max_attempts`: после 15 попыток → ошибка
    - `test_tesseract_no_hardcode`: импорт `pdf_extractor` не устанавливает Windows-путь
    - `test_tesseract_graceful_degradation`: Tesseract недоступен → warning, не краш
    - `test_period_input_has_file_path`: `PeriodInput` принимает `file_path`
    - `test_multi_analysis_validates_file_count`: `len(files) != len(periods)` → 422
    - `test_recommendations_no_outer_wait_for`: нет `asyncio.wait_for` в `generate_recommendations`
    - `test_circuit_breaker_uses_asyncio_lock`: `isinstance(breaker._lock, asyncio.Lock)`
    - `test_is_valid_financial_value_accepts_small`: `_is_valid_financial_value(0.15)` → `True`
    - `test_is_valid_financial_value_rejects_year`: `_is_valid_financial_value(2023)` → `False`
    - `test_is_valid_financial_value_float_year`: `_is_valid_financial_value(2023.0)` → `False`
    - `test_cors_no_name_error`: `dev_mode=True` + невалидный CORS → нет `NameError`
    - `test_mask_number_none_returns_dash`: `_mask_number(None)` → `"—"`
    - _Requirements: 2.1–2.20_

- [-] 18. Write integration tests

  - [x] 18.1 Написать integration-тесты в `tests/test_qwen_regression_integration.py`
    - `test_full_upload_polling_flow`: POST /upload → polling → completed → результат отображается
    - `test_multi_analysis_with_files`: multipart запрос с файлами → корректная обработка без `AttributeError`
    - `test_app_startup_dev_mode_invalid_cors`: запуск с `dev_mode=True` + невалидный CORS → нет `NameError`, используются `default_origins`
    - _Requirements: 2.1, 2.9, 2.18_

- [x] 18.2 Патчноут и коммит — Группа 5 (тесты)
  - Обновить `.agent/PROJECT_LOG.md`: добавить запись сверху с итоговой статистикой тестов
  - Выполнить коммит:
    ```
    git add -A
    git commit -m "test(regression): add exploratory, preservation, fix and integration tests for Qwen regressions

    - test_qwen_regression_exploratory.py — воспроизведение 4 багов (Property 1: Bug Condition)
    - test_qwen_regression_preservation.py — 4 PBT + 4 unit (Property 2: Preservation)
    - test_qwen_regression_fixes.py — 16 unit-тестов верификации исправлений
    - test_qwen_regression_integration.py — 3 integration-теста полного flow"
    ```
  - Отправить в GitHub: `git push`

## Checkpoint

- [ ] 19. Checkpoint — Ensure all tests pass
  - Запустить полный набор тестов: `pytest tests/test_qwen_regression_exploratory.py tests/test_qwen_regression_preservation.py tests/test_qwen_regression_fixes.py tests/test_qwen_regression_integration.py -v`
  - Убедиться, что все тесты проходят
  - Убедиться, что существующие тесты не сломаны: `pytest --tb=short`
  - Обновить `.agent/overview.md` и `.agent/PROJECT_LOG.md`
  - Если возникают вопросы — уточнить у пользователя


## Группа 6 — Post-deploy verification

- [ ] 20. Smoke-тесты перед деплоем в production
  - Запустить smoke-тесты на staging-окружении перед деплоем в production:
    - `POST /upload` с тестовым PDF → убедиться, что возвращается `task_id` (баг #1)
    - `GET /result/{task_id}` → убедиться, что статус меняется `processing` → `completed` (баг #1)
    - Проверить логи на отсутствие `AttributeError` в `multi_analysis` (баг #3)
    - Проверить логи на наличие `OCR недоступен` при запуске без Tesseract — убедиться, что это warning, не краш (баг #2)
    - Убедиться, что `pytest tests/test_qwen_regression_integration.py -v` проходит на staging
  - _Prerequisite: задача 19 завершена_
