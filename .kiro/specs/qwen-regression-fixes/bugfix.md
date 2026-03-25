# Bugfix Requirements Document

## Introduction

В ходе частичного переписывания проекта NeoFin AI другим AI-агентом (Qwen) были внесены регрессии в 14 местах кодовой базы. Баги охватывают критические нарушения архитектуры (неправильный flow анализа, хардкод Windows-путей, сломанная multi-period модель), серьёзные проблемы надёжности (двойной timeout, threading.Lock в async-коде, неверная фильтрация финансовых значений, NameError при старте, нарушение type hint), нарушения правил AGENTS.md (f-строки в логах, импорты внутри функций, откат версии pdfplumber), а также мелкие нарушения (console.log в production, `err: any` в TypeScript, устаревшая документация).

---

## Bug Analysis

### Current Behavior (Defect)

**БАГ 1 — AnalysisContext.tsx: неправильный эндпоинт и нет polling**

1.1 WHEN пользователь загружает PDF-файл через фронтенд THEN система отправляет синхронный POST `/analyze/pdf/file` с timeout 300000ms вместо правильного flow POST `/upload` → polling GET `/result/{task_id}`

1.2 WHEN анализ занимает более нескольких секунд THEN система зависает на 5 минут или падает с timeout-ошибкой, не показывая прогресс

1.3 WHEN polling возвращает HTTP 404 (task_id не найден) или HTTP 5xx THEN система не имеет определённой стратегии обработки — возможен бесконечный лоадер или краш

**БАГ 2 — pdf_extractor.py: хардкод Windows-пути к Tesseract**

1.4 WHEN модуль `pdf_extractor.py` импортируется в Docker/Linux-окружении THEN система пытается установить `pytesseract.tesseract_cmd` на `C:\Program Files\Tesseract-OCR\tesseract.exe` на уровне модуля

1.5 WHEN OCR требуется для скан-PDF в Docker/Linux THEN система не может найти Tesseract и OCR не работает

1.6 WHEN Tesseract не установлен вообще (ни в PATH, ни по `TESSERACT_CMD`) THEN система падает с необработанным исключением вместо graceful degradation

**БАГ 3 — multi_analysis.py: file_path не передаётся в periods** ⚠️ BREAKING CHANGE

1.7 WHEN клиент отправляет запрос на multi-period анализ THEN `MultiAnalysisRequest.periods` содержит только `period_label` (строки), без поля `file_path`

1.8 WHEN `process_multi_analysis` вызывает `_process_single_period(period.period_label, period.file_path)` THEN система падает с `AttributeError: 'PeriodInput' object has no attribute 'file_path'`

**БАГ 4 — recommendations.py: двойной timeout**

1.9 WHEN генерируются рекомендации THEN существует внешний `asyncio.wait_for(timeout=65)` в `tasks.py`, внутренний `asyncio.wait_for(timeout=65)` в `recommendations.py`, и ещё `ai_service.invoke(timeout=60)` — итого три вложенных timeout для одной операции

1.10 WHEN внутренний timeout срабатывает раньше внешнего THEN поведение непредсказуемо и сложно отлаживать

**БАГ 5 — circuit_breaker.py: threading.Lock в async-коде**

1.11 WHEN несколько async-задач одновременно обращаются к `CircuitBreaker` THEN `threading.Lock` блокирует event loop при contention

1.12 WHEN нагрузка на систему высокая THEN возможны deadlocks из-за блокирующего `threading.Lock` в async-контексте

**БАГ 6 — pdf_extractor.py: _is_valid_financial_value отбрасывает значения < 1000**

1.13 WHEN PDF содержит финансовые показатели малого бизнеса (выручка < 1000 руб.) THEN функция `_is_valid_financial_value` возвращает `False` и значение отбрасывается

1.14 WHEN PDF содержит финансовые коэффициенты (например, ROE = 0.15, current_ratio = 1.5) THEN функция `_is_valid_financial_value` отбрасывает их как "слишком маленькие" (< 1000)

**БАГ 7 — app.py: NameError в CORS except блоке**

1.15 WHEN приложение запускается с `dev_mode=False` и невалидным значением `CORS_ALLOW_ORIGINS` THEN в блоке `except ValueError` используется переменная `default_origins`, которая определяется только внутри ветки `else` (не `dev_mode`)

1.16 WHEN срабатывает `except ValueError` при `dev_mode=True` THEN `default_origins` не определена и возникает `NameError: name 'default_origins' is not defined`

**БАГ 8 — masking.py: _mask_number возвращает None вместо str**

1.17 WHEN `_mask_number` вызывается со значением `None` THEN функция возвращает `None`, нарушая объявленный тип возврата `-> str`

1.18 WHEN результат `_mask_number(None)` используется в контексте, ожидающем строку THEN возникают ошибки типизации и потенциальные runtime-ошибки

**БАГ 9 — f-строки в логах (40+ мест)**

1.19 WHEN в `src/app.py`, `src/tasks.py`, `src/core/ai_service.py`, `src/utils/circuit_breaker.py`, `src/utils/retry_utils.py` вызываются методы `logger.*()` THEN используются f-строки вместо `%`-форматирования, что нарушает правило AGENTS.md

**БАГ 10 — tasks.py: импорты внутри функций**

1.20 WHEN выполняется функция `process_pdf()` THEN внутри неё находятся `from src.controllers.analyze import _extract_metrics_with_regex`, `from src.analysis.nlp_analysis import analyze_narrative` и `from src.analysis.recommendations import generate_recommendations` — импорты на уровне функции, что нарушает правило AGENTS.md

**БАГ 11 — requirements.txt: откат версии pdfplumber**

1.21 WHEN используется `pdfplumber~=0.11.9` THEN применяется версия с известной проблемой, зафиксированной в `local_notes.md`; правильная версия `~=0.12.0`

**БАГ 12 — client.ts: console.log в production**

1.22 WHEN выполняются HTTP-запросы через `apiClient` в production THEN в консоль браузера выводятся `console.log` и `console.error` с деталями запросов и ответов

**БАГ 13 — TypeScript: err: any (нарушение strict mode)**

1.23 WHEN в `AnalysisContext.tsx` и `AnalysisHistory.tsx` перехватываются ошибки в catch-блоках THEN используется тип `err: any`, что нарушает TypeScript strict mode

**БАГ 14 — Документация устарела**

1.24 WHEN разработчик читает `docs/CONFIGURATION.md` THEN документация описывает DeepSeek как AI-провайдер, тогда как код использует Qwen/Qwen3.5-9B-Instruct через `huggingface_agent`

---

### Expected Behavior (Correct)

**БАГ 1 — AnalysisContext.tsx**

2.1 WHEN пользователь загружает PDF-файл через фронтенд THEN система SHALL отправить POST `/upload` для получения `task_id`, затем выполнять polling GET `/result/{task_id}` каждые 2000ms до завершения анализа

2.2 WHEN анализ выполняется в фоне THEN система SHALL отображать прогресс через polling и не зависать

2.3 WHEN polling возвращает HTTP 404 THEN система SHALL остановить polling и показать сообщение "Задача не найдена"

2.4 WHEN polling возвращает HTTP 5xx THEN система SHALL повторить запрос, суммарное количество попыток SHALL не превышать `MAX_POLLING_ATTEMPTS=15`; после исчерпания попыток система SHALL показать сообщение об ошибке

2.5 WHEN суммарное время polling превышает 30 секунд без успешного ответа THEN система SHALL остановить polling и показать сообщение об ошибке

**БАГ 2 — pdf_extractor.py**

2.6 WHEN модуль `pdf_extractor.py` импортируется в любом окружении THEN система SHALL НЕ устанавливать хардкод Windows-путь к Tesseract на уровне модуля; путь к Tesseract SHALL определяться только через переменную окружения `TESSERACT_CMD` или системный PATH

2.7 WHEN OCR требуется в Docker/Linux THEN система SHALL корректно использовать Tesseract из системного PATH без Windows-специфичного кода

2.8 WHEN Tesseract не установлен (ни в PATH, ни по `TESSERACT_CMD`) THEN система SHALL перехватить исключение, залогировать предупреждение "OCR недоступен: установите tesseract-ocr" и вернуть только текстовый слой PDF без OCR (graceful degradation)

**БАГ 3 — multi_analysis.py** ⚠️ BREAKING CHANGE

2.9 WHEN клиент отправляет запрос на multi-period анализ THEN `PeriodInput` SHALL содержать поле `file_path: str` наряду с `period_label`; это изменение является breaking change в контракте API и должно быть задокументировано в CHANGELOG

2.10 WHEN `process_multi_analysis` вызывает `_process_single_period` THEN система SHALL корректно передавать `period.file_path` без `AttributeError`

2.11 WHEN клиент использует старый формат запроса (без `file_path`) THEN система SHALL вернуть HTTP 422 с явным сообщением о недостающем поле

**БАГ 4 — recommendations.py**

2.12 WHEN генерируются рекомендации THEN SHALL существовать только один timeout-контроль: `asyncio.wait_for` в `tasks.py` с таймаутом `REC_TIMEOUT` (из env, дефолт 65s); дублирующий `asyncio.wait_for` в `recommendations.py` SHALL быть удалён; `ai_service.invoke` вызывается без дополнительного внешнего `wait_for`

2.13 WHEN timeout срабатывает THEN система SHALL залогировать предупреждение с указанием фактического значения `REC_TIMEOUT` и вернуть fallback-рекомендации

**БАГ 5 — circuit_breaker.py**

2.14 WHEN несколько async-задач одновременно обращаются к `CircuitBreaker` THEN система SHALL использовать `asyncio.Lock` вместо `threading.Lock` для защиты состояния circuit breaker

2.15 WHEN используется `asyncio.Lock` THEN код SHALL содержать комментарий `# NB: не выполнять длительные await внутри with lock` для предотвращения будущих ошибок

**БАГ 6 — pdf_extractor.py**

2.16 WHEN PDF содержит финансовые показатели любого масштаба THEN `_is_valid_financial_value` SHALL убрать нижний порог 1000; функция SHALL отклонять только: значения `None`, числа в диапазоне лет `1900–2100` (вероятно, год отчётности), и числа с абсолютным значением `> 1e15` (ошибка парсинга)

2.17 WHEN функция применяется к сырым метрикам (выручка, активы) THEN контекстная валидация масштаба SHALL осуществляться на уровне `_METRIC_KEYWORDS` через разные ключи, а не через единый числовой порог

**БАГ 7 — app.py**

2.18 WHEN приложение запускается с любой комбинацией `dev_mode` и значений `CORS_ALLOW_ORIGINS` THEN переменная `default_origins` SHALL быть определена до блока `try/except`, чтобы быть доступной в `except ValueError`

**БАГ 8 — masking.py**

2.19 WHEN `_mask_number` вызывается со значением `None` THEN функция SHALL возвращать константу `MASKED_NONE_VALUE = "—"` в соответствии с объявленным типом `-> str`

2.20 WHEN `MASKED_NONE_VALUE` используется в проекте THEN это SHALL быть единственная константа для представления замаскированного отсутствующего значения во всём модуле `masking.py`

**БАГ 9 — f-строки в логах**

2.21 WHEN в коде вызываются методы `logger.*()` THEN SHALL использоваться `%`-форматирование (`logger.info("msg %s", var)`) вместо f-строк во всех файлах: `src/app.py`, `src/tasks.py`, `src/core/ai_service.py`, `src/utils/circuit_breaker.py`, `src/utils/retry_utils.py`

**БАГ 10 — tasks.py**

2.22 WHEN модуль `tasks.py` загружается THEN все импорты SHALL находиться на уровне модуля, а не внутри функций `process_pdf()` и других

**БАГ 11 — requirements.txt**

2.23 WHEN устанавливаются зависимости THEN `pdfplumber` SHALL иметь версию `~=0.12.0` согласно `local_notes.md`

**БАГ 12 — client.ts**

2.24 WHEN выполняются HTTP-запросы через `apiClient` THEN `console.log`/`console.error` в interceptors SHALL выводиться только при `import.meta.env.DEV === true`; в production-сборке логи SHALL отсутствовать

**БАГ 13 — TypeScript strict mode**

2.25 WHEN в `AnalysisContext.tsx` и `AnalysisHistory.tsx` перехватываются ошибки THEN SHALL использоваться `unknown` вместо `any`; для извлечения сообщения об ошибке SHALL применяться inline type guard: `err instanceof Error ? err.message : String(err)`

**БАГ 14 — Документация**

2.26 WHEN разработчик читает `docs/CONFIGURATION.md` THEN документация SHALL корректно описывать актуальные AI-провайдеры (GigaChat, HuggingFace с моделью Qwen/Qwen3.5-9B-Instruct, Ollama) и соответствующие переменные окружения (`HF_TOKEN`, `HF_MODEL`)

---

### Unchanged Behavior (Regression Prevention)

3.1 WHEN загружается корректный PDF с финансовыми данными крупной компании (показатели > 1000) THEN система SHALL CONTINUE TO корректно извлекать метрики и рассчитывать коэффициенты

3.2 WHEN OCR-анализ запускается на Windows-машине с установленным Tesseract THEN система SHALL CONTINUE TO корректно находить и использовать Tesseract (через PATH или `TESSERACT_CMD`)

3.3 WHEN выполняется single-period анализ через `/upload` → polling THEN система SHALL CONTINUE TO работать без изменений

3.4 WHEN circuit breaker находится в состоянии CLOSED и нет contention THEN система SHALL CONTINUE TO пропускать запросы к AI-сервису без задержек

3.5 WHEN `mask_analysis_data` вызывается с числовыми значениями (не None) THEN система SHALL CONTINUE TO корректно маскировать числа в формате "X,XXX"

3.6 WHEN приложение запускается с валидным `CORS_ALLOW_ORIGINS` и `dev_mode=False` THEN система SHALL CONTINUE TO корректно настраивать CORS без ошибок

3.7 WHEN AI-сервис недоступен THEN система SHALL CONTINUE TO возвращать fallback-рекомендации без краша

3.8 WHEN multi-period анализ завершается успешно THEN система SHALL CONTINUE TO возвращать результаты, отсортированные хронологически

3.9 WHEN `pdfplumber` используется для извлечения таблиц THEN система SHALL CONTINUE TO корректно работать с версией `~=0.12.0`

3.10 WHEN пользователь не авторизован (нет API-ключа) THEN система SHALL CONTINUE TO возвращать 401 и удалять ключ из localStorage

3.11 WHEN polling возвращает `status: "completed"` THEN система SHALL CONTINUE TO останавливать polling и отображать результат анализа

3.12 WHEN `generate_recommendations` вызывается без AI-провайдера THEN система SHALL CONTINUE TO возвращать `FALLBACK_RECOMMENDATIONS` без исключений
