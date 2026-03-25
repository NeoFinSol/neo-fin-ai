"""
Circuit Breaker pattern implementation for NeoFin AI.

Prevents cascading failures by temporarily disabling services
that are experiencing repeated failures.

Features:
- Configurable failure threshold
- Configurable timeout (recovery period)
- Automatic state transitions (CLOSED → OPEN → HALF_OPEN → CLOSED)
- Thread-safe implementation

Usage:
    from src.utils.circuit_breaker import CircuitBreaker
    
    breaker = CircuitBreaker(
        name="AI Service",
        failure_threshold=5,
        recovery_timeout=120
    )
    
    async def call_ai():
        with breaker.track_call():
            return await ai_service.invoke(input)
    
    # Or manually:
    if breaker.is_available():
        try:
            result = await call()
            breaker.record_success()
        except Exception:
            breaker.record_failure()
"""

import asyncio
import logging
import os
import time
from contextlib import contextmanager
from enum import Enum
from threading import Lock
from typing import Optional

from src.utils.logging_config import get_logger

logger = get_logger(__name__)

# Configuration from environment
CIRCUIT_BREAKER_THRESHOLD = int(os.getenv("AI_CIRCUIT_BREAKER_THRESHOLD", "5"))
CIRCUIT_BREAKER_TIMEOUT = int(os.getenv("AI_CIRCUIT_BREAKER_TIMEOUT", "120"))


class CircuitState(Enum):
    """Circuit breaker states."""
    
    CLOSED = "closed"      # Normal operation, requests allowed
    OPEN = "open"          # Circuit tripped, requests blocked
    HALF_OPEN = "half_open"  # Testing if service recovered


class CircuitBreakerOpenError(Exception):
    """Raised when circuit breaker is open and request is rejected."""
    
    def __init__(self, service_name: str, retry_after: int):
        self.service_name = service_name
        self.retry_after = retry_after
        super().__init__(
            f"Circuit breaker open for {service_name}, retry after {retry_after}s"
        )


class CircuitBreaker:
    """
    Circuit breaker for protecting against cascading failures.
    
    State transitions:
    - CLOSED → OPEN: When failure_count >= threshold
    - OPEN → HALF_OPEN: After recovery_timeout seconds
    - HALF_OPEN → CLOSED: On successful call
    - HALF_OPEN → OPEN: On failed call
    
    Attributes:
        name: Service name for logging
        failure_threshold: Number of failures before opening circuit
        recovery_timeout: Seconds to wait before testing recovery
    """
    
    def __init__(
        self,
        name: str,
        failure_threshold: int = CIRCUIT_BREAKER_THRESHOLD,
        recovery_timeout: int = CIRCUIT_BREAKER_TIMEOUT,
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: Optional[float] = None
        self._lock = Lock()
        
        self._logger = get_logger(__name__)
    
    @property
    def state(self) -> CircuitState:
        """Get current circuit state."""
        with self._lock:
            self._check_state_transition()
            return self._state
    
    @property
    def is_available(self) -> bool:
        """Check if circuit allows requests."""
        with self._lock:
            self._check_state_transition()
            return self._state != CircuitState.OPEN
    
    @property
    def failure_count(self) -> int:
        """Get current failure count."""
        return self._failure_count
    
    @property
    def time_until_retry(self) -> int:
        """Get seconds until circuit might transition to HALF_OPEN."""
        if self._last_failure_time is None:
            return 0
        
        elapsed = time.monotonic() - self._last_failure_time
        remaining = self.recovery_timeout - elapsed
        return max(0, int(remaining))
    
    def _check_state_transition(self) -> None:
        """Check if state should transition (must be called with lock held)."""
        if self._state == CircuitState.OPEN and self._last_failure_time:
            elapsed = time.monotonic() - self._last_failure_time
            if elapsed >= self.recovery_timeout:
                self._state = CircuitState.HALF_OPEN
                self._logger.warning(
                    f"Circuit breaker for {self.name} transitioned to HALF_OPEN "
                    f"(testing recovery)"
                )
    
    def record_success(self) -> None:
        """
        Record successful call.
        
        Transitions:
        - HALF_OPEN → CLOSED (reset failure count)
        - CLOSED: Reset failure count
        """
        with self._lock:
            self._success_count += 1
            
            if self._state == CircuitState.HALF_OPEN:
                self._state = CircuitState.CLOSED
                self._failure_count = 0
                self._logger.info(
                    f"Circuit breaker for {self.name} CLOSED (service recovered)"
                )
            elif self._state == CircuitState.CLOSED:
                # Reset failure count on success
                if self._failure_count > 0:
                    self._failure_count = max(0, self._failure_count - 1)
    
    def record_failure(self) -> None:
        """
        Record failed call.
        
        Transitions:
        - CLOSED → OPEN (if threshold reached)
        - HALF_OPEN → OPEN (reset timeout)
        - CLOSED: Increment failure count
        """
        with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.monotonic()
            
            if self._state == CircuitState.HALF_OPEN:
                self._state = CircuitState.OPEN
                self._logger.error(
                    f"Circuit breaker for {self.name} stayed OPEN "
                    f"(recovery test failed)"
                )
            elif self._state == CircuitState.CLOSED:
                if self._failure_count >= self.failure_threshold:
                    self._state = CircuitState.OPEN
                    self._logger.error(
                        f"Circuit breaker for {self.name} OPENED "
                        f"(failures: {self._failure_count}/{self.failure_threshold})"
                    )
    
    def reset(self) -> None:
        """Manually reset circuit breaker to CLOSED state."""
        with self._lock:
            self._state = CircuitState.CLOSED
            self._failure_count = 0
            self._success_count = 0
            self._last_failure_time = None
            self._logger.info(f"Circuit breaker for {self.name} manually reset")
    
    @contextmanager
    def track_call(self):
        """
        Context manager for tracking call success/failure.
        
        Usage:
            with breaker.track_call():
                result = await unstable_operation()
                return result
        """
        try:
            yield
            self.record_success()
        except Exception:
            self.record_failure()
            raise
    
    def get_status(self) -> dict:
        """
        Get circuit breaker status as dict.
        
        Returns:
            dict: {state, failure_count, threshold, time_until_retry}
        """
        with self._lock:
            self._check_state_transition()
            return {
                "state": self._state.value,
                "failure_count": self._failure_count,
                "threshold": self.failure_threshold,
                "time_until_retry": self.time_until_retry if self._state == CircuitState.OPEN else 0,
            }


# Global circuit breaker instance for AI service
ai_circuit_breaker = CircuitBreaker(
    name="AI Service",
    failure_threshold=CIRCUIT_BREAKER_THRESHOLD,
    recovery_timeout=CIRCUIT_BREAKER_TIMEOUT,
)
