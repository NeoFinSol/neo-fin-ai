"""
Custom exception hierarchy for NeoFin AI.

All application-specific exceptions inherit from BaseAppError.
Each exception has:
- code: Machine-readable error code (for API responses)
- message: Human-readable description
- details: Optional additional context (only in dev mode)

Usage:
    from src.exceptions import ExtractionError, AIServiceError
    
    try:
        ...
    except ExtractionError as e:
        logger.error(f"Extraction failed: {e.message}", extra={"error_code": e.code})
        raise
"""

from typing import Any, Dict, Optional


class BaseAppError(Exception):
    """
    Base class for all application-specific exceptions.

    Attributes:
        code: Machine-readable error code (e.g., "EXTRACTION_FAILED")
        message: Human-readable description
        details: Optional additional context (for debugging)
    """

    def __init__(
        self,
        message: str,
        code: str = "INTERNAL_ERROR",
        details: Optional[Dict[str, Any]] = None,
    ):
        self.message = message
        self.code = code
        self.details = details or {}
        super().__init__(self.message)

    def to_dict(self, include_details: bool = False) -> dict:
        """
        Convert exception to dictionary for API response.

        Args:
            include_details: Include detailed error context (only in dev mode)

        Returns:
            dict: {code, message, details (optional)}
        """
        result = {
            "code": self.code,
            "message": self.message,
        }

        if include_details and self.details:
            result["details"] = self.details

        return result


class ValidationError(BaseAppError):
    """
    Raised when input validation fails.

    Examples:
    - Invalid PDF file (not a PDF or corrupted)
    - File size exceeds limit
    - Missing required fields in request
    """

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            code="VALIDATION_ERROR",
            details=details,
        )


class ExtractionError(BaseAppError):
    """
    Raised when PDF extraction fails.

    Examples:
    - Cannot extract text from PDF
    - OCR failed on scanned document
    - Table extraction returned no results
    """

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            code="EXTRACTION_FAILED",
            details=details,
        )


class AIServiceError(BaseAppError):
    """
    Raised when AI service call fails.

    Examples:
    - AI provider timeout
    - AI provider returns error
    - AI provider unavailable
    """

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            code="AI_SERVICE_ERROR",
            details=details,
        )


class DatabaseError(BaseAppError):
    """
    Raised when database operation fails.

    Examples:
    - Connection lost
    - Query timeout
    - Integrity constraint violation
    """

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            code="DATABASE_ERROR",
            details=details,
        )


class TaskRuntimeError(BaseAppError):
    """
    Raised when task dispatch/runtime infrastructure is unavailable.
    """

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            code="TASK_RUNTIME_ERROR",
            details=details,
        )


class CircuitBreakerOpenError(BaseAppError):
    """
    Raised when a circuit breaker is open and the request is rejected.

    Canonical definition lives here; src/utils/circuit_breaker.py re-exports
    this class so all callers share the same exception identity.
    """

    def __init__(
        self,
        service_name: str,
        retry_after: int,
        details: Optional[Dict[str, Any]] = None,
    ):
        self.service_name = service_name
        self.retry_after = retry_after
        super().__init__(
            message=(
                f"Circuit breaker open for {service_name}, "
                f"retry after {retry_after}s"
            ),
            code="CIRCUIT_BREAKER_OPEN",
            details=details,
        )
