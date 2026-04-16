from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from src.core.ai_service import ai_service
from src.db.crud import check_database_connectivity
from src.utils.logging_config import get_logger, metrics

logger = get_logger(__name__)

router = APIRouter(prefix="/system", tags=["system"])


def _current_utc_timestamp() -> str:
    """Return the current time as a timezone-aware UTC ISO-8601 string."""
    return datetime.now(timezone.utc).isoformat()


async def _database_is_available(log_context: str) -> bool:
    """Check database connectivity and log failures for the calling endpoint."""
    try:
        return await check_database_connectivity()
    except Exception as e:
        logger.error("%s: %s", log_context, e)
        return False


def _apply_health_ai_status(health_status: dict) -> None:
    """Mutate the health payload with the current AI service status."""
    if not ai_service.is_configured:
        health_status["services"]["ai"] = "not_configured"
        return

    if not ai_service.is_available:
        health_status["services"]["ai"] = "degraded"
        health_status["ai_circuit_breaker"] = ai_service.get_circuit_breaker_status()
        if health_status["status"] == "ok":
            health_status["status"] = "degraded"
        return

    health_status["services"]["ai"] = "ok"


@router.get("/health")
async def health_check() -> dict:
    """
    Comprehensive health check endpoint.

    Returns status and health of all components:
    - status: "ok", "degraded", or "down"
    - services: individual component health

    Returns:
        dict: {
            "status": "ok|degraded|down",
            "services": {
                "db": "ok|down",
                "ai": "ok|degraded|down",
                "ocr": "ok"
            }
        }
    """
    health_status = {
        "status": "ok",
        "timestamp": _current_utc_timestamp(),
        "services": {
            "db": "ok",
            "ai": "ok",
            "ocr": "ok",  # OCR is bundled with the app, always "ok" if configured
        },
    }

    if not await _database_is_available("Database health check failed"):
        health_status["services"]["db"] = "down"
        health_status["status"] = "down"

    _apply_health_ai_status(health_status)

    return health_status


@router.get("/healthz")
async def healthz_check() -> dict:
    """
    Extended health check with dependency verification.

    Returns:
        dict: Health status with timestamp and component status
    """
    health_status = {
        "status": "healthy",
        "timestamp": _current_utc_timestamp(),
        "components": {
            "database": "unknown",
            "ai_service": "unknown",
        },
    }

    if await _database_is_available("Database health check failed"):
        health_status["components"]["database"] = "healthy"
    else:
        health_status["components"]["database"] = "unhealthy"
        health_status["status"] = "degraded"

    # Check AI service
    if ai_service.is_configured:
        if ai_service.is_available:
            health_status["components"]["ai_service"] = "healthy"
        else:
            cb_status = ai_service.get_circuit_breaker_status()
            health_status["components"]["ai_service"] = "degraded"
            health_status["ai_circuit_breaker"] = cb_status
    else:
        health_status["components"]["ai_service"] = "not_configured"

    return health_status


@router.get("/ready")
async def readiness_check() -> dict[str, str]:
    """
    Readiness check - verifies if the application is ready to accept traffic.

    Returns:
        dict: Readiness status

    Raises:
        HTTPException: 503 if not ready
    """
    # Check if database is available with actual connection test
    if not await _database_is_available("Readiness check failed"):
        raise HTTPException(
            status_code=503,
            detail="Service not ready: database connection failed",
        )

    return {"status": "ready"}


@router.get("/metrics")
async def metrics_endpoint():
    """
    Application metrics endpoint.

    Returns metrics in JSON format for monitoring systems.

    Returns:
        dict: {
            "total_tasks": int,
            "successful_tasks": int,
            "failed_tasks": int,
            "avg_processing_time_ms": float,
            "ai_failures": int
        }
    """
    return metrics.get_metrics()


@router.get("/ai/providers")
async def ai_providers() -> dict[str, list[str] | str | None]:
    """Return configured AI providers for UI/provider selection."""
    available = list(dict.fromkeys(["auto", *ai_service.available_providers]))
    return {
        "default_provider": ai_service.provider,
        "available_providers": available,
    }
