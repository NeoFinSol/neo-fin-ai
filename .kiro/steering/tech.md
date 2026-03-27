# NeoFin AI — Tech Stack & Commands

## Backend

- **Python 3.11** with FastAPI 0.115, uvicorn (ASGI)
- **Pydantic v2** + pydantic-settings for validation and env management
- **SQLAlchemy 2.0 async** + asyncpg (PostgreSQL driver)
- **Alembic 1.13** for migrations
- **PDF processing**: PyPDF2, pdfplumber, camelot-py, pdf2image, pytesseract, opencv-python, pillow
- **HTTP clients**: aiohttp (async), requests (sync)
- **Rate limiting**: slowapi
- **AI providers**: GigaChat (OAuth2), HuggingFace/DeepSeek, Ollama

## Frontend

- **React 19** + TypeScript 5.8
- **Mantine UI v8** (components, forms, notifications, charts)
- **@mantine/charts** (Recharts-based) for TrendChart
- **Vite 6** (build tool, dev server with `/api` proxy to backend:8000)
- **React Router v7**
- **axios** for HTTP
- **Tailwind CSS v4**

## Database

- **PostgreSQL 16** with JSONB for analysis results
- Two databases: `neofin` (production) and `neofin_test` (tests)

## Testing

- **Backend**: pytest + pytest-asyncio (`asyncio_mode = auto`), Hypothesis (property-based testing)
- **Frontend**: vitest + @testing-library/react + fast-check (property-based testing)

## Infrastructure

- **Docker** + Docker Compose (multi-stage builds)
- **Nginx** — reverse proxy, serves React static files, rate limiting
- **GitHub Actions** CI: lint → test → security → build

## Common Commands

### Development (Docker)
```bash
docker-compose up --build          # start all services (backend, frontend, db, db_test)
docker-compose up --build --profile ollama  # include local Ollama LLM
docker-compose -f docker-compose.prod.yml up -d --build  # production
```

### Backend (local dev, Python 3.11+)
```bash
pip install -r requirements.txt
pip install -r requirements-dev.txt
uvicorn src.app:app --reload       # dev server on :8000

# Migrations
alembic upgrade head               # apply all migrations
alembic revision --autogenerate -m "description"  # create new migration
```

### Backend Tests
```bash
pytest tests/ -v                   # all tests
pytest tests/ -v -m "not e2e"     # skip e2e (requires full docker stack)
pytest tests/test_analysis_scoring.py -v  # single file
pytest tests/ --cov=src --cov-report=html  # with coverage
```

### Frontend (local dev, Node 20+)
```bash
cd frontend
npm install
npm run dev        # dev server on :3000
npm run build      # production build → dist/
npm run lint       # TypeScript type check
npm test           # vitest --run (single pass)
npm run coverage   # vitest with coverage
```

### Production Deploy
```bash
./scripts/deploy-prod.sh           # validate .env → build → migrate → start
```

## Key Environment Variables

| Variable | Required | Description |
|---|---|---|
| `DATABASE_URL` | yes | PostgreSQL async connection string |
| `API_KEY` | yes | API access key |
| `CONFIDENCE_THRESHOLD` | no (default: 0.5) | Metrics below this are excluded from ratio calculations |
| `GIGACHAT_CLIENT_ID` / `GIGACHAT_CLIENT_SECRET` | no | GigaChat LLM provider |
| `HF_TOKEN` | no | HuggingFace/DeepSeek provider |
| `LLM_URL` | no | Ollama local LLM endpoint |
| `DEMO_MODE` | no (default: 0) | Mask numeric data in API responses |

Full variable reference: `docs/CONFIGURATION.md`

## Linting & Code Quality

- **ruff** + **flake8** (config in `.flake8`)
- **mypy** for type checking
- **pre-commit** hooks: `.pre-commit-config.yaml`
