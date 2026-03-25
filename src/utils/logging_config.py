"""
Structured logging configuration for NeoFin AI.

Provides JSON-formatted logs for production and readable text logs for development.
All logs include contextual information (task_id, session_id, module, etc.).

Usage:
    from src.utils.logging_config import get_logger, setup_logging
    
    # Call once at application startup
    setup_logging()
    
    # Get logger in any module
    logger = get_logger(__name__)
    logger.info("Message", extra={"task_id": "abc123"})
"""

import json
import logging
import os
import sys
import traceback
from datetime import datetime, timezone
from functools import wraps
from typing import Any, Callable, Dict, Optional


class JsonFormatter(logging.Formatter):
    """
    JSON formatter for production logs.
    
    Output format:
    {
        "timestamp": "2026-03-25T14:30:00.123456Z",
        "level": "INFO",
        "service": "backend",
        "module": "src.tasks",
        "message": "Processing started",
        "task_id": "abc123",
        "session_id": null,
        "duration_ms": null,
        "extra": {...}
    }
    """
    
    def __init__(self, service: str = "backend"):
        super().__init__()
        self.service = service
    
    def format(self, record: logging.LogRecord) -> str:
        log_data: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "level": record.levelname,
            "service": self.service,
            "module": record.name,
            "message": record.getMessage(),
            "task_id": getattr(record, "task_id", None),
            "session_id": getattr(record, "session_id", None),
            "duration_ms": getattr(record, "duration_ms", None),
            "extra": getattr(record, "extra_data", None),
        }
        
        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = {
                "type": record.exc_info[0].__name__ if record.exc_info[0] else None,
                "message": str(record.exc_info[1]) if record.exc_info[1] else None,
                "traceback": traceback.format_exception(*record.exc_info),
            }
        
        return json.dumps(log_data, ensure_ascii=False, default=str)


class TextFormatter(logging.Formatter):
    """
    Readable text formatter for development.
    
    Output format:
    2026-03-25 14:30:00 | INFO | src.tasks | [task:abc123] Processing started
    """
    
    def __init__(self):
        super().__init__(
            fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
    
    def format(self, record: logging.LogRecord) -> str:
        # Add contextual information to message
        parts = []
        
        if hasattr(record, "task_id") and record.task_id:
            parts.append(f"[task:{record.task_id}]")
        
        if hasattr(record, "session_id") and record.session_id:
            parts.append(f"[session:{record.session_id}]")
        
        if hasattr(record, "duration_ms") and record.duration_ms is not None:
            parts.append(f"[{record.duration_ms:.0f}ms]")
        
        if parts:
            record.msg = f"{' '.join(parts)} {record.msg}"
        
        if hasattr(record, "extra_data") and record.extra_data:
            extra_str = " | ".join(f"{k}={v}" for k, v in record.extra_data.items())
            record.msg = f"{record.msg} | {extra_str}"
        
        return super().format(record)


class ContextAdapter(logging.LoggerAdapter):
    """
    Logger adapter that adds contextual information to all log records.
    
    Usage:
        logger = get_logger(__name__, task_id="abc123")
        logger.info("Message")  # Automatically includes task_id
    """
    
    def process(self, msg: str, kwargs: dict) -> tuple[str, dict]:
        extra = kwargs.get("extra", {})
        extra.update(self.extra)
        
        # Merge extra_data if present
        if "extra_data" in extra:
            merged = extra.get("extra_data", {})
            merged.update(kwargs.pop("extra_data", {}))
            extra["extra_data"] = merged
        
        kwargs["extra"] = extra
        return msg, kwargs


def setup_logging() -> None:
    """
    Configure logging for the application.
    
    Reads LOG_LEVEL and LOG_FORMAT from environment:
    - LOG_LEVEL: DEBUG, INFO, WARNING, ERROR, CRITICAL (default: INFO)
    - LOG_FORMAT: json, text (default: text)
    
    In production (LOG_FORMAT=json):
    - JSON output to stdout
    - Structured for log aggregation (ELK, CloudWatch, etc.)
    
    In development (LOG_FORMAT=text):
    - Human-readable output
    - Colored if terminal supports it
    """
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    log_format = os.getenv("LOG_FORMAT", "text").lower()
    
    # Validate log level
    valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
    if log_level not in valid_levels:
        log_level = "INFO"
    
    # Validate log format
    if log_format not in ["json", "text"]:
        log_format = "text"
    
    # Get root logger
    root_logger = logging.getLogger()
    
    # Skip if already configured (uvicorn may have configured it)
    if root_logger.handlers:
        return
    
    # Create handler
    handler = logging.StreamHandler(sys.stdout)
    
    if log_format == "json":
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(TextFormatter())
    
    # Configure root logger
    root_logger.setLevel(getattr(logging, log_level, logging.INFO))
    root_logger.addHandler(handler)
    
    # Reduce noise from third-party libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


def get_logger(
    name: str,
    task_id: Optional[str] = None,
    session_id: Optional[str] = None,
) -> ContextAdapter:
    """
    Get a logger with optional context.
    
    Args:
        name: Logger name (usually __name__)
        task_id: Optional task ID for correlation
        session_id: Optional session ID for multi-analysis correlation
    
    Returns:
        ContextAdapter: Logger that includes context in all messages
    """
    logger = logging.getLogger(name)
    extra = {}
    
    if task_id:
        extra["task_id"] = task_id
    if session_id:
        extra["session_id"] = session_id
    
    return ContextAdapter(logger, extra)


def log_timing(
    logger: logging.Logger,
    operation: str,
    task_id: Optional[str] = None,
    session_id: Optional[str] = None,
) -> Callable:
    """
    Decorator to log timing of async operations.
    
    Usage:
        @log_timing(logger, "PDF extraction", task_id=task_id)
        async def extract_pdf(path):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            import time
            
            start = time.monotonic()
            log_extra = {"task_id": task_id, "session_id": session_id}
            
            try:
                logger.info(
                    f"{operation} started",
                    extra=log_extra,
                )
                result = await func(*args, **kwargs)
                duration_ms = (time.monotonic() - start) * 1000
                
                logger.info(
                    f"{operation} completed",
                    extra={**log_extra, "duration_ms": duration_ms},
                )
                return result
            except Exception as exc:
                duration_ms = (time.monotonic() - start) * 1000
                logger.error(
                    f"{operation} failed",
                    exc_info=True,
                    extra={**log_extra, "duration_ms": duration_ms},
                )
                raise
        
        return wrapper
    return decorator


class MetricsCollector:
    """
    Simple in-memory metrics collector for /metrics endpoint.
    
    Thread-safe counters for:
    - Total tasks processed
    - Successful/failed tasks
    - Processing times
    - AI failures
    
    Usage:
        metrics = MetricsCollector()
        metrics.record_task_start()
        metrics.record_task_success(duration_ms=1234)
        metrics.record_ai_failure()
        metrics.get_metrics()  # Returns dict for /metrics endpoint
    """
    
    def __init__(self):
        import threading
        self._lock = threading.Lock()
        self._total_tasks = 0
        self._successful_tasks = 0
        self._failed_tasks = 0
        self._ai_failures = 0
        self._processing_times: list[float] = []
        self._max_times = 1000  # Keep last 1000 times for average
    
    def record_task_start(self) -> None:
        """Record start of a new task."""
        with self._lock:
            self._total_tasks += 1
    
    def record_task_success(self, duration_ms: float) -> None:
        """Record successful task completion with duration."""
        with self._lock:
            self._successful_tasks += 1
            self._processing_times.append(duration_ms)
            # Trim old times to prevent memory growth
            if len(self._processing_times) > self._max_times:
                self._processing_times = self._processing_times[-self._max_times:]
    
    def record_task_failure(self) -> None:
        """Record failed task."""
        with self._lock:
            self._failed_tasks += 1
    
    def record_ai_failure(self) -> None:
        """Record AI provider failure (timeout, error, etc.)."""
        with self._lock:
            self._ai_failures += 1
    
    def get_metrics(self) -> dict:
        """
        Get current metrics as dict.
        
        Returns:
            dict: {
                "total_tasks": int,
                "successful_tasks": int,
                "failed_tasks": int,
                "avg_processing_time_ms": float,
                "ai_failures": int
            }
        """
        with self._lock:
            avg_time = (
                sum(self._processing_times) / len(self._processing_times)
                if self._processing_times else 0.0
            )
            
            return {
                "total_tasks": self._total_tasks,
                "successful_tasks": self._successful_tasks,
                "failed_tasks": self._failed_tasks,
                "avg_processing_time_ms": round(avg_time, 2),
                "ai_failures": self._ai_failures,
            }


# Global metrics collector instance
metrics = MetricsCollector()
