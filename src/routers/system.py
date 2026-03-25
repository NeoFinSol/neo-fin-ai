import logging
from datetime import datetime

from fastapi import APIRouter, HTTPException
from sqlalchemy import text

from src.core.ai_service import ai_service
from src.db.database import get_engine
from src.utils.logging_config import get_logger, metrics

logger = get_logger(__name__)

router = APIRouter(prefix="/system", tags=["system"])


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
        "timestamp": datetime.utcnow().isoformat(),
        "services": {
            "db": "ok",
            "ai": "ok",
            "ocr": "ok",  # OCR is bundled with the app, always "ok" if configured
        },
    }
    
    # Check database
    try:
        engine = get_engine()
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        health_status["services"]["db"] = "ok"
    except Exception as e:
        logger.error("Database health check failed: %s", e)
        health_status["services"]["db"] = "down"
        health_status["status"] = "down"
    
    # Check AI service
    if not ai_service.is_configured:
        health_status["services"]["ai"] = "not_configured"
        # Don't mark as degraded if AI was never configured (expected in some deployments)
    elif not ai_service.is_available:
        # Circuit breaker is open
        cb_status = ai_service.get_circuit_breaker_status()
        health_status["services"]["ai"] = "degraded"
        health_status["ai_circuit_breaker"] = cb_status
        
        # Only mark as degraded (not down) since core functionality still works
        if health_status["status"] == "ok":
            health_status["status"] = "degraded"
    else:
        health_status["services"]["ai"] = "ok"
    
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
        "timestamp": datetime.utcnow().isoformat(),
        "components": {
            "database": "unknown",
            "ai_service": "unknown",
        }
    }

    # Check database connection with actual query
    try:
        engine = get_engine()
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        health_status["components"]["database"] = "healthy"
    except Exception as e:
        logger.error("Database health check failed: %s", e)
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
    try:
        engine = get_engine()
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception as e:
        logger.error("Readiness check failed: %s", e)
        raise HTTPException(
            status_code=503,
            detail=f"Service not ready: database connection failed - {str(e)}"
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
