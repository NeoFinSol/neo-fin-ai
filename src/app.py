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
    # Configure structured logging with validation
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    log_format = os.getenv("LOG_FORMAT", "text").lower()
    
    # Validate log level
    valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
    if log_level not in valid_levels:
        log_level = "INFO"
    
    # Validate log format
    if log_format not in ["json", "text"]:
        log_format = "text"
    
    # Only configure logging if not already configured by uvicorn
    root_logger = logging.getLogger()
    if not root_logger.handlers:
        if log_format == "json":
            # JSON format for production
            logging.basicConfig(
                level=getattr(logging, log_level, logging.INFO),
                format='{"timestamp": "%(asctime)s", "level": "%(levelname)s", "logger": "%(name)s", "message": "%(message)s"}',
                datefmt="%Y-%m-%dT%H:%M:%S"
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


# Initialize rate limiter using validated settings
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[app_settings.rate_limit],
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

# Routers (must be added after middleware)
app.include_router(system_router.router)
app.include_router(analyze_router.router)
app.include_router(pdf_tasks_router.router)
