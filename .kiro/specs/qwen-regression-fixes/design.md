# Qwen Regression Fixes — Bugfix Design

## Overview

В ходе частичного переписывания проекта NeoFin AI агентом Qwen были внесены регрессии в 14 местах кодовой базы. Баги охватывают три категории:

- **Критические** (БАГ 1–3): неправильный flow анализа на фронтенде, хардкод Windows-путей к Tesseract, сломанная multi-period модель (breaking change)
- **Серьёзные** (БАГ 4–8): двойной timeout, threading.Lock в async-коде, неверная фильтрация финансовых значений, NameError при старте, нарушение типа возврата
- **Нарушения AGENTS.md и мелкие** (БАГ 9–14): f-строки в логах, импорты внутри функций, откат версии pdfplumber, console.log в production, `err: any`, устаревшая документация

Стратегия исправления: минимальные точечные изменения в каждом файле, без рефакторинга несвязанной логики. Каждое исправление верифицируется тестами.

**Rollback-стратегия**: если любой из критических фиксов (БАГ 1–3) вызывает непредвиденные сбои в production, применяется откат через `git revert` по соответствующему коммиту с последующим хотфиксом.

---

## Glossary

- **Bug_Condition (C)**: Условие, при котором проявляется баг — конкретный входной сигнал или состояние системы, воспроизводящее дефект
- **Property (P)**: Ожидаемое корректное поведение при выполнении Bug_Condition
- **Preservation**: Существующее поведение, которое не должно измениться после исправления
- **isBugCondition**: Псевдокод-функция, формально описывающая условие проявления бага
- **process_pdf**: Оркестратор pipeline в `src/tasks.py` — запускает extraction → ratios → scoring → NLP → recommendations
- **analyze**: Функция в `AnalysisContext.tsx`, отвечающая за загрузку PDF и получение результата
- **CircuitBreaker**: Класс в `src/utils/circuit_breaker.py`, защищающий AI-сервис от каскадных сбоев
- **_is_valid_financial_value**: Функция в `src/analysis/pdf_extractor.py`, фильтрующая извлечённые числовые значения
- **PeriodInput**: Pydantic-модель в `src/models/schemas.py`, описывающая один период multi-period анализа
- **TESSERACT_AVAILABLE**: Флаг на уровне модуля `pdf_extractor.py`, определяющий доступность OCR

---

## Bug Details

### Bug Condition

Регрессии проявляются в 14 независимых местах кодовой базы. Каждый баг имеет свою Bug_Condition.

**Формальная спецификация (сводная):**

```
FUNCTION isBugCondition(context)
  INPUT: context — описание текущего состояния системы
  OUTPUT: boolean

  -- БАГ 1: неправильный flow на фронтенде
  IF context.file == "AnalysisContext.tsx"
     AND context.endpoint == "/analyze/pdf/file"
     AND context.hasPolling == False
  THEN RETURN True

  -- БАГ 2: хардкод Windows-пути
  IF context.file == "pdf_extractor.py"
     AND context.hasHardcodedWindowsPath == True
  THEN RETURN True

  -- БАГ 3: отсутствует file_path в PeriodInput
  IF context.file == "schemas.py"
     AND "file_path" NOT IN PeriodInput.fields
  THEN RETURN True

  -- БАГ 4: двойной timeout
  IF context.file == "recommendations.py"
     AND context.hasOuterWaitFor == True
     AND context.hasInnerWaitFor == True
  THEN RETURN True

  -- БАГ 5: threading.Lock в async-коде
  IF context.file == "circuit_breaker.py"
     AND context.lockType == "threading.Lock"
  THEN RETURN True

  -- БАГ 6: порог 1000 в _is_valid_financial_value
  IF context.file == "pdf_extractor.py"
     AND context.value IS NOT None
     AND abs(context.value) < 1000
     AND context.value NOT IN year_range(1900, 2101)
  THEN RETURN True

  -- БАГ 7: NameError в CORS
  IF context.file == "app.py"
     AND context.dev_mode == True
     AND context.corsOrigins IS INVALID
  THEN RETURN True

  -- БАГ 8: _mask_number(None) возвращает None
  IF context.file == "masking.py"
     AND context.input == None
     AND context.returnType != "str"
  THEN RETURN True

  -- БАГ 9–14: нарушения AGENTS.md и мелкие
  IF context.hasFStringInLogger == True
     OR context.hasInlineFunctionImport == True
     OR context.pdfplumberVersion == "0.11.9"
     OR context.hasUnconditionalConsoleLog == True
     OR context.hasErrAny == True
     OR context.docsDescribeDeepSeek == True
  THEN RETURN True

  RETURN False
END FUNCTION
```

### Примеры проявления багов

- **БАГ 1**: Пользователь загружает PDF → фронтенд делает `POST /analyze/pdf/file` с timeout 300s → зависает на 5 минут или падает с ошибкой; правильно: `POST /upload` → polling `GET /result/{task_id}`
- **БАГ 2**: Docker-контейнер импортирует `pdf_extractor.py` → код пытается установить `pytesseract.tesseract_cmd = "C:\Program Files\Tesseract-OCR\tesseract.exe"` → OCR не работает на Linux
- **БАГ 3**: Клиент отправляет multi-period запрос → `process_multi_analysis` вызывает `period.file_path` → `AttributeError: 'PeriodInput' object has no attribute 'file_path'`
- **БАГ 4**: `recommendations.py` оборачивает `ai_service.invoke(timeout=60)` в `asyncio.wait_for(timeout=65)`, а `tasks.py` оборачивает весь вызов ещё в `asyncio.wait_for(timeout=65)` — три вложенных timeout
- **БАГ 5**: Несколько async-задач одновременно вызывают `circuit_breaker.record_failure()` → `threading.Lock` блокирует event loop
- **БАГ 6**: PDF малого бизнеса с выручкой 500 руб. → `_is_valid_financial_value(500)` возвращает `False` → метрика отбрасывается; аналогично для коэффициентов (ROE = 0.15 → отбрасывается)
- **БАГ 7**: `app_settings.dev_mode=True`, `CORS_ALLOW_ORIGINS` содержит невалидное значение → `except ValueError` обращается к `default_origins` → `NameError`
- **БАГ 8**: `_mask_number(None)` возвращает `None` вместо `"—"` → нарушение типа `-> str`

---

## Expected Behavior

### Preservation Requirements

**Unchanged Behaviors:**
- Загрузка корректного PDF с финансовыми данными крупной компании (показатели > 1000) продолжает работать корректно
- OCR на Windows с установленным Tesseract продолжает работать через PATH или `TESSERACT_CMD`
- Single-period анализ через `/upload` → polling продолжает работать без изменений
- Circuit breaker в состоянии CLOSED без contention продолжает пропускать запросы без задержек
- `mask_analysis_data` с числовыми значениями (не None) продолжает корректно маскировать числа
- Приложение с валидным `CORS_ALLOW_ORIGINS` и `dev_mode=False` продолжает корректно настраивать CORS
- AI-сервис при недоступности продолжает возвращать fallback-рекомендации без краша
- Multi-period анализ при успешном завершении продолжает возвращать результаты, отсортированные хронологически
- Пользователь без API-ключа продолжает получать 401 и удаление ключа из localStorage
- `generate_recommendations` без AI-провайдера продолжает возвращать `FALLBACK_RECOMMENDATIONS`

**Scope:**
Все входные данные, не попадающие под Bug_Condition, должны быть полностью не затронуты исправлениями. Это включает:
- Корректные PDF с крупными финансовыми показателями
- Запросы к single-period анализу
- Работу circuit breaker без высокой нагрузки
- Маскировку числовых значений (не None)

---

## Hypothesized Root Cause

### БАГ 1 — AnalysisContext.tsx
Qwen заменил правильный polling-flow (POST `/upload` → GET `/result/{task_id}`) на синхронный вызов несуществующего эндпоинта `/analyze/pdf/file` с огромным timeout. Вероятно, агент не изучил существующий `usePdfAnalysis.ts` hook и написал упрощённую версию.

### БАГ 2 — pdf_extractor.py
Qwen добавил Windows-специфичный код на уровне модуля без условия проверки платформы. Код работает только на Windows-машине разработчика, ломает Docker/Linux.

### БАГ 3 — multi_analysis.py
Qwen создал `PeriodInput` без поля `file_path`, но `process_multi_analysis` в `tasks.py` обращается к `period.file_path`. Несогласованность между схемой и логикой обработки.

### БАГ 4 — recommendations.py
Qwen добавил `asyncio.wait_for` внутри `generate_recommendations`, не зная, что `tasks.py` уже оборачивает весь вызов в `asyncio.wait_for`. Результат — три вложенных timeout.

### БАГ 5 — circuit_breaker.py
Qwen использовал `threading.Lock` в async-коде, не учитывая, что блокирующий lock в async-контексте блокирует event loop. Правильный инструмент — `asyncio.Lock`.

### БАГ 6 — _is_valid_financial_value
Qwen добавил порог `abs(value) < 1000` для фильтрации "шума", не учитывая малый бизнес и финансовые коэффициенты (которые по определению < 1). Правильный подход — фильтровать только годы (1900–2100) и переполнение (> 1e15).

### БАГ 7 — app.py
Qwen переместил определение `default_origins` внутрь ветки `else` блока `try`, но `except ValueError` использует эту переменную. При `dev_mode=True` ветка `else` не выполняется → `NameError`.

### БАГ 8 — masking.py
Qwen не обновил сигнатуру `_mask_number` при добавлении обработки `None`. Функция возвращает `None` вместо строки, нарушая объявленный тип `-> str`.

### БАГ 9–14
Нарушения правил AGENTS.md (f-строки, inline-импорты, версия pdfplumber) и мелкие проблемы (console.log, err: any, документация) — результат того, что Qwen не читал AGENTS.md перед написанием кода.

---

## Correctness Properties

Property 1: Bug Condition — Polling Termination

_For any_ последовательности ответов от сервера (completed, failed, processing, 404, 5xx, timeout, connection refused), функция `analyze` в `AnalysisContext.tsx` SHALL завершить polling за конечное число шагов не более `MAX_POLLING_ATTEMPTS=15`, либо при получении `status: "completed"` или `status: "failed"`, либо при HTTP 404, либо после исчерпания попыток.

Дополнительные условия:
- Сетевые ошибки (timeout, connection refused) SHALL считаться как попытка и вызывать `setTimeout(poll, POLLING_INTERVAL)` — не прерывать polling немедленно
- При unmount компонента SHALL вызываться `clearTimeout(timeoutId)` и устанавливаться флаг `cancelled = true`, предотвращая `setState` на размонтированном компоненте

**Validates: Requirements 2.1, 2.2, 2.3, 2.4, 2.5**

Property 2: Preservation — Masking Idempotency

_For any_ словаря `data` с числовыми значениями, `mask_analysis_data(mask_analysis_data(data, True), True)` SHALL быть равно `mask_analysis_data(data, True)` — повторное применение маскировки не изменяет уже замаскированные данные.

**Validates: Requirements 3.5**

Property 3: Bug Condition — Financial Value Filter

_For any_ числового значения `v`, `_is_valid_financial_value(v)` SHALL возвращать `True` тогда и только тогда, когда все условия выполнены:
- `v is not None`
- `abs(v) <= 1e15`
- НЕ является целым числом в диапазоне 1900–2100

Проверка на "целое число" SHALL использовать безопасное float-сравнение:
```python
def _is_year(v: float) -> bool:
    if isinstance(v, int):
        return 1900 <= v <= 2100
    if isinstance(v, float) and v.is_integer():
        return 1900 <= int(v) <= 2100
    return False
```
Это предотвращает ложные срабатывания для значений типа `1999.9999999999998` (результат float-арифметики), которые `v == int(v)` может некорректно классифицировать.

В частности, функция SHALL принимать значения в диапазоне `(0, 1000)` (коэффициенты, малый бизнес) и отклонять целые числа 1900–2100 (годы).

**Validates: Requirements 2.16, 2.17, 3.1**

Property 4: Bug Condition — Circuit Breaker State Machine

_For any_ последовательности вызовов `record_success()` и `record_failure()`, переходы состояний CircuitBreaker SHALL соответствовать автомату: CLOSED→OPEN (при `failure_count >= threshold`), OPEN→HALF_OPEN (после `recovery_timeout`), HALF_OPEN→CLOSED (при `record_success`), HALF_OPEN→OPEN (при `record_failure`). Никакие другие переходы недопустимы.

**Validates: Requirements 2.14, 3.4**

Property 5: Bug Condition — Single Timeout Control

_For any_ вызова `generate_recommendations`, на стеке вызовов SHALL существовать ровно один `asyncio.wait_for` — в `tasks.py`. Вложенный `asyncio.wait_for` в `recommendations.py` SHALL отсутствовать.

**Validates: Requirements 2.12, 2.13**

---

## Fix Implementation

### Changes Required

#### БАГ 1 — `frontend/src/context/AnalysisContext.tsx`

**Специфические изменения:**
1. Заменить `POST /analyze/pdf/file` на `POST /upload` для получения `task_id`
2. Добавить константы `MAX_POLLING_ATTEMPTS = 15` и `POLLING_INTERVAL = 2000`
3. Реализовать рекурсивный polling через `setTimeout` с счётчиком попыток и флагом `cancelled`
4. Обработать HTTP 404 → остановить polling, показать "Задача не найдена"
5. Обработать HTTP 5xx → retry (считается как попытка), `setTimeout(poll, POLLING_INTERVAL)`
6. Обработать сетевые ошибки (timeout, connection refused) → retry (считается как попытка), `setTimeout(poll, POLLING_INTERVAL)`
7. Добавить `useRef<ReturnType<typeof setTimeout>>` для хранения `timeoutId`; в cleanup-функции `useEffect` вызывать `clearTimeout(timeoutId.current)` и устанавливать `cancelled = true`
8. Заменить `err: any` на `err: unknown` с type guard

#### БАГ 2 — `src/analysis/pdf_extractor.py`

**Специфические изменения:**
1. Удалить блок хардкода `_tesseract_path = os.path.expandvars(r"C:\Program Files\...")`
2. Добавить опциональную поддержку `TESSERACT_CMD` из env
3. Добавить функцию `_check_tesseract_available() -> bool` с `try/except`
4. Добавить флаг `TESSERACT_AVAILABLE = _check_tesseract_available()` на уровне модуля
5. В `extract_text_from_scanned` проверять `TESSERACT_AVAILABLE` перед вызовом OCR

#### БАГ 3 — `src/models/schemas.py` и `src/routers/multi_analysis.py`

**Специфические изменения в `src/models/schemas.py`:**
1. Добавить поле `file_path: str = Field(description="Путь к временному PDF-файлу для этого периода")` в `PeriodInput`

**Специфические изменения в `src/routers/multi_analysis.py`:**

Роутер должен принимать multipart/form-data с несколькими файлами и метками периодов:

```python
@router.post("", status_code=202, response_model=MultiAnalysisAcceptedResponse)
async def start_multi_analysis(
    background_tasks: BackgroundTasks,
    files: list[UploadFile] = File(...),       # PDF-файлы для каждого периода
    periods: list[str] = Form(...),             # метки периодов (например, ["2021", "2022"])
    _api_key: str = Depends(get_api_key),
) -> MultiAnalysisAcceptedResponse:
    # Валидация: количество файлов должно совпадать с количеством меток
    if len(files) != len(periods):
        raise HTTPException(status_code=422, detail="Количество файлов должно совпадать с количеством меток периодов")
    if len(files) > 5:
        raise HTTPException(status_code=422, detail="Максимум 5 периодов")

    # Сохранение файлов во временные файлы
    period_inputs = []
    for file, label in zip(files, periods):
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
        content = await file.read()
        tmp.write(content)
        tmp.close()
        period_inputs.append(PeriodInput(period_label=label, file_path=tmp.name))

    session_id = str(uuid4())
    await create_multi_session(session_id)
    background_tasks.add_task(process_multi_analysis, session_id, period_inputs)
    return MultiAnalysisAcceptedResponse(session_id=session_id, status="processing")
```

Временные файлы очищаются в `process_multi_analysis` после обработки каждого периода через `_cleanup_temp_file`.

#### БАГ 4 — `src/analysis/recommendations.py`

**Специфические изменения:**
1. Удалить внешний `asyncio.wait_for(timeout=65.0)` из `generate_recommendations`
2. Оставить только `ai_service.invoke(timeout=60)` — единственный timeout внутри invoke
3. Внешний `asyncio.wait_for` в `tasks.py` остаётся без изменений

#### БАГ 5 — `src/utils/circuit_breaker.py` и `src/core/ai_service.py`

**Специфические изменения:**
1. Заменить `from threading import Lock` на `import asyncio`
2. Изменить `self._lock = Lock()` на `self._lock = asyncio.Lock()`
3. Сделать `record_success`, `record_failure`, `reset` async-методами с `async with self._lock`
4. Убрать lock из синхронных свойств `is_available`, `state` (read-only, атомарные операции)
5. Добавить комментарий `# NB: не выполнять длительные await внутри with lock`
6. В `ai_service.py` обновить вызовы: `await ai_circuit_breaker.record_success()`, `await ai_circuit_breaker.record_failure()`

#### БАГ 6 — `src/analysis/pdf_extractor.py`

**Специфические изменения:**
1. Добавить вспомогательную функцию `_is_year(v: float) -> bool` с безопасным float-сравнением:
   ```python
   def _is_year(v: float) -> bool:
       if isinstance(v, int):
           return 1900 <= v <= 2100
       if isinstance(v, float) and v.is_integer():
           return 1900 <= int(v) <= 2100
       return False
   ```
2. В `_is_valid_financial_value` убрать проверку `abs(value) < 1000`
3. Заменить `if value == int(value) and int(value) in _YEAR_RANGE` на `if _is_year(value)`
4. Оставить фильтр переполнения: `if abs(value) > 1e15: return False`

#### БАГ 7 — `src/app.py`

**Специфические изменения:**
1. Переместить определение `default_origins = [...]` до блока `try/except`

#### БАГ 8 — `src/utils/masking.py`

**Специфические изменения:**
1. Добавить константу `MASKED_NONE_VALUE = "—"` на уровне модуля
2. Обновить сигнатуру: `def _mask_number(value: float | int | None) -> str`
3. Заменить `return None` на `return MASKED_NONE_VALUE`

#### БАГ 9 — f-строки в логах

**Файлы:** `src/app.py`, `src/tasks.py`, `src/core/ai_service.py`, `src/utils/circuit_breaker.py`, `src/utils/retry_utils.py`

**Специфические изменения:**
1. Заменить все `logger.info(f"...")`, `logger.warning(f"...")`, `logger.error(f"...")` на `%`-форматирование
2. Пример: `logger.info(f"PDF processing completed: {task_id}")` → `logger.info("PDF processing completed: %s", task_id)`

#### БАГ 10 — `src/tasks.py`

**Специфические изменения:**
1. Перенести `from src.analysis.nlp_analysis import analyze_narrative` на уровень модуля
2. Перенести `from src.analysis.recommendations import generate_recommendations` на уровень модуля
3. Проверить существование `src/controllers/analyze.py` и `_extract_metrics_with_regex`; если файл существует — перенести импорт на уровень модуля; если нет — удалить вызов или заменить на inline-реализацию

#### БАГ 11 — `requirements.txt`

**Специфические изменения:**
1. Заменить `pdfplumber~=0.11.9` на `pdfplumber~=0.12.0`

#### БАГ 12 — `frontend/src/api/client.ts`

**Специфические изменения:**
1. Обернуть `console.log` в request interceptor в `if (import.meta.env.DEV)`
2. Обернуть `console.log` и `console.error` в response interceptor в `if (import.meta.env.DEV)`

#### БАГ 13 — TypeScript `err: any`

**Файлы:** `frontend/src/context/AnalysisContext.tsx`, `frontend/src/pages/AnalysisHistory.tsx`

**Специфические изменения:**
1. Заменить `catch (err: any)` на `catch (err: unknown)`
2. Для извлечения сообщения использовать: `const axiosMsg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail; const finalMsg = axiosMsg || (err instanceof Error ? err.message : 'Ошибка');`

#### БАГ 14 — `docs/CONFIGURATION.md`

**Специфические изменения:**
1. Заменить упоминания "DeepSeek" на "HuggingFace (Qwen/Qwen3.5-9B-Instruct)"
2. Добавить переменные `HF_TOKEN`, `HF_MODEL` с актуальными дефолтами
3. Добавить `QWEN_API_KEY`, `QWEN_API_URL` как deprecated-провайдер

---

## Testing Strategy

### Validation Approach

Стратегия тестирования следует двухфазному подходу: сначала воспроизвести баг на незафиксированном коде (exploratory), затем верифицировать исправление и убедиться в отсутствии регрессий (fix + preservation checking).

### Exploratory Bug Condition Checking

**Goal**: Воспроизвести баги ДО исправления, подтвердить root cause анализ.

**Test Plan**: Написать тесты, симулирующие каждый баг, и запустить их на незафиксированном коде.

**Test Cases:**
1. **Polling test (БАГ 1)**: Вызвать `analyze(file)` с моком `apiClient` → убедиться, что делается запрос к `/analyze/pdf/file` вместо `/upload` (будет падать на исправленном коде)
2. **Tesseract hardcode test (БАГ 2)**: Импортировать `pdf_extractor` в Linux-окружении → убедиться, что `pytesseract.tesseract_cmd` не установлен в Windows-путь
3. **PeriodInput.file_path test (БАГ 3)**: Создать `PeriodInput(period_label="2023")` → обратиться к `.file_path` → ожидать `AttributeError`
4. **Double timeout test (БАГ 4)**: Замокать `ai_service.invoke` с задержкой → убедиться, что `asyncio.wait_for` вызывается дважды
5. **threading.Lock test (БАГ 5)**: Запустить несколько async-задач, обращающихся к `circuit_breaker` → убедиться в использовании `threading.Lock`
6. **Financial value filter test (БАГ 6)**: Вызвать `_is_valid_financial_value(0.15)` → ожидать `False` (баг) / `True` (после исправления)
7. **NameError test (БАГ 7)**: Запустить `app.py` с `dev_mode=True` и невалидным `CORS_ALLOW_ORIGINS` → ожидать `NameError`
8. **Mask None test (БАГ 8)**: Вызвать `_mask_number(None)` → ожидать `None` (баг) / `"—"` (после исправления)

**Expected Counterexamples:**
- `_is_valid_financial_value(0.15)` возвращает `False` — коэффициенты отбрасываются
- `PeriodInput(period_label="2023").file_path` бросает `AttributeError`
- `_mask_number(None)` возвращает `None` вместо строки

### Fix Checking

**Goal**: Верифицировать, что для всех входных данных, где Bug_Condition выполняется, исправленный код ведёт себя корректно.

**Pseudocode:**
```
FOR ALL input WHERE isBugCondition(input) DO
  result := fixedFunction(input)
  ASSERT expectedBehavior(result)
END FOR
```

**Конкретные проверки:**
- `_is_valid_financial_value(0.15)` → `True`
- `_is_valid_financial_value(500)` → `True`
- `_is_valid_financial_value(2023)` → `False` (год)
- `_mask_number(None)` → `"—"`
- `PeriodInput(period_label="2023", file_path="/tmp/file.pdf").file_path` → `"/tmp/file.pdf"`
- Polling завершается за ≤ 15 попыток при любом ответе сервера

### Preservation Checking

**Goal**: Верифицировать, что для всех входных данных, где Bug_Condition НЕ выполняется, исправленный код ведёт себя идентично оригинальному.

**Pseudocode:**
```
FOR ALL input WHERE NOT isBugCondition(input) DO
  ASSERT originalFunction(input) = fixedFunction(input)
END FOR
```

**Testing Approach**: Property-based тестирование рекомендуется для:
- `_is_valid_financial_value` — генерация случайных чисел вне диапазона 1900–2100 и > 1000
- `mask_analysis_data` — генерация случайных словарей с числовыми значениями
- Circuit breaker state machine — генерация случайных последовательностей вызовов

**Test Cases:**
1. **Large financial values (БАГ 6)**: `_is_valid_financial_value(1_000_000)` → `True` (как раньше)
2. **Masking non-None (БАГ 8)**: `_mask_number(1234567.89)` → `"X,XXX,XXX.XX"` (как раньше)
3. **CORS valid config (БАГ 7)**: Запуск с валидным `CORS_ALLOW_ORIGINS` → корректная настройка CORS
4. **Circuit breaker CLOSED (БАГ 5)**: Одиночные вызовы `record_success/failure` → корректные переходы состояний
5. **Recommendations fallback (БАГ 4)**: `generate_recommendations` без AI → `FALLBACK_RECOMMENDATIONS`

### Unit Tests

- `test_is_valid_financial_value`: проверить граничные значения (None, 0, 0.15, 500, 999, 1000, 1900, 2023, 2100, 2101, 1e15, 1e16)
- `test_mask_number_none`: `_mask_number(None)` → `"—"`
- `test_mask_number_values`: существующие числовые значения маскируются корректно
- `test_period_input_file_path`: `PeriodInput` принимает и возвращает `file_path`
- `test_cors_default_origins_defined`: `default_origins` доступна в `except ValueError`
- `test_circuit_breaker_async_lock`: `CircuitBreaker` использует `asyncio.Lock`, не `threading.Lock`
- `test_recommendations_no_double_timeout`: `generate_recommendations` не содержит внешнего `asyncio.wait_for`
- `test_client_ts_conditional_log`: `console.log` в interceptors обёрнут в `import.meta.env.DEV`

### Property-Based Tests

- **Polling termination** (Hypothesis): для любой последовательности ответов сервера (completed/failed/processing/404/5xx) polling завершается за ≤ 15 шагов
- **Masking idempotency** (Hypothesis): `mask_analysis_data(mask_analysis_data(data, True), True) == mask_analysis_data(data, True)` для любого словаря `data`
- **Financial value filter** (Hypothesis): `_is_valid_financial_value(v)` возвращает `True` для всех `v` в `(0, 1e15)` кроме целых 1900–2100
- **Circuit breaker state machine** (Hypothesis): для любой последовательности `record_success/record_failure` переходы состояний соответствуют автомату

### Integration Tests

- Полный flow: `POST /upload` → polling `GET /result/{task_id}` → `status: "completed"` → результат отображается
- Multi-period анализ с `file_path` в `PeriodInput` → корректная обработка без `AttributeError`
- Запуск приложения с `dev_mode=True` и невалидным `CORS_ALLOW_ORIGINS` → нет `NameError`, используются `default_origins`
- OCR в Docker/Linux без `TESSERACT_CMD` → graceful degradation, только текстовый слой PDF
