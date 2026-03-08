import contextlib
import logging

from fastapi import FastAPI
import uvicorn

import src.routers.system as system_router
import src.routers.analyze as analyze_router
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

# Routers
app.include_router(system_router.router)
app.include_router(analyze_router.router)


if __name__ == "__main__":
	uvicorn.run(app, host="0.0.0.0", port=8000)
