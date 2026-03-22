import contextlib
import logging
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

import src.routers.system as system_router
import src.routers.analyze as analyze_router
import src.routers.pdf_tasks as pdf_tasks_router
from src.core.agent import agent
from src.models.settings import app_settings


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
	logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

	agent.set_config(
		app_settings.qwen_api_key,
		app_settings.qwen_api_url
	)

	yield


app = FastAPI(version="0.1.0", lifespan=lifespan)

# CORS configuration - restricted for security
allow_credentials = os.getenv("CORS_ALLOW_CREDENTIALS", "false").lower() == "true"
allow_origins = os.getenv(
    "CORS_ALLOW_ORIGINS", 
    "http://localhost,http://localhost:80,http://127.0.0.1,http://127.0.0.1:80"
).split(",")
allow_methods = os.getenv(
    "CORS_ALLOW_METHODS",
    "GET,POST,PUT,DELETE,OPTIONS"
).split(",")
allow_headers = os.getenv(
    "CORS_ALLOW_HEADERS",
    "Content-Type,Authorization,X-Requested-With"
).split(",")

app.add_middleware(
	CORSMiddleware,
	allow_origins=allow_origins,
	allow_credentials=allow_credentials,
	allow_methods=allow_methods,
	allow_headers=allow_headers,
)

# Routers
app.include_router(system_router.router)
app.include_router(analyze_router.router)
app.include_router(pdf_tasks_router.router)


if __name__ == "__main__":
	uvicorn.run(app, host="0.0.0.0", port=8000)
