# NeoFin AI — Architecture

## 1. Быстрый старт для агента

NeoFin AI — ИИ-ассистент финансового директора: принимает PDF-отчёты компаний, извлекает финансовые данные, вычисляет 12 коэффициентов, строит интегральный скоринг 0–100, генерирует NLP-рекомендации через GigaChat/Hugging Face/Ollama.
Точка входа backend: `src/app.py` (FastAPI app, middleware, routers, lifespan).
Точка входа frontend: `frontend/src/App.tsx` (роутинг, провайдеры, lazy-загрузка страниц).
Локальный запуск: `docker-compose up --build` — поднимает backend, frontend/nginx, db, db_test, ollama.

---

## 2. Структура слоёв

```
┌─────────────────────────────────────────────────────────┐
│         Frontend: React 19 / Mantine 8 / Vite 6         │
│  frontend/src/pages/, frontend/src/components/          │
│  Отвечает: UI, polling, отображение результатов         │
│  НЕ должно: содержать бизнес-логику, прямые SQL-запросы │
└────────────────────┬────────────────────────────────────┘
                     │ HTTP REST (axios)
                     │ POST /upload → GET /result/{id} (polling 2000ms)
┌────────────────────▼────────────────────────────────────┐
│              API Layer: FastAPI routers                  │
│  src/routers/upload.py, src/routers/result.py           │
│  Отвечает: валидация входа, HTTP-ответы, auth-проверка  │
│  НЕ должно: содержать бизнес-логику, импортировать БД   │
└────────────────────┬────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────┐
│            Controllers: бизнес-логика запроса           │
│  src/controllers/ (если выделены) или src/tasks.py      │
│  Отвечает: оркестрация pipeline, маппинг ключей         │
│  НЕ должно: импортировать из routers, знать о HTTP      │
└────────────────────┬────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────┐
│         Analysis Pipeline                               │
│  src/analysis/pdf_extractor.py                          │
│       → src/analysis/ratios.py                          │
│       → src/analysis/scoring.py                         │
│       → src/analysis/nlp_analysis.py                    │
│  Отвечает: чистые функции над данными                   │
│  НЕ должно: знать о FastAPI, HTTP, БД, AI-провайдерах  │
└────────────────────┬────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────┐
│              AI Service                                  │
│  src/core/ai_service.py  ← единственная точка входа     │
│       → src/core/gigachat_agent.py (GigaChat)           │
│       → src/core/agent.py (Qwen)                        │
│       → ollama HTTP (fallback)                          │
│  Отвечает: выбор провайдера, retry, graceful degrade    │
│  НЕ должно: вызываться напрямую минуя ai_service.py     │
└────────────────────┬────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────┐
│         Database Layer: SQLAlchemy async + PostgreSQL    │
│  src/db/database.py  — engine, session factory          │
│  src/db/crud.py      — ЕДИНСТВЕННЫЙ файл с session.add()│
│  src/db/models.py    — ORM-модели                       │
│  НЕ должно: содержать бизнес-логику, HTTP-зависимости   │
└─────────────────────────────────────────────────────────┘
```

**Правила зависимостей (нарушение = баг архитектуры):**
- `routers/*` → только валидация + вызов функций из `tasks.py` или controllers; никакой логики внутри
- `controllers` / `tasks.py` → не импортируют ничего из `routers/`
- `src/analysis/*` → нет импортов `fastapi`, `sqlalchemy`, `httpx`/`requests` к AI
- `src/core/gigachat_agent.py`, `src/core/agent.py` → вызываются только из `src/core/ai_service.py`
- `session.add()`, `session.commit()`, `session.execute()` → только в `src/db/crud.py`

---

## 3. Файловая структура проекта

```
src/
├── app.py                        # точка входа FastAPI: middleware, lifespan, подключение routers
├── tasks.py                      # process_pdf(): BackgroundTask, RATIO_KEY_MAP, _build_score_payload()
├── analysis/
│   ├── __init__.py
│   ├── pdf_extractor.py          # извлечение текста (PyPDF2), таблиц (camelot/pdfplumber), OCR (tesseract)
│   ├── ratios.py                 # 5 финансовых коэффициентов; возвращает русскоязычные ключи
│   ├── scoring.py                # интегральный скоринг 0–100; weights dict; возвращает details: dict
│   └── nlp_analysis.py           # NLP-анализ через ai_service; [MEDIUM] закомментирован в tasks.py
├── core/
│   ├── __init__.py
│   ├── ai_service.py             # AIService: _configure(), выбор провайдера, graceful degrade
│   ├── gigachat_agent.py         # GigaChat: OAuth2 flow, SSL, Bearer token кеш 55 мин, retry 3x
│   └── agent.py                  # Qwen: Bearer token, retry 3x exponential backoff
├── db/
│   ├── __init__.py
│   ├── database.py               # get_engine() lazy init, AsyncSession factory, get_db() dependency
│   ├── models.py                 # ORM-модель Analysis (таблица analyses)
│   └── crud.py                   # create_analysis(), get_analysis(), update_analysis() — только здесь SQL
├── models/
│   ├── __init__.py
│   ├── schemas.py                # Pydantic-схемы: UploadResponse, AnalysisResult, RatiosSchema и др.
│   └── settings.py               # Settings(BaseSettings): все env-переменные с валидацией
├── routers/
│   ├── __init__.py
│   ├── upload.py                 # POST /upload: валидация PDF, magic header, size ≤50MB, BackgroundTask
│   └── result.py                 # GET /result/{task_id}: чтение статуса из БД
└── utils/
    └── __init__.py

frontend/
├── index.html
├── vite.config.ts                # Vite 6, proxy /api → backend:8000
├── tsconfig.json
├── package.json
└── src/
    ├── App.tsx                   # роутинг (React Router 7), lazy-страницы, провайдеры
    ├── main.tsx                  # точка входа React, MantineProvider
    ├── api/
    │   ├── client.ts             # axios instance, baseURL, X-API-Key header
    │   ├── interfaces.ts         # ОСНОВНОЙ контракт данных: AnalysisResult, Ratios, Score и др.
    │   └── types.ts              # [БАГ] дублирует interfaces.ts с расхождениями — не использовать
    ├── components/
    │   ├── Layout.tsx            # [CRITICAL] файл не создан, импортируется в App.tsx
    │   └── ProtectedRoute.tsx    # [CRITICAL] файл не создан, импортируется в App.tsx
    ├── hooks/
    │   └── usePdfAnalysis.ts     # polling каждые 2000ms, upload логика, notification system
    └── pages/
        ├── Dashboard.tsx         # MetricCard компоненты, навигация к /reports
        ├── DetailedReport.tsx    # полный отчёт: ratios, score, NLP; ожидаемые поля — читать перед правками
        ├── AnalysisHistory.tsx   # [HIGH] использует mockHistory, нет реальных API-вызовов
        └── Auth.tsx              # [HIGH] handleSubmit сохраняет fake API key без валидации

migrations/
├── env.py                        # Alembic env: async engine, target_metadata
├── script.py.mako
└── versions/
    ├── 0001_create_analyses.py   # создание таблицы analyses
    └── 0002_add_indexes.py       # индексы по task_id, status, created_at

.github/
└── workflows/
    └── ci.yml                    # pipeline: lint (ruff/flake8) → test (pytest) → security → build

docker-compose.yml                # сервисы: backend, frontend, db, db_test, ollama
docker-compose.ci.yml             # CI-вариант без ollama, с db_test
Dockerfile                        # backend: Python 3.11, Tesseract, Poppler, pip install
entrypoint.sh                     # alembic upgrade head → uvicorn src.app:app
alembic.ini                       # путь к migrations/, sqlalchemy.url из env
.env                              # реальные секреты (не в git)
.env.example                      # шаблон переменных
.flake8                           # конфиг flake8
.pre-commit-config.yaml           # ruff + flake8 + mypy хуки
```

---

## 4. Основные сущности и модели данных

### ORM-модель: `Analysis` (таблица `analyses`) — `src/db/models.py`

```
Поле            Тип                  Индекс    Описание
─────────────────────────────────────────────────────────────────
id              Integer PK           PK        автоинкремент
task_id         String(36)           UNIQUE    UUID v4, генерируется при /upload
status          String(20)           INDEX     "processing" | "completed" | "failed"
filename        String(255)          —         оригинальное имя файла
result          JSON / Text          —         полный payload результата (см. ниже)
error_message   Text, nullable       —         сообщение об ошибке при status=failed
created_at      DateTime             INDEX     UTC, default=now()
updated_at      DateTime             —         UTC, обновляется при каждом update
```

Индексы (миграция `0002_add_indexes.py`): `ix_analyses_task_id`, `ix_analyses_status`, `ix_analyses_created_at`.

### Pydantic-схемы — `src/models/schemas.py`

```python
UploadResponse:
    task_id: str          # UUID задачи
    status: str           # всегда "processing" при создании
    message: str

AnalysisResult:
    task_id: str
    status: str           # "processing" | "completed" | "failed"
    filename: str
    data: Optional[AnalysisData]
    error: Optional[str]

AnalysisData:
    scanned: bool         # True если PDF обработан через OCR
    text: str             # извлечённый текст
    tables: list[dict]    # сырые таблицы из camelot/pdfplumber
    metrics: dict         # сырые финансовые метрики из pdf_extractor
    ratios: RatiosSchema  # коэффициенты (EN-ключи после маппинга)
    score: ScoreSchema    # интегральный скоринг
    nlp: NLPSchema        # результат NLP-анализа

RatiosSchema:
    current_ratio: Optional[float]
    quick_ratio: Optional[float]
    debt_to_equity: Optional[float]
    roa: Optional[float]
    roe: Optional[float]

ScoreSchema:
    score: float                    # 0–100
    risk_level: str                 # "low" | "medium" | "high" | "critical"
    factors: list[ScoreFactor]      # после _build_score_payload()
    normalized_scores: dict[str, float]

ScoreFactor:
    name: str
    description: str
    impact: str                     # "positive" | "negative" | "neutral"

NLPSchema:
    risks: list[str]
    key_factors: list[str]
    recommendations: list[str]

# [UNUSED] AnalyzeResponse определён в schemas.py, но не используется в /upload flow
```

### Frontend-интерфейсы — `frontend/src/api/interfaces.ts`

```typescript
interface AnalysisResult {
  task_id: string
  status: 'processing' | 'completed' | 'failed'
  filename: string
  data?: AnalysisData
  error?: string
}

interface AnalysisData {
  scanned: boolean
  text: string
  tables: Record<string, unknown>[]
  metrics: Record<string, number | null>
  ratios: Ratios
  score: Score
  nlp: NLPResult
}

interface Ratios {
  current_ratio: number | null
  quick_ratio: number | null
  debt_to_equity: number | null
  roa: number | null
  roe: number | null
}

interface Score {
  score: number
  risk_level: string
  factors: ScoreFactor[]
  normalized_scores: Record<string, number>
}

interface ScoreFactor {
  name: string
  description: string
  impact: 'positive' | 'negative' | 'neutral'
}

interface NLPResult {
  risks: string[]
  key_factors: string[]
  recommendations: string[]
}
```

### ⚠️ Критичные несоответствия backend ↔ frontend

**Несоответствие 1: ключи коэффициентов**
- `src/analysis/ratios.py` возвращает русскоязычные ключи:
  `{"Коэффициент текущей ликвидности": 1.5, "Рентабельность активов": 0.08, ...}`
- Frontend ожидает camelCase/snake_case английские ключи:
  `{current_ratio: 1.5, roa: 0.08, ...}`
- Маппинг происходит в `src/tasks.py` через `RATIO_KEY_MAP`:
  ```python
  RATIO_KEY_MAP = {
      "Коэффициент текущей ликвидности": "current_ratio",
      "Коэффициент быстрой ликвидности": "quick_ratio",
      "Долг к собственному капиталу":    "debt_to_equity",
      "Рентабельность активов":          "roa",
      "Рентабельность собственного капитала": "roe",
  }
  ```
- Функция `_translate_ratios()` в `tasks.py` применяет этот маппинг перед сохранением в БД.

**Несоответствие 2: структура scoring**
- `src/analysis/scoring.py` возвращает `details: dict` (плоский словарь с числовыми значениями)
- Frontend ожидает `factors: [{name, description, impact}]` (список объектов)
- Преобразование выполняет `_build_score_payload()` в `src/tasks.py`

**Несоответствие 3: дублирование типов**
- `frontend/src/api/types.ts` дублирует `interfaces.ts` с расхождениями в типах
- Использовать только `interfaces.ts` — `types.ts` не трогать до рефакторинга

---

## 5. Data Flow: главный сценарий

```
User
 │
 ▼
POST /upload (multipart/form-data, file ≤ 50MB)
 │
 ├─ validate: magic header b"%PDF-" на первых 8 байт
 ├─ validate: content-type == "application/pdf"
 ├─ validate: size ≤ 50MB (читается чанками по 8KB)
 ├─ save → SpooledTemporaryFile (RAM до 1MB, потом диск)
 ├─ generate task_id (UUID4)
 ├─ crud.create_analysis(task_id, status="processing")  ← БД
 ├─ BackgroundTasks.add_task(process_pdf, task_id, tmp_path)
 └─ return {task_id, status: "processing"}  ← немедленно

                    [BackgroundTask: process_pdf()]
                     │
                     ├─ is_scanned(pdf)?
                     │   ├─ YES → pdf2image + pytesseract (OCR)
                     │   └─ NO  → PyPDF2 (текст) + pdfplumber (таблицы)
                     │
                     ├─ extract_tables():
                     │   ├─ camelot lattice mode
                     │   └─ fallback: camelot stream mode
                     │
                     ├─ parse_financial_statements()
                     │   └─ → dict[str, float | None]  (сырые метрики)
                     │
                     ├─ calculate_ratios(metrics)
                     │   └─ → dict[ru_key, float | None]  (5 коэффициентов, RU-ключи)
                     │
                     ├─ calculate_integral_score(ratios)
                     │   └─ → {score: float, risk_level: str, details: dict}
                     │
                     ├─ _translate_ratios(ratios, RATIO_KEY_MAP)
                     │   └─ → dict[en_key, float | None]  (EN-ключи для frontend)
                     │
                     ├─ _build_score_payload(score_result)
                     │   └─ → {score, risk_level, factors: [{name,description,impact}], normalized_scores}
                     │
                     ├─ [optional] analyze_narrative() via ai_service.analyze()
                     │   ├─ asyncio.wait_for(timeout=60s)
                     │   ├─ SUCCESS → {risks: [], key_factors: [], recommendations: []}
                     │   └─ FAIL/TIMEOUT → {risks: [], key_factors: [], recommendations: []}  (graceful)
                     │
                     ├─ crud.update_analysis(task_id, status="completed", result={...})  ← БД
                     └─ finally: os.unlink(tmp_path)  (cleanup tempfile)

Frontend polling (usePdfAnalysis.ts, каждые 2000ms)
 │
 ▼
GET /result/{task_id}
 │
 ├─ status == "processing" → продолжать polling
 ├─ status == "failed"     → показать ошибку, остановить polling
 └─ status == "completed"  → остановить polling
     │
     ▼
     data: {scanned, text, tables, metrics, ratios, score, nlp}
      │
      ├─ Dashboard.tsx → MetricCard (score, risk_level, ratios)
      └─ navigate /reports → DetailedReport.tsx
          ├─ ratios таблица (current_ratio, quick_ratio, debt_to_equity, roa, roe)
          ├─ score gauge + factors список
          └─ nlp секция (risks, key_factors, recommendations)
```

---

## 6. Внешние интеграции

| Сервис     | Файл                          | Протокол    | Auth                          | Timeout | Retry              | Fallback          |
|------------|-------------------------------|-------------|-------------------------------|---------|--------------------|--------------------|
| GigaChat   | `src/core/gigachat_agent.py`  | HTTPS+OAuth2| Bearer token (кеш 55 мин)     | 120s    | 3x exponential     | → Qwen             |
| Qwen       | `src/core/agent.py`           | HTTPS       | Bearer token                  | 120s    | 3x exponential     | → Ollama           |
| Ollama     | `src/core/ai_service.py`      | HTTP        | —                             | 120s    | нет                | NLP отключается    |
| PostgreSQL | `src/db/database.py`          | asyncpg     | env: POSTGRES_USER/PASSWORD   | —       | —                  | —                  |

**Логика выбора провайдера в `AIService._configure()` (`src/core/ai_service.py`):**

```
if settings.use_gigachat:
    provider = GigaChatAgent()          # src/core/gigachat_agent.py
elif settings.use_qwen:
    provider = QwenAgent()              # src/core/agent.py
elif settings.use_local_llm:
    provider = OllamaClient()           # inline в ai_service.py
else:
    provider = None                     # NLP отключён, analyze() возвращает пустые списки
```

Никто за пределами `src/core/ai_service.py` не должен инстанциировать `GigaChatAgent` или `QwenAgent` напрямую.

**GigaChat OAuth2 flow (`src/core/gigachat_agent.py`):**
- Токен запрашивается при первом вызове, кешируется на 55 минут (срок жизни токена — 60 мин)
- SSL-сертификат GigaChat требует кастомного CA bundle (настраивается через env)
- При 401 — немедленный refresh токена без учёта retry-счётчика

---

## 7. Основные паттерны

### a) Lazy initialization (БД) — `src/db/database.py`

```python
_engine: Optional[AsyncEngine] = None

def get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        _engine = create_async_engine(settings.database_url, ...)
    return _engine
```

Engine создаётся только при первом вызове `get_engine()`. Без этого импорт модуля падал бы при отсутствии `DATABASE_URL` — критично для тестовой среды, где URL подставляется позже.

### b) BackgroundTasks (обработка PDF) — `src/tasks.py`

```python
# src/routers/upload.py
@router.post("/upload")
async def upload_pdf(background_tasks: BackgroundTasks, file: UploadFile):
    task_id = str(uuid4())
    await crud.create_analysis(task_id, status="processing")
    background_tasks.add_task(process_pdf, task_id, tmp_path)
    return {"task_id": task_id, "status": "processing"}
```

`/upload` возвращает ответ немедленно. `process_pdf()` выполняется асинхронно в том же процессе. PDF-анализ занимает 10–60 секунд — HTTP-таймаут неприемлем. Frontend поллит `/result/{id}` каждые 2000ms (захардкожено в `usePdfAnalysis.ts`).

### c) Graceful degradation (AI) — `src/core/ai_service.py`

```python
async def analyze(self, text: str) -> NLPResult:
    if self.provider is None:
        return NLPResult(risks=[], key_factors=[], recommendations=[])
    try:
        return await asyncio.wait_for(self.provider.analyze(text), timeout=60)
    except Exception:
        return NLPResult(risks=[], key_factors=[], recommendations=[])
```

Числовой анализ (ratios, score) не зависит от AI и всегда выполняется. NLP — опциональный слой.

### d) Chunked file reading + magic header validation — `src/routers/upload.py`

```python
header = await asyncio.to_thread(file.file.read, 8)
if not header.startswith(b"%PDF-"):
    raise HTTPException(400, "Not a PDF file")
total = len(header)
while chunk := await asyncio.to_thread(file.file.read, 8192):
    total += len(chunk)
    if total > 50 * 1024 * 1024:   # 50MB
        raise HTTPException(413, "File too large")
```

Лимит 50MB проверяется в процессе чтения, не после полной загрузки в память.

### e) SpooledTemporaryFile — `src/routers/upload.py`

```python
with SpooledTemporaryFile(max_size=1 * 1024 * 1024) as tmp:
    # файл в RAM до 1MB, потом автоматически спиллится на диск
    ...
# finally: tmp удаляется автоматически при выходе из with
```

Имя tempfile включает `task_id` для уникальности при нескольких инстансах.

### f) Upsert pattern — `src/db/crud.py`

```python
async def update_analysis(task_id: str, **kwargs):
    analysis = await get_analysis(task_id)
    if analysis is None:
        await create_analysis(task_id, **kwargs)   # race condition protection
    else:
        # update fields
        await session.commit()
```

Защита от race condition между `/upload` endpoint и `process_pdf` background task: если запись ещё не создана — создаём.

---

## 8. Критичные файлы: что читать агенту

**ВСЕГДА читать перед любыми изменениями:**

```
src/app.py                          — middleware стек, порядок подключения routers, CORS origins, lifespan
src/models/settings.py              — все env-переменные, их типы и валидация; изменение здесь влияет на всё
src/db/database.py                  — как создаётся engine и session; lazy init паттерн
frontend/src/api/interfaces.ts      — ОСНОВНОЙ контракт данных frontend; любое изменение backend-ответа
                                      должно отражаться здесь
src/tasks.py                        — RATIO_KEY_MAP (маппинг RU→EN ключей) и _build_score_payload()
                                      (преобразование details→factors); без понимания этого файла
                                      любые правки ratios.py или scoring.py сломают frontend
```

**Читать перед изменением конкретного слоя:**

```
[Analysis pipeline]
src/analysis/pdf_extractor.py       — _METRIC_KEYWORDS dict определяет, какие строки считаются
                                      финансовыми метриками; изменение влияет на все downstream расчёты
src/analysis/ratios.py              — формулы 5 коэффициентов; ключи ОБЯЗАТЕЛЬНО русские (маппинг в tasks.py)
src/analysis/scoring.py             — weights dict и пороговые значения; нормализация 0–100;
                                      структура details dict должна соответствовать _build_score_payload()

[AI/NLP]
src/core/ai_service.py              — логика _configure(): порядок выбора провайдера, graceful degrade
src/core/gigachat_agent.py          — OAuth2 flow, SSL bundle, формат запроса/ответа GigaChat API;
                                      изменение формата промпта — только здесь

[Frontend]
frontend/src/hooks/usePdfAnalysis.ts     — polling интервал 2000ms, логика остановки polling,
                                           система уведомлений; изменение статусов backend затрагивает этот файл
frontend/src/pages/DetailedReport.tsx    — какие поля ожидаются из data.ratios, data.score.factors,
                                           data.nlp; читать перед изменением структуры ответа
frontend/src/pages/Dashboard.tsx         — MetricCard компонент, навигация к /reports,
                                           какие поля score используются для отображения
```

---

## 9. Что НЕ нужно в контексте (не читать без причины)

```
docs/old_reports/*.md               — устаревшие отчёты о багах и фиксах, не отражают текущий код
docs/old_reports/GIT_*.txt          — CI артефакты коммитов, не содержат логики
docs/old_reports/*_SUCCESS.txt      — артефакты деплоя, не содержат логики
tests/test_benchmarks.py            — перфоманс-тесты, не запускаются в CI pipeline
tests/test_e2e.py                   — требует полного docker-compose стека, не для unit-правок
tests/test_frontend_e2e.py          — требует запущенного frontend, не для unit-правок
Backend.pyproj                      — Visual Studio project file, не используется в CI/Docker
frontend/src/api/types.ts           — дублирует interfaces.ts с расхождениями; использовать interfaces.ts
docs/tasks/WEEK*.md                 — планы разработки, устарели после MVP
BUILDING.md, BUILD_GUIDE.md,        — частично устаревшие инструкции; актуальна только
BUILD_README.md                       команда docker-compose up --build
```

---

## 10. Масштабируемость и ограничения

**Текущие ограничения (работает на одном инстансе):**

- `BackgroundTasks` в FastAPI — in-process, не переживает рестарт сервера. Если процесс упадёт во время обработки PDF — задача потеряется, `status` останется `"processing"` навсегда. Нет механизма восстановления.
- Polling каждые 2000ms × N активных пользователей = N запросов/2с к БД. При 100 пользователях — 50 req/s только на `/result/{id}`.
- `SlowAPI` rate limiter использует in-memory storage — при нескольких инстансах лимиты не синхронизируются.
- Tempfiles создаются в системной temp-директории контейнера. `task_id` в имени файла защищает от коллизий, но при горизонтальном масштабировании разные инстансы не видят файлы друг друга.
- `camelot-py` требует Tesseract и Poppler — тяжёлые системные зависимости (~500MB в Docker-образе), нельзя убрать без замены PDF-обработки.

**Что нужно для масштабирования:**

- BackgroundTasks → Celery + Redis (или ARQ) с персистентной очередью задач
- Polling → WebSocket или Server-Sent Events (SSE)
- SlowAPI memory storage → Redis storage
- Tempfiles → объектное хранилище (S3 / MinIO) с presigned URLs

**Жёсткие лимиты (нельзя менять без тестирования всего pipeline):**

```
MAX_PDF_PAGES    = 100        # защита от DoS; проверяется в pdf_extractor.py
MAX_FILE_SIZE    = 50MB       # проверяется в upload.py при чтении чанками
AI_TIMEOUT       = 120s       # задан в agent.py, gigachat_agent.py, ai_service.py — менять везде
NLP_TIMEOUT      = 60s        # asyncio.wait_for в ai_service.analyze()
POLLING_INTERVAL = 2000ms     # захардкожен в frontend/src/hooks/usePdfAnalysis.ts
TOKEN_CACHE_TTL  = 55min      # GigaChat Bearer token; меньше срока жизни токена (60 мин)
SPOOLED_MAX_SIZE = 1MB        # SpooledTemporaryFile RAM-порог в upload.py
CHUNK_SIZE       = 8192       # размер чанка при чтении файла в upload.py
```

---

## 11. Известные проблемы и технический долг

```
[CRITICAL] frontend/src/components/Layout.tsx
           — файл не создан; App.tsx импортирует его → приложение не компилируется

[CRITICAL] frontend/src/components/ProtectedRoute.tsx
           — файл не создан; App.tsx импортирует его → приложение не компилируется

[CRITICAL] frontend/src/api/types.ts vs interfaces.ts
           — дублирование типов с расхождениями в полях; часть компонентов может
             импортировать из types.ts и получать неверные типы

[HIGH]     frontend/src/pages/AnalysisHistory.tsx
           — использует локальный mockHistory массив; нет вызовов к API;
             история анализов не отображается реально

[HIGH]     frontend/src/pages/Auth.tsx (handleSubmit)
           — сохраняет введённый API key в localStorage без валидации на backend;
             любая строка принимается как валидный ключ

[MEDIUM]   src/analysis/nlp_analysis.py
           — модуль реализован, но вызов закомментирован в src/tasks.py;
             NLP-анализ не выполняется даже при доступном AI-провайдере

[MEDIUM]   src/models/schemas.py (AnalyzeResponse)
           — схема определена, но не используется в /upload flow;
             /upload возвращает UploadResponse, не AnalyzeResponse

[LOW]      frontend/src/pages/DetailedReport.tsx (trend data)
           — значения "+2.4%" и "-1.1%" захардкожены в JSX; не берутся из API

[LOW]      корень репозитория: GIT_COMMIT_SUCCESS.txt, GIT_PUSH_SUCCESS.txt
           — мусорные файлы от CI артефактов; не несут логики; можно удалить
```
