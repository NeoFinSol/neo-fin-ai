# NeoFin AI — Project Structure

## Root Layout

```
neofin-ai/
├── src/                    # Backend Python source
├── frontend/               # React TypeScript frontend
├── tests/                  # Backend test suite
├── migrations/             # Alembic migration files
├── scripts/                # Deploy and utility scripts
├── docs/                   # Architecture, API, config docs
├── .agent/                 # Agent context files (architecture notes, session logs)
├── .kiro/                  # Kiro specs and steering
├── docker-compose.yml      # Dev environment
├── docker-compose.prod.yml # Production environment
├── Dockerfile.backend      # Multi-stage backend image
├── frontend/Dockerfile.frontend  # Multi-stage frontend image
├── nginx.conf              # Nginx reverse proxy config
├── entrypoint.sh           # Container entrypoint: alembic upgrade → uvicorn
├── requirements.txt        # Production Python deps
├── requirements-dev.txt    # Dev/test Python deps
├── pytest.ini              # pytest config
└── .env.example            # Environment variable template
```

## Backend: `src/`

Strict layered architecture — dependencies flow top-down only.

```
src/
├── app.py                  # FastAPI app: middleware, CORS, router registration, lifespan
├── tasks.py                # Pipeline orchestrator: process_pdf(), RATIO_KEY_MAP, _build_score_payload()
├── analysis/               # Pure domain functions — no FastAPI/SQLAlchemy imports
│   ├── pdf_extractor.py    # Text/table/OCR extraction; _METRIC_KEYWORDS dict
│   ├── ratios.py           # 13 financial ratios; returns Russian-language keys
│   ├── scoring.py          # Integral score 0–100; weights dict; confidence_score field
│   ├── nlp_analysis.py     # NLP risk/factor analysis via ai_service
│   ├── recommendations.py  # 3–5 recommendations via ai_service; timeout 65s
│   └── confidence.py       # Confidence score logic
├── core/                   # AI service layer and cross-cutting concerns
│   ├── ai_service.py       # SINGLE entry point for all LLM calls; provider selection at startup
│   ├── base_agent.py       # BaseAIAgent: Singleton ClientSession, exponential retry
│   ├── gigachat_agent.py   # GigaChat: OAuth2, token cache 55 min, SSL
│   ├── huggingface_agent.py# DeepSeek via HuggingFace Inference API
│   ├── agent.py            # Qwen/generic agent
│   ├── auth.py             # API key authentication
│   ├── security.py         # Security utilities
│   ├── ws_manager.py       # WebSocket ConnectionManager (Singleton)
│   ├── constants.py        # Shared constants
│   └── prompts.py          # LLM prompt templates
├── db/                     # Database layer — only place with SQL
│   ├── database.py         # Lazy engine init, AsyncSession factory, get_db()
│   ├── models.py           # ORM models: Analysis, MultiAnalysisSession
│   └── crud.py             # ALL session.add/commit/execute calls live here only
├── routers/                # HTTP endpoints — validation and delegation only, no business logic
│   ├── analyze.py          # POST /analyze
│   ├── pdf_tasks.py        # POST /upload, GET /result/{task_id}
│   ├── analyses.py         # GET /analyses (paginated history)
│   ├── multi_analysis.py   # POST /multi-analysis, GET /multi-analysis/{session_id}
│   ├── system.py           # GET /health, GET /system/info
│   └── websocket.py        # WebSocket /ws/{task_id}
├── controllers/
│   └── analyze.py          # Controller for analyze flow
├── models/
│   ├── schemas.py          # Pydantic response schemas
│   ├── requests.py         # Pydantic request schemas
│   └── settings.py         # Settings(BaseSettings): all env vars with validation
├── utils/
│   ├── masking.py          # mask_analysis_data(data, demo_mode) — pure function
│   ├── error_handler.py    # Global error handling
│   ├── file_utils.py       # Temp file utilities
│   ├── logging_config.py   # Logging setup
│   ├── retry_utils.py      # Retry decorators
│   └── circuit_breaker.py  # Circuit breaker pattern
└── exceptions/
    └── PdfExtractException.py
```

## Frontend: `frontend/src/`

```
frontend/src/
├── App.tsx                 # Router, lazy page loading, providers
├── main.tsx                # Entry point, MantineProvider
├── api/
│   ├── client.ts           # axios instance, baseURL=/api, X-API-Key header
│   └── interfaces.ts       # SINGLE source of truth for all TypeScript types — use this, not types.ts
├── context/
│   ├── AnalysisContext.tsx         # App-level analysis state (status, result, filename, error)
│   └── AnalysisHistoryContext.tsx  # Analysis history state
├── pages/
│   ├── Dashboard.tsx       # PDF upload, analysis trigger
│   ├── DetailedReport.tsx  # Full result: ratios, score, NLP; multi-period tabs
│   ├── AnalysisHistory.tsx # Paginated history list (real API, not mock)
│   └── Auth.tsx            # API key validation via pre-flight GET /analyses
├── components/
│   ├── ConfidenceBadge.tsx # Confidence indicator: 🟢≥0.8 / 🟡0.5–0.8 / 🔴<0.5 + tooltip
│   ├── TrendChart.tsx      # Multi-period LineChart; connectNulls=false; anomaly markers
│   └── Layout.tsx          # Navigation wrapper
└── hooks/
    └── usePdfAnalysis.ts   # Polling every 2000ms, upload logic, notifications
```

## Tests: `tests/`

- Unit tests: `test_analysis_*.py`, `test_core_*.py`, `test_db_*.py`
- Integration tests: `test_*_router.py`, `test_*_integration.py`
- Property-based tests (Hypothesis): `test_confidence_properties.py`, `test_qwen_regression_*.py`
- E2E tests (require full docker stack): `test_e2e.py`, `test_frontend_e2e.py` — run with `-m e2e`
- Benchmarks: `test_benchmarks.py` — not in CI pipeline

## Migrations: `migrations/versions/`

Applied automatically on container start via `entrypoint.sh`.

## Architecture Rules

- SQL only in `src/db/crud.py` — never in routers, tasks, or analysis
- LLM access only through `src/core/ai_service.py` — never import agents directly
- `src/analysis/*` must not import from `fastapi`, `sqlalchemy`, or AI agents
- Routers only validate input and delegate — no business logic
- Frontend types: use `interfaces.ts` exclusively — `types.ts` is a legacy duplicate with divergent types
- `RATIO_KEY_MAP` in `tasks.py` translates Russian ratio keys from `ratios.py` to English keys for the frontend — both sides must stay in sync
