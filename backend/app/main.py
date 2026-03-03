from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.endpoints import router as api_router


def create_app() -> FastAPI:
    app = FastAPI(
        title="neo-fin-ai",
        description="MVP ИИ-ассистента финансового директора",
        version="0.1.0",
    )

    # CORS для локальной разработки фронтенда
    origins = [
        "http://localhost",
        "http://127.0.0.1",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5500",
        "http://127.0.0.1:5500",
    ]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )

    app.include_router(api_router)

    return app


app = create_app()

