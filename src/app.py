import contextlib
import logging
import os
from typing import List

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address

from src.models.settings import app_settings
import src.routers.system as system_router
import src.routers.analyze as analyze_router
import src.routers.pdf_tasks as pdf_tasks_router
import src.routers.analyses as analyses_router
import src.routers.multi_analysis as multi_analysis_router
import src.routers.websocket as websocket_router
from src.core.ai_service import ai_service
from src.core.runtime_events import runtime_event_bridge
from src.db.database import dispose_engine
from src.utils.logging_config import setup_logging, get_logger
from src.utils.error_handler import register_exception_handlers


logger = get_logger(__name__)


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
    origins = [origin.strip() for origin in origins_str.split(",")]
    origins = [origin for origin in origins if origin]

    # Security check: reject wildcard origins
    if "*" in origins:
        raise ValueError(
            "Wildcard '*' CORS origin is not allowed for security reasons. "
            "Specify explicit origins instead."
        )

    # Validate origin format (must start with http:// or https://)
    valid_origins = []
    for origin in origins:
        if origin.startswith(("http://", "https://")):
            valid_origins.append(origin)
        else:
            logger.warning(
                "Skipping invalid CORS origin '%s' (must start with http:// or https://)",
                origin,
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

    items = [item.strip() for item in list_str.split(",")]
    return [item for item in items if item]


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    # Setup structured logging
    setup_logging()

    # AI service auto-configures based on available credentials
    # Priority: GigaChat > Qwen > Local LLM (Ollama)
    if ai_service.is_configured:
        logger.info("AI service configured with provider: %s", ai_service.provider)
    else:
        logger.warning("No AI service configured. NLP features will be disabled.")

    async with runtime_event_bridge():
        logger.info("Application startup complete")
        yield

    await ai_service.close()
    await dispose_engine()
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
register_exception_handlers(app)

# Add rate limiter to app state
app.state.limiter = limiter

# Add exception handler for rate limit exceeded
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Add SlowAPI middleware (correct way to apply rate limiting)
app.add_middleware(SlowAPIMiddleware)

# CORS configuration - restricted and validated for security
default_origins = [
    "http://localhost",
    "http://localhost:80",
    "http://127.0.0.1",
    "http://127.0.0.1:80",
]

try:
    allow_credentials = os.getenv("CORS_ALLOW_CREDENTIALS", "false").lower() == "true"

    # In development mode, be more permissive with CORS for localhost origins
    if app_settings.dev_mode:
        allow_origins = ["*"]
        allow_methods = ["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"]
        allow_headers = ["*"]
        allow_credentials = False  # Cannot use credentials=True with wildcard origins
        logger.info("CORS configured in DEV MODE: allowing all origins")
    else:
        # Parse and validate CORS origins with secure defaults
        allow_origins = _parse_cors_origins(
            os.getenv("CORS_ALLOW_ORIGINS", ",".join(default_origins))
        )

        # Parse methods and headers with defaults
        allow_methods = _parse_cors_list(
            os.getenv("CORS_ALLOW_METHODS", ""),
            ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        )

        allow_headers = _parse_cors_list(
            os.getenv("CORS_ALLOW_HEADERS", ""),
            ["Content-Type", "Authorization", "X-Requested-With", "X-API-Key"],
        )

        logger.info(
            "CORS configured - Origins: %d, Methods: %d, Headers: %d",
            len(allow_origins),
            len(allow_methods),
            len(allow_headers),
        )

except ValueError as e:
    logger.error("CORS configuration error: %s", e)
    # Fall back to safe defaults (localhost only)
    allow_origins = default_origins
    allow_methods = ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
    allow_headers = ["Content-Type", "Authorization", "X-Requested-With", "X-API-Key"]
    allow_credentials = False
    logger.warning("Using safe default CORS configuration")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=allow_credentials,
    allow_methods=allow_methods,
    allow_headers=allow_headers,
)


# =============================================================================
# Request Logging Middleware
# Logs every HTTP request with method, path, status code, and duration
# =============================================================================
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """
    Middleware to log all HTTP requests.
    
    Logs:
    - Request method and path
    - Response status code
    - Processing duration in milliseconds
    - User agent (for debugging)
    """
    import time
    
    start_time = time.monotonic()
    
    # Extract task_id from query params or headers if present
    task_id = request.query_params.get("task_id")
    if not task_id:
        task_id = request.headers.get("X-Task-ID")
    
    # Log request
    logger.info(
        "%s %s started",
        request.method,
        request.url.path,
        extra={
            "task_id": task_id,
            "extra_data": {
                "method": request.method,
                "path": request.url.path,
                "query": str(request.query_params),
                "user_agent": request.headers.get("user-agent", "unknown"),
            }
        },
    )
    
    response = await call_next(request)

    # Calculate duration
    duration_ms = (time.monotonic() - start_time) * 1000

    # Error handlers are responsible for logging exception details.
    log_level = logging.WARNING if response.status_code >= 400 else logging.INFO
    logger.log(
        log_level,
        "%s %s completed",
        request.method,
        request.url.path,
        extra={
            "task_id": task_id,
            "duration_ms": duration_ms,
            "extra_data": {
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": round(duration_ms, 2),
            }
        },
    )

    return response


# Routers (must be added after middleware)
app.include_router(system_router.router)
app.include_router(analyze_router.router)
app.include_router(pdf_tasks_router.router)
app.include_router(analyses_router.router)
app.include_router(multi_analysis_router.router)
app.include_router(websocket_router.router)
