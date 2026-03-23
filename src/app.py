import contextlib
import logging
import os
from typing import List

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

import src.routers.system as system_router
import src.routers.analyze as analyze_router
import src.routers.pdf_tasks as pdf_tasks_router
from src.core.agent import agent
from src.core.gigachat_agent import gigachat_agent
from src.models.settings import app_settings


logger = logging.getLogger(__name__)


def _parse_cors_origins(origins_str: str) -> List[str]:
    """
    Parse and validate CORS origins from environment variable.
    
    Args:
        origins_str: Comma-separated list of origins
        
    Returns:
        List[str]: Validated list of origins
        
    Raises:
        ValueError: If '*' is found in origins (security risk)
    """
    if not origins_str:
        return []
    
    # Split by comma, strip whitespace, filter empty strings
    origins = [origin.strip() for origin in origins_str.split(',')]
    origins = [origin for origin in origins if origin]
    
    # Security check: reject wildcard origins
    if '*' in origins:
        raise ValueError(
            "Wildcard '*' CORS origin is not allowed for security reasons. "
            "Specify explicit origins instead."
        )
    
    # Validate origin format (must start with http:// or https://)
    valid_origins = []
    for origin in origins:
        if origin.startswith(('http://', 'https://')):
            valid_origins.append(origin)
        else:
            logger.warning(
                "Skipping invalid CORS origin '%s' (must start with http:// or https://)", 
                origin
            )
    
    return valid_origins


def _parse_cors_list(list_str: str, default_values: List[str]) -> List[str]:
    """
    Parse comma-separated list with defaults.
    
    Args:
        list_str: Comma-separated list from environment
        default_values: Default values if list_str is empty
        
    Returns:
        List[str]: Parsed and validated list
    """
    if not list_str:
        return default_values
    
    items = [item.strip() for item in list_str.split(',')]
    return [item for item in items if item]


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

    # AI service auto-configures based on available credentials
    # Priority: GigaChat > Qwen > Local LLM (Ollama)
    if ai_service.is_configured:
        logger.info("AI service configured with provider: %s", ai_service.provider)
    else:
        logger.warning("No AI service configured. NLP features will be disabled.")

    yield


app = FastAPI(version="0.1.0", lifespan=lifespan)

# CORS configuration - restricted and validated for security
try:
    allow_credentials = os.getenv("CORS_ALLOW_CREDENTIALS", "false").lower() == "true"
    
    # Parse and validate CORS origins with secure defaults
    default_origins = ["http://localhost", "http://localhost:80", "http://127.0.0.1", "http://127.0.0.1:80"]
    allow_origins = _parse_cors_origins(
        os.getenv("CORS_ALLOW_ORIGINS", ",".join(default_origins))
    )
    
    # Parse methods and headers with defaults
    allow_methods = _parse_cors_list(
        os.getenv("CORS_ALLOW_METHODS", ""),
        ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
    )
    
    allow_headers = _parse_cors_list(
        os.getenv("CORS_ALLOW_HEADERS", ""),
        ["Content-Type", "Authorization", "X-Requested-With"]
    )
    
    logger.info(
        "CORS configured - Origins: %d, Methods: %d, Headers: %d",
        len(allow_origins), len(allow_methods), len(allow_headers)
    )
    
except ValueError as e:
    logger.error("CORS configuration error: %s", e)
    # Fall back to safe defaults (localhost only)
    allow_origins = default_origins
    allow_methods = ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
    allow_headers = ["Content-Type", "Authorization", "X-Requested-With"]
    allow_credentials = False
    logger.warning("Using safe default CORS configuration")

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
