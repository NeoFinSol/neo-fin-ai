# Neo Fin AI - Solution Structure

## 📁 Project Organization

```
neo-fin-ai/
├── neo-fin-ai.sln              # Visual Studio Solution File
├── Backend.pyproj              # Python Backend Project
├── frontend/
│   └── Frontend.csproj         # Frontend Project
├── src/
│   ├── app.py                  # FastAPI Application
│   ├── controllers/            # Request handlers
│   ├── routers/                # API routes
│   ├── core/                   # Core business logic
│   ├── db/                     # Database configuration
│   └── models/                 # Data models & settings
├── frontend/src/               # React + Vite frontend
├── migrations/                 # Alembic database migrations
├── docker-compose.yml          # Docker Compose config
├── requirements.txt            # Python dependencies
└── README.md                   # Project documentation
```

## 🚀 Quick Start

### Option 1: Docker (Recommended)
```powershell
cd E:\neo-fin-ai
docker-compose up -d
# Backend: http://localhost:8000
# Frontend: http://localhost
```

### Option 2: Local Development
```powershell
# Terminal 1 - Backend
E:\neo-fin-ai\venv\Scripts\python.exe -m uvicorn src.app:app --reload

# Terminal 2 - Frontend
cd frontend
npm run dev
```

## 📚 API Documentation

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## 🛠 Technology Stack

- **Backend**: FastAPI, SQLAlchemy, Alembic, Pydantic
- **Frontend**: React 19, Vite, Mantine UI
- **Database**: PostgreSQL
- **Containerization**: Docker, Docker Compose

## 📝 Development Notes

- Backend runs on port 8000
- Frontend runs on port 80 (Docker) or 5173 (local dev)
- Database is PostgreSQL (configured in docker-compose.yml)
- Migrations are applied automatically on startup (via entrypoint.sh)
