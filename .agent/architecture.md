# NeoFin AI — Architecture

## 1. Быстрый старт для агента

NeoFin AI — ИИ-ассистент финансового директора: принимает PDF-отчёты компаний, извлекает финансовые данные, вычисляет 13 коэффициентов, строит интегральный скоринг 0–100, генерирует NLP-рекомендации через GigaChat/Ollama. Предоставляет API истории анализов с пагинацией и маскировкой данных для демо-режима.
Точка входа backend: `src/app.py` (FastAPI app, middleware, routers, lifespan).
Точка входа frontend: `frontend/src/App.tsx` (роутинг, провайдеры, lazy-загрузка страниц).
Локальный запуск: `docker-compose up --build` — поднимает backend, frontend/nginx, db, db_test, ollama.

---

## 2. Структура слоёв

```
┌─────────────────────────────────────────────────────────┐
│         Frontend: React 19 / Mantine 8 / Vite 6         │
│  frontend/src/pages/, frontend/src/components/          │
│  Отвечает: UI, WebSocket-обновления, отображение        │
│  НЕ должно: содержать бизнес-логику, прямые SQL-запросы │
└────────────────────┬────────────────────────────────────┘
                     │ HTTP REST + WebSocket (/ws/{id})
                     │ POST /upload → WebSocket update → Result
┌────────────────────▼────────────────────────────────────┐
│              API Layer: FastAPI routers                  │
│  src/routers/upload.py, src/routers/websocket.py        │
│  Отвечает: валидация входа, WS-соединения, auth-проверка│
│  НЕ должно: содержать бизнес-логику, импортировать БД   │
└────────────────────┬────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────┐
│            Controllers: бизнес-логика запроса           │
│  src/tasks.py + src/core/ws_manager.py                  │
│  Отвечает: оркестрация pipeline, WS-broadcast           │
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
│       → src/core/agent.py (DeepSeek)                    │
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
- `src/core/gigachat_agent.py`, `src/core/agent.py` → вызываются только из `src/core/ai_service.py` (через `BaseAIAgent`)
- `session.add()`, `session.commit()`, `session.execute()` → только в `src/db/crud.py`

---

## 3. Файловая структура проекта

```
src/
├── app.py                        # точка входа FastAPI: middleware, lifespan, подключение routers
├── tasks.py                      # process_pdf(): оркестратор pipeline; использует чистые функции из analysis/
├── analysis/
│   ├── __init__.py
│   ├── pdf_extractor.py          # извлечение текста (PyPDF2), таблиц (camelot), OCR (tesseract); regex fallback
│   ├── ratios.py                 # 13 финансовых коэффициентов; RATIO_KEY_MAP и translate_ratios()
│   ├── scoring.py                # интегральный скоринг 0–100; 4 группы весов; build_score_payload()
│   ├── nlp_analysis.py           # NLP-анализ через ai_service; подключён в tasks.py
│   └── recommendations.py        # 3–5 рекомендаций с ссылками на метрики; timeout 65s; graceful degrade
├── core/
│   ├── __init__.py
│   ├── ai_service.py             # AIService: _configure(), выбор провайдера, graceful degrade
│   ├── base_agent.py             # BaseAIAgent: базовый класс с Singleton aiohttp.ClientSession
│   ├── gigachat_agent.py         # GigaChat: наследует BaseAIAgent, OAuth2 flow, SSL, ретраи
│   ├── agent.py                  # DeepSeek: наследует BaseAIAgent, Bearer token, ретраи
│   └── ws_manager.py             # ConnectionManager: управление WebSocket-подписками
├── db/
│   ├── __init__.py
│   ├── database.py               # get_engine() lazy init, AsyncSession factory, get_db() dependency
│   ├── models.py                 # ORM-model Analysis (таблица analyses)
│   └── crud.py                   # create_analysis(), get_analysis(), update_analysis()
├── models/
│   ├── __init__.py
│   ├── schemas.py                # Pydantic-схемы: UploadResponse, AnalysisResult, ScoreSchema
│   └── settings.py               # Settings(BaseSettings): все env-переменные с валидацией
├── routers/
│   ├── __init__.py
│   ├── upload.py                 # POST /upload: валидация PDF, magic header, size ≤50MB, BackgroundTask
│   ├── result.py                 # GET /result/{task_id}: чтение статуса из БД (fallback для WS)
│   ├── websocket.py              # /ws/{task_id}: WebSocket-эндпоинт для real-time обновлений
│   └── analyses.py               # GET /analyses (пагинация), GET /analyses/{task_id}
└── utils/
    ├── __init__.py
    ├── masking.py                # mask_analysis_data(data, demo_mode): чистая функция
    └── file_utils.py             # cleanup_temp_file(): безопасная очистка временных ресурсов

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
    │   ├── Layout.tsx            # AppShell с навигацией и logout
    │   └── ProtectedRoute.tsx    # redirect на /login при !isAuthenticated
    ├── hooks/
    │   └── usePdfAnalysis.ts     # polling каждые 2000ms, upload логика, notification system
    └── pages/
        ├── Dashboard.tsx         # MetricCard компоненты, навигация к /reports
        ├── DetailedReport.tsx    # полный отчёт: BarChart из реальных ratios, score, NLP
        ├── AnalysisHistory.tsx   # список анализов из GET /analyses; пагинация; клик → DetailedReport
        └── Auth.tsx              # [HIGH] handleSubmit сохраняет API key без валидации на backend

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

### 3.1 Операционная структура (вынесено из AGENTS.md)

```
src/
├── app.py              → точка входа FastAPI, middleware, lifespan
├── tasks.py            → оркестратор pipeline; декомпозирован на фазы
├── analysis/           → чистые функции: pdf_extractor, ratios, scoring, nlp_analysis, recommendations
├── core/               → ai_service, base_agent, gigachat_agent, agent, ws_manager
├── db/                 → database (lazy engine), crud (единственный файл с SQL), models
├── models/             → schemas (Pydantic), settings (env-переменные)
└── routers/            → upload, result, analyses, websocket, multi_analysis

frontend/src/
├── api/                → client.ts (axios), interfaces.ts (основной контракт)
├── hooks/              → usePdfAnalysis.ts, useAnalysisSocket.ts, useMultiAnalysisPolling.ts
├── pages/              → Dashboard, DetailedReport, AnalysisHistory, Auth
└── components/         → Layout.tsx, ProtectedRoute.tsx, ConfidenceBadge.tsx

migrations/versions/    → 0001_create_analyses, 0002_add_indexes
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
    ratios: RatiosSchema  # 13 коэффициентов (EN-ключи после маппинга)
    score: ScoreSchema    # интегральный скоринг
    nlp: NLPSchema        # результат NLP-анализа

RatiosSchema:             # 13 коэффициентов по 4 группам
    current_ratio, quick_ratio, absolute_liquidity_ratio  # ликвидность
    roa, roe, ros, ebitda_margin                          # рентабельность
    equity_ratio, financial_leverage, interest_coverage   # устойчивость
    asset_turnover, inventory_turnover, receivables_turnover  # активность

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

# Схемы истории анализов (Этап 3):
AnalysisSummaryResponse:
    task_id: str
    status: str
    created_at: datetime
    score: float | None
    risk_level: str | None
    filename: str | None

AnalysisListResponse:
    items: list[AnalysisSummaryResponse]
    total: int
    page: int
    page_size: int

AnalysisDetailResponse:
    task_id: str
    status: str
    created_at: datetime
    data: dict | None
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
  metrics: FinancialMetrics
  ratios: FinancialRatios   // 13 коэффициентов
  score: Score
  nlp: NLPResult
}

interface FinancialRatios {
  // Ликвидность
  current_ratio: number | null
  quick_ratio: number | null
  absolute_liquidity_ratio: number | null
  // Рентабельность
  roa: number | null
  roe: number | null
  ros: number | null
  ebitda_margin: number | null
  // Устойчивость
  equity_ratio: number | null
  financial_leverage: number | null
  interest_coverage: number | null
  // Активность
  asset_turnover: number | null
  inventory_turnover: number | null
  receivables_turnover: number | null
}

interface Score {
  score: number
  risk_level: string
  confidence_score: number
  factors: ScoreFactor[]
  normalized_scores: Record<string, number | null>
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

// История анализов (Этап 3):
interface AnalysisSummary {
  task_id: string
  status: string
  created_at: string        // ISO 8601
  score: number | null
  risk_level: string | null
  filename: string | null
}

interface AnalysisListResponse {
  items: AnalysisSummary[]
  total: number
  page: number
  page_size: number
}
```

### ⚠️ Критичные несоответствия backend ↔ frontend

**Несоответствие 1: ключи коэффициентов (Исправлено)**
- Маппинг и трансляция ключей теперь инкапсулированы в слое `analysis` ([ratios.py](file:///e:/neo-fin-ai/src/analysis/ratios.py)).
- Оркестратор ([tasks.py](file:///e:/neo-fin-ai/src/tasks.py)) вызывает `translate_ratios()` перед сохранением.

**Несоответствие 2: структура scoring (Исправлено)**
- Формирование `payload` факторов теперь инкапсулировано в [scoring.py](file:///e:/neo-fin-ai/src/analysis/scoring.py) через `build_score_payload()`.

**Несоответствие 3: дублирование типов (Исправлено)**
- Файл `frontend/src/api/types.ts` удалён. Проект использует единый контракт в [interfaces.ts](file:///e:/neo-fin-ai/frontend/src/api/interfaces.ts).

**Несоответствие 4: утечка неизвестных ключей в translate_ratios (Исправлено)**
- `translate_ratios()` теперь дропает ключи, отсутствующие в `RATIO_KEY_MAP`, вместо проброса на фронтенд.

---

## 5. Data Flow: главный сценарий

```
User
 │
 ▼
POST /upload (multipart/form-data, file ≤ 50MB)
 │
 ├─ validate: magic header b"%PDF-" на первых 8 байт
 ├─ generate task_id (UUID4)
 ├─ crud.create_analysis(task_id, status="processing")
 ├─ BackgroundTasks.add_task(process_pdf, task_id, tmp_path)
 └─ return {task_id, status: "processing"}

                    [BackgroundTask: process_pdf()]
                     │
                     ├─ [Phase 1: Extraction]
                     │   ├─ is_scanned(pdf)? → extract text/tables
                     │   ├─ parse metrics → apply_confidence_filter
                     │   └─ ws_manager.broadcast(task_id, status="extracting")
                     │
                     ├─ [Phase 2: Scoring]
                     │   ├─ calculate_ratios → translate_ratios
                     │   ├─ calculate_integral_score → build_score_payload
                     │   └─ ws_manager.broadcast(task_id, status="scoring")
                     │
                     ├─ [Phase 3: AI Analysis]
                     │   ├─ analyze_narrative (GigaChat/DeepSeek)
                     │   ├─ generate_recommendations
                     │   └─ ws_manager.broadcast(task_id, status="analyzing")
                     │
                     ├─ [Phase 4: Finalize]
                     │   ├─ crud.update_analysis(task_id, status="completed", result={...})
                     │   └─ ws_manager.broadcast(task_id, status="completed", result={...})
                     │
                     └─ finally: cleanup_temp_file(file_path)

Frontend WebSocket (useAnalysisSocket.ts)
 │
 ▼
WS /ws/{task_id}
 │
 ├─ onMessage: обновление UI (статус-бар, прогресс)
 └─ onComplete: редирект на /reports или показ DetailedReport

История анализов (AnalysisHistory.tsx, Этап 3)
 │
 ▼
GET /analyses?page=1&page_size=20
 │
 ├─ get_analyses_list(page, page_size)  ← crud.py
 ├─ [если DEMO_MODE=1] mask_analysis_data(item.result, True) для каждого элемента
 └─ AnalysisListResponse {items, total, page, page_size}
     │
     ▼
     AnalysisHistory.tsx: таблица с пагинацией Mantine
      │
      └─ клик на строку → GET /analyses/{task_id}
          │
          ├─ get_analysis(task_id)  ← crud.py
          ├─ [если DEMO_MODE=1] mask_analysis_data(result, True)
          └─ AnalysisDetailResponse {task_id, status, created_at, data}
              │
              └─ DetailedReport.tsx (тот же компонент)
```

---

## 6. Внешние интеграции

| Сервис     | Файл                          | Протокол    | Auth                          | Timeout | Retry              | Fallback          |
|------------|-------------------------------|-------------|-------------------------------|---------|--------------------|--------------------|
| GigaChat   | `src/core/gigachat_agent.py`  | HTTPS+OAuth2| Bearer token (кеш 55 мин)     | 120s    | 3x exponential     | → DeepSeek         |
| DeepSeek   | `src/core/agent.py`           | HTTPS       | Bearer token                  | 120s    | 3x exponential     | → Ollama           |
| Ollama     | `src/core/ai_service.py`      | HTTP        | —                             | 120s    | нет                | NLP отключается    |
| PostgreSQL | `src/db/database.py`          | asyncpg     | env: POSTGRES_USER/PASSWORD   | —       | —                  | —                  |

**Логика выбора провайдера в `AIService._configure()` (`src/core/ai_service.py`):**

```
if settings.use_gigachat:
    provider = GigaChatAgent()          # src/core/gigachat_agent.py
elif settings.use_qwen:
    provider = DeepSeekAgent()              # src/core/agent.py
elif settings.use_local_llm:
    provider = OllamaClient()           # inline в ai_service.py
else:
    provider = None                     # NLP отключён, analyze() возвращает пустые списки
```

Никто за пределами `src/core/ai_service.py` не должен инстанциировать `GigaChatAgent` или `DeepSeekAgent` напрямую.

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

### g) WebSocket Connection Management — `src/core/ws_manager.py`

```python
# src/core/ws_manager.py
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, Set[WebSocket]] = {}
    async def connect(self, websocket: WebSocket, task_id: str): ...
    async def broadcast(self, task_id: str, message: dict): ...
```

Используется для группировки соединений по `task_id`. Позволяет нескольким вкладкам/пользователям следить за одной задачей без лишней нагрузки на БД.

### h) Base AI Agent (Singleton Session) — `src/core/base_agent.py`

```python
# src/core/base_agent.py
class BaseAIAgent:
    _session: Optional[aiohttp.ClientSession] = None
    @classmethod
    async def get_session(cls) -> aiohttp.ClientSession:
        if cls._session is None or cls._session.closed:
            cls._session = aiohttp.ClientSession(...)
        return cls._session
```

Предотвращает исчерпание портов (port exhaustion) при большом количестве параллельных запросов к AI-провайдерам.
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
src/tasks.py                        — Оркестратор pipeline; точка входа для фоновых задач;
                                      читать для понимания порядка вызовов (ratios -> scoring -> ai)
```

**Читать перед изменением конкретного слоя:**

```
[Analysis pipeline]
src/analysis/pdf_extractor.py       — _METRIC_KEYWORDS dict определяет, какие строки считаются
                                      финансовыми метриками; изменение влияет на все downstream расчёты
src/analysis/ratios.py              — формулы 13 коэффициентов; RATIO_KEY_MAP и translate_ratios()
src/analysis/scoring.py             — weights dict и пороговые значения; нормализация 0–100;
                                      build_score_payload() для формирования данных фронтенда

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
- **Logging**: внедрить агрегацию логов (ELK/Loki)

**Жёсткие лимиты (нельзя менять без тестирования всего pipeline):**

```
MAX_PDF_PAGES    = 100        # защита от DoS; проверяется в pdf_extractor.py
MAX_FILE_SIZE    = 50MB       # проверяется в upload.py при чтении чанками
AI_TIMEOUT       = 120s       # задан в agent.py, gigachat_agent.py, ai_service.py — менять везде
NLP_TIMEOUT      = 60s        # asyncio.wait_for в tasks.py
REC_TIMEOUT      = 65s        # asyncio.wait_for в tasks.py
MAX_OCR_PAGES    = 50         # константа в pdf_extractor.py; OCR останавливается после 50 страниц
POLLING_INTERVAL = 2000ms     # захардкожен в frontend/src/hooks/usePdfAnalysis.ts
TOKEN_CACHE_TTL  = 55min      # GigaChat Bearer token; меньше срока жизни токена (60 мин)
SPOOLED_MAX_SIZE = 1MB        # SpooledTemporaryFile RAM-порог в upload.py
CHUNK_SIZE       = 8192       # размер чанка при чтении файла в upload.py
DOCKER_BUILD_CACHE = local    # Dockerfile.backend: кеш между сборками
NGINX_RATE_LIMIT   = 10r/s    # nginx.conf: limit_req_zone rate
```

### Docker production notes (вынесено из AGENTS.md)

```
Dockerfile.backend           → multi-stage build (build → runtime)
frontend/Dockerfile.frontend → multi-stage build (node → nginx)
docker-compose.prod.yml      → production-оркестрация (nginx, backend, db, ollama)
nginx.conf                   → reverse proxy, rate limiting, gzip, security headers
scripts/deploy-prod.sh       → деплой-пайплайн (validate → build → migrate → start)
```

### Триггеры действий (вынесено из AGENTS.md)

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
| **Production деплой** | Используй `scripts/deploy-prod.sh` или `docker compose -f docker-compose.prod.yml` |
| **Docker build ошибка** | Проверь `.dockerignore` и `frontend/.dockerignore` — лишние файлы могут сломать сборку |
| **Nginx 502 Bad Gateway** | Backend не запустился; проверь `docker-compose logs backend` и health check |
| **Миграции не применяются** | Запусти вручную: `docker compose -f docker-compose.prod.yml run --rm backend-migrate` |

---

## 11. Известные проблемы и технический долг

```
[HIGH]     frontend/src/pages/Auth.tsx (handleSubmit)
           — сохраняет введённый API key в localStorage без валидации на backend;
             любая строка принимается как валидный ключ
```
