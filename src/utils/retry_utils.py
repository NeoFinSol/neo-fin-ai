"""
Retry utilities with exponential backoff for NeoFin AI.

Provides resilient retry mechanism for unstable operations:
- AI service calls
- OCR operations
- External API calls

Features:
- Exponential backoff (1s, 2s, 4s, ...)
- Configurable max retries
- Configurable backoff multiplier
- Graceful fallback on final failure

Usage:
    from src.utils.retry_utils import retry_with_backoff
    
    @retry_with_backoff(max_retries=3, backoff_multiplier=2.0)
    async def unstable_operation():
        ...
    
    # Or with custom fallback:
    result = await retry_with_backoff(
        operation=my_func,
        max_retries=3,
        fallback=lambda: {"default": "value"}
    )
"""

import asyncio
import logging
import os
from functools import wraps
from typing import Any, Callable, Optional, TypeVar

from src.utils.logging_config import get_logger

logger = get_logger(__name__)

# Configuration from environment
RETRY_COUNT = int(os.getenv("RETRY_COUNT", "3"))
RETRY_BACKOFF = float(os.getenv("RETRY_BACKOFF", "2.0"))
RETRY_INITIAL_DELAY = float(os.getenv("RETRY_INITIAL_DELAY", "1.0"))

T = TypeVar("T")


class RetryExhaustedError(Exception):
    """Raised when all retry attempts have been exhausted."""

    def __init__(self, message: str, last_exception: Optional[Exception] = None):
        self.message = message
        self.last_exception = last_exception
        super().__init__(self.message)


async def retry_with_backoff(
    operation: Callable[..., Any],
    *args,
    max_retries: int = RETRY_COUNT,
    backoff_multiplier: float = RETRY_BACKOFF,
    initial_delay: float = RETRY_INITIAL_DELAY,
    fallback: Optional[Callable[..., Any]] = None,
    retryable_exceptions: tuple = (Exception,),
    operation_name: str = "operation",
    **kwargs,
) -> Optional[Any]:
    """
    Execute async operation with retry and exponential backoff.

    Args:
        operation: Async function to execute
        *args: Positional arguments for operation
        max_retries: Maximum number of retry attempts (default: 3)
        backoff_multiplier: Multiplier for delay between retries (default: 2.0)
        initial_delay: Initial delay in seconds (default: 1.0)
        fallback: Optional fallback function if all retries fail
        retryable_exceptions: Tuple of exceptions that trigger retry
        operation_name: Name for logging purposes
        **kwargs: Keyword arguments for operation

    Returns:
        Result of operation or fallback

    Raises:
        RetryExhaustedError: If all retries failed and no fallback provided

    Example:
        result = await retry_with_backoff(
            ai_service.invoke,
            {"input": "data"},
            max_retries=3,
            fallback=lambda: None,
            operation_name="AI invocation"
        )
    """
    last_exception: Optional[Exception] = None
    delay = initial_delay

    for attempt in range(max_retries + 1):  # +1 for initial attempt
        try:
            if attempt > 0:
                logger.warning(
                    "Retrying %s (attempt %d/%d)",
                    operation_name,
                    attempt,
                    max_retries,
                    extra={
                        "extra_data": {"attempt": attempt, "max_retries": max_retries}
                    },
                )

            # Execute operation
            if asyncio.iscoroutinefunction(operation):
                result = await operation(*args, **kwargs)
            else:
                result = operation(*args, **kwargs)

            if attempt > 0:
                logger.info("%s succeeded after %d retries", operation_name, attempt)

            return result

        except retryable_exceptions as exc:
            last_exception = exc

            # Log the failure
            logger.warning(
                "%s failed (attempt %d/%d): %s",
                operation_name,
                attempt + 1,
                max_retries + 1,
                exc,
                exc_info=True if attempt == max_retries else False,
            )

            # If this was the last attempt, break
            if attempt >= max_retries:
                break

            # Wait before next retry (exponential backoff)
            logger.info("Waiting %.1fs before next retry", delay)
            await asyncio.sleep(delay)
            delay *= backoff_multiplier

    # All retries exhausted
    if fallback is not None:
        logger.warning(
            "%s failed after %d retries, using fallback",
            operation_name,
            max_retries,
            extra={"extra_data": {"max_retries": max_retries}},
        )

        if asyncio.iscoroutinefunction(fallback):
            return await fallback()
        else:
            return fallback()

    # No fallback - raise error
    raise RetryExhaustedError(
        f"{operation_name} failed after {max_retries} retries",
        last_exception=last_exception,
    )


def with_retry(
    max_retries: int = RETRY_COUNT,
    backoff_multiplier: float = RETRY_BACKOFF,
    initial_delay: float = RETRY_INITIAL_DELAY,
    fallback: Optional[Callable[..., Any]] = None,
    retryable_exceptions: tuple = (Exception,),
    operation_name: Optional[str] = None,
) -> Callable:
    """
    Decorator for adding retry with backoff to async functions.

    Args:
        max_retries: Maximum number of retry attempts
        backoff_multiplier: Multiplier for delay between retries
        initial_delay: Initial delay in seconds
        fallback: Optional fallback function
        retryable_exceptions: Tuple of exceptions that trigger retry
        operation_name: Name for logging (defaults to function name)

    Returns:
        Decorated function with retry logic

    Example:
        @with_retry(max_retries=3, operation_name="AI call")
        async def call_ai(input_data):
            ...
    """

    def decorator(func: Callable) -> Callable:
        op_name = operation_name or func.__name__

        @wraps(func)
        async def wrapper(*args, **kwargs):
            return await retry_with_backoff(
                operation=func,
                *args,
                max_retries=max_retries,
                backoff_multiplier=backoff_multiplier,
                initial_delay=initial_delay,
                fallback=fallback,
                retryable_exceptions=retryable_exceptions,
                operation_name=op_name,
                **kwargs,
            )

        return wrapper

    return decorator


async def retry_with_timeout(
    operation: Callable[..., Any],
    *args,
    timeout: float,
    max_retries: int = RETRY_COUNT,
    backoff_multiplier: float = RETRY_BACKOFF,
    initial_delay: float = RETRY_INITIAL_DELAY,
    fallback: Optional[Callable[..., Any]] = None,
    operation_name: str = "operation",
    **kwargs,
) -> Optional[Any]:
    """
    Execute async operation with timeout and retry.

    Combines timeout control with retry mechanism.

    Args:
        operation: Async function to execute
        *args: Positional arguments for operation
        timeout: Timeout in seconds for each attempt
        max_retries: Maximum number of retry attempts
        backoff_multiplier: Multiplier for delay between retries
        initial_delay: Initial delay in seconds
        fallback: Optional fallback function
        operation_name: Name for logging
        **kwargs: Keyword arguments for operation

    Returns:
        Result of operation or fallback

    Example:
        result = await retry_with_timeout(
            ai_service.invoke,
            {"input": "data"},
            timeout=30.0,
            max_retries=3,
            operation_name="AI call"
        )
    """

    async def operation_with_timeout():
        return await asyncio.wait_for(operation(*args, **kwargs), timeout=timeout)

    return await retry_with_backoff(
        operation=operation_with_timeout,
        max_retries=max_retries,
        backoff_multiplier=backoff_multiplier,
        initial_delay=initial_delay,
        fallback=fallback,
        retryable_exceptions=(asyncio.TimeoutError, Exception),
        operation_name=operation_name,
    )
