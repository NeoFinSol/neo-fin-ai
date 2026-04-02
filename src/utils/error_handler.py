"""
Global exception handler for NeoFin API.

Provides centralized error handling:
- Catches all unhandled exceptions
- Returns unified error response format
- Logs errors with full traceback
- Hides sensitive details in production

Usage:
    Already registered in src/app.py
    No additional setup required.

Error response format (production):
{
    "status": "failed",
    "error": {
        "code": "INTERNAL_ERROR",
        "message": "An unexpected error occurred"
    }
}

Error response format (development, DEV_MODE=1):
{
    "status": "failed",
    "error": {
        "code": "VALIDATION_ERROR",
        "message": "Invalid input data",
        "details": {
            "field": "value"
        }
    }
}
"""

import logging
import os
import traceback
from typing import Any, Dict, Optional

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError

from src.exceptions import (
    AIServiceError,
    BaseAppError,
    DatabaseError,
    ExtractionError,
    TaskRuntimeError,
)
from src.exceptions import ValidationError as AppValidationError
from src.utils.logging_config import get_logger

logger = get_logger(__name__)

# Check if running in development mode
DEV_MODE = os.getenv("DEV_MODE", "0") == "1"


def create_error_response(
    error_code: str,
    message: str,
    details: Optional[Dict[str, Any]] = None,
    status_code: int = 500,
) -> JSONResponse:
    """
    Create unified error response.

    Args:
        error_code: Machine-readable error code
        message: Human-readable message
        details: Optional details (only included in dev mode)
        status_code: HTTP status code

    Returns:
        JSONResponse with error payload
    """
    error_payload = {
        "code": error_code,
        "message": message,
    }

    # Include details only in development mode
    if DEV_MODE and details:
        error_payload["details"] = details

    response_body = {
        "status": "failed",
        "error": error_payload,
    }

    return JSONResponse(
        status_code=status_code,
        content=response_body,
    )


async def app_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Global exception handler for all unhandled exceptions.

    Logs the error and returns a safe error response.
    """
    # Log the full traceback
    logger.error(
        f"Unhandled exception: {exc}",
        exc_info=True,
        extra={
            "extra_data": {
                "method": request.method,
                "path": request.url.path,
                "client": request.client.host if request.client else "unknown",
            }
        },
    )

    # Return safe error response
    return create_error_response(
        error_code="INTERNAL_ERROR",
        message="An unexpected error occurred. Please try again later.",
        details={"type": type(exc).__name__} if DEV_MODE else None,
        status_code=500,
    )


async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    """
    Handle FastAPI validation errors.

    Returns 422 with validation error details.
    """
    logger.warning(
        f"Validation error: {exc.errors()}",
        extra={
            "extra_data": {
                "method": request.method,
                "path": request.url.path,
            }
        },
    )

    return create_error_response(
        error_code="VALIDATION_ERROR",
        message="Invalid request data",
        details={"errors": exc.errors()} if DEV_MODE else None,
        status_code=422,
    )


async def app_validation_error_handler(
    request: Request,
    exc: AppValidationError,
) -> JSONResponse:
    """
    Handle application-specific validation errors.

    Returns 400 with error details.
    """
    logger.warning(
        f"Application validation error: {exc.message}",
        extra={
            "extra_data": {
                "method": request.method,
                "path": request.url.path,
            }
        },
    )

    return create_error_response(
        error_code=exc.code,
        message=exc.message,
        details=exc.details if DEV_MODE else None,
        status_code=400,
    )


async def extraction_error_handler(
    request: Request,
    exc: ExtractionError,
) -> JSONResponse:
    """
    Handle PDF extraction errors.

    Returns 400 with extraction error details.
    """
    logger.error(
        f"Extraction error: {exc.message}",
        exc_info=True,
        extra={
            "extra_data": {
                "method": request.method,
                "path": request.url.path,
            }
        },
    )

    return create_error_response(
        error_code=exc.code,
        message=exc.message,
        details=exc.details if DEV_MODE else None,
        status_code=400,
    )


async def ai_service_error_handler(
    request: Request,
    exc: AIServiceError,
) -> JSONResponse:
    """
    Handle AI service errors.

    Returns 503 (service unavailable) for AI errors.
    Note: AI errors are typically handled gracefully in the pipeline,
    but this handler catches any that bubble up.
    """
    logger.error(
        f"AI service error: {exc.message}",
        exc_info=True,
        extra={
            "extra_data": {
                "method": request.method,
                "path": request.url.path,
            }
        },
    )

    return create_error_response(
        error_code=exc.code,
        message=exc.message,
        details=exc.details if DEV_MODE else None,
        status_code=503,
    )


async def database_error_handler(
    request: Request,
    exc: DatabaseError,
) -> JSONResponse:
    """
    Handle database errors.

    Returns 503 (service unavailable) for database errors.
    """
    logger.error(
        f"Database error: {exc.message}",
        exc_info=True,
        extra={
            "extra_data": {
                "method": request.method,
                "path": request.url.path,
            }
        },
    )

    return create_error_response(
        error_code=exc.code,
        message=exc.message,
        details=exc.details if DEV_MODE else None,
        status_code=503,
    )


async def task_runtime_error_handler(
    request: Request,
    exc: TaskRuntimeError,
) -> JSONResponse:
    """
    Handle task runtime / dispatch errors.
    """
    logger.error(
        f"Task runtime error: {exc.message}",
        exc_info=True,
        extra={
            "extra_data": {
                "method": request.method,
                "path": request.url.path,
            }
        },
    )

    return create_error_response(
        error_code=exc.code,
        message=exc.message,
        details=exc.details if DEV_MODE else None,
        status_code=503,
    )


async def sqlalchemy_error_handler(
    request: Request,
    exc: SQLAlchemyError,
) -> JSONResponse:
    """
    Handle SQLAlchemy database errors.

    Returns 503 (service unavailable).
    """
    logger.error(
        f"SQLAlchemy error: {exc}",
        exc_info=True,
        extra={
            "extra_data": {
                "method": request.method,
                "path": request.url.path,
            }
        },
    )

    return create_error_response(
        error_code="DATABASE_ERROR",
        message="Database operation failed",
        details={"type": type(exc).__name__} if DEV_MODE else None,
        status_code=503,
    )


async def pydantic_validation_error_handler(
    request: Request,
    exc: ValidationError,
) -> JSONResponse:
    """
    Handle Pydantic validation errors.

    Returns 422 with validation details.
    """
    logger.warning(
        f"Pydantic validation error: {exc.errors()}",
        extra={
            "extra_data": {
                "method": request.method,
                "path": request.url.path,
            }
        },
    )

    return create_error_response(
        error_code="VALIDATION_ERROR",
        message="Invalid data format",
        details={"errors": exc.errors()} if DEV_MODE else None,
        status_code=422,
    )


def register_exception_handlers(app: FastAPI) -> None:
    """
    Register all exception handlers with FastAPI app.

    Call this during application initialization.

    Args:
        app: FastAPI application instance
    """
    # FastAPI validation errors
    app.add_exception_handler(RequestValidationError, validation_exception_handler)

    # Pydantic validation errors
    app.add_exception_handler(ValidationError, pydantic_validation_error_handler)

    # Application-specific errors
    app.add_exception_handler(AppValidationError, app_validation_error_handler)
    app.add_exception_handler(ExtractionError, extraction_error_handler)
    app.add_exception_handler(AIServiceError, ai_service_error_handler)
    app.add_exception_handler(DatabaseError, database_error_handler)
    app.add_exception_handler(TaskRuntimeError, task_runtime_error_handler)

    # SQLAlchemy errors
    app.add_exception_handler(SQLAlchemyError, sqlalchemy_error_handler)

    # Global catch-all handler must be registered last so specific handlers win.
    app.add_exception_handler(Exception, app_exception_handler)

    logger.info("Exception handlers registered")
