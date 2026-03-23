import logging
from datetime import datetime

from fastapi import APIRouter, HTTPException

from src.core.ai_service import ai_service
from src.db.database import get_engine

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/system", tags=["system"])


@router.get("/health")
def health_check() -> dict[str, str]:
    """Basic health check endpoint."""
    return {"status": "ok"}


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
    
    # Check database connection
    try:
        engine = get_engine()
        # Engine exists
        health_status["components"]["database"] = "healthy"
    except Exception as e:
        logger.error("Database health check failed: %s", e)
        health_status["components"]["database"] = "unhealthy"
        health_status["status"] = "degraded"
    
    # Check AI service
    if ai_service.is_configured:
        health_status["components"]["ai_service"] = "healthy"
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
    # Check if database is available
    try:
        engine = get_engine()
        if engine is None:
            raise HTTPException(
                status_code=503,
                detail="Service not ready: database connection not available"
            )
    except Exception as e:
        logger.error("Readiness check failed: %s", e)
        raise HTTPException(
            status_code=503,
            detail=f"Service not ready: {str(e)}"
        )
    
    return {"status": "ready"}
