import contextlib
import logging
import os
from typing import List

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address
import uvicorn

import src.routers.system as system_router
import src.routers.analyze as analyze_router
import src.routers.pdf_tasks as pdf_tasks_router
from src.core.ai_service import ai_service
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
    # Configure structured logging
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    log_format = os.getenv("LOG_FORMAT", "text").lower()
    
    if log_format == "json":
        # JSON format for production
        logging.basicConfig(
            level=getattr(logging, log_level, logging.INFO),
            format='{"timestamp": "%(asctime)s", "level": "%(levelname)s", "logger": "%(name)s", "message": "%(message)s"}',
            datefmt="%Y-%m-%dT%H:%M:%S%z"
        )
    else:
        # Text format for development
        logging.basicConfig(
            level=getattr(logging, log_level, logging.INFO),
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )

    # AI service auto-configures based on available credentials
    # Priority: GigaChat > Qwen > Local LLM (Ollama)
    if ai_service.is_configured:
        logger.info("AI service configured with provider: %s", ai_service.provider)
    else:
        logger.warning("No AI service configured. NLP features will be disabled.")
    
    logger.info("Application startup complete")

    yield
    
    logger.info("Application shutdown complete")


# Initialize rate limiter
def get_rate_limit() -> str:
    """Get rate limit from environment or use default."""
    return os.getenv("RATE_LIMIT", "100/minute")


# Use Limiter from slowapi (correct API)
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[get_rate_limit()],
    # Use memory storage for single-instance deployments
    # For production with multiple instances, use Redis:
    # storage_uri="redis://localhost:6379"
)

app = FastAPI(version="0.1.0", lifespan=lifespan)

# Add rate limiter to app state
app.state.limiter = limiter

# Add exception handler for rate limit exceeded
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Add SlowAPI middleware (correct way to apply rate limiting)
app.add_middleware(SlowAPIMiddleware)

# CORS configuration - restricted and validated for security
