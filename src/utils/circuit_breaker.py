"""
Circuit Breaker pattern implementation for NeoFin AI.

Prevents cascading failures by temporarily disabling services
that are experiencing repeated failures.

Features:
- Configurable failure threshold
- Configurable timeout (recovery period)
- Automatic state transitions (CLOSED → OPEN → HALF_OPEN → CLOSED)
- Async-safe implementation using asyncio.Lock

Usage:
    from src.utils.circuit_breaker import CircuitBreaker

    breaker = CircuitBreaker(
        name="AI Service",
        failure_threshold=5,
        recovery_timeout=120
    )

    async def call_ai():
        if breaker.is_available:
            try:
                result = await call()
                await breaker.record_success()
            except Exception:
                await breaker.record_failure()
"""

import asyncio
import os
import time
from contextlib import asynccontextmanager
from enum import Enum
from typing import Optional

from src.exceptions import (  # noqa: F401 — re-export canonical class
    CircuitBreakerOpenError,
)
from src.utils.logging_config import get_logger

logger = get_logger(__name__)

# Configuration from environment
CIRCUIT_BREAKER_THRESHOLD = int(os.getenv("AI_CIRCUIT_BREAKER_THRESHOLD", "5"))
CIRCUIT_BREAKER_TIMEOUT = int(os.getenv("AI_CIRCUIT_BREAKER_TIMEOUT", "120"))


class CircuitState(Enum):
    """Circuit breaker states."""

    CLOSED = "closed"  # Normal operation, requests allowed
    OPEN = "open"  # Circuit tripped, requests blocked
    HALF_OPEN = "half_open"  # Testing if service recovered


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
        # NB: не выполнять длительные await внутри with lock
        self._lock = asyncio.Lock()

        self._logger = get_logger(__name__)

    @property
    def state(self) -> CircuitState:
        """Get current circuit state (read-only, no lock needed)."""
        self._check_state_transition_unlocked()
        return self._state

    @property
    def is_available(self) -> bool:
        """Check if circuit allows requests (read-only, no lock needed)."""
        self._check_state_transition_unlocked()
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

    def _check_state_transition_unlocked(self) -> None:
        """Check if state should transition without lock (for read-only properties)."""
        if self._state == CircuitState.OPEN and self._last_failure_time:
            elapsed = time.monotonic() - self._last_failure_time
            if elapsed >= self.recovery_timeout:
                self._state = CircuitState.HALF_OPEN
                self._logger.warning(
                    "Circuit breaker for %s transitioned to HALF_OPEN"
                    " (testing recovery)",
                    self.name,
                )

    async def record_success(self) -> None:
        """
        Record successful call.

        Transitions:
        - HALF_OPEN → CLOSED (reset failure count)
        - CLOSED: Reset failure count
        """
        # NB: не выполнять длительные await внутри with lock
        async with self._lock:
            self._success_count += 1

            if self._state == CircuitState.HALF_OPEN:
                self._state = CircuitState.CLOSED
                self._failure_count = 0
                self._logger.info(
                    "Circuit breaker for %s CLOSED (service recovered)", self.name
                )
            elif self._state == CircuitState.CLOSED:
                if self._failure_count > 0:
                    self._failure_count = max(0, self._failure_count - 1)

    async def record_failure(self) -> None:
        """
        Record failed call.

        Transitions:
        - CLOSED → OPEN (if threshold reached)
        - HALF_OPEN → OPEN (reset timeout)
        - CLOSED: Increment failure count
        """
        # NB: не выполнять длительные await внутри with lock
        async with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.monotonic()

            if self._state == CircuitState.HALF_OPEN:
                self._state = CircuitState.OPEN
                self._logger.error(
                    "Circuit breaker for %s stayed OPEN (recovery test failed)",
                    self.name,
                )
            elif self._state == CircuitState.CLOSED:
                if self._failure_count >= self.failure_threshold:
                    self._state = CircuitState.OPEN
                    self._logger.error(
                        "Circuit breaker for %s OPENED (failures: %d/%d)",
                        self.name,
                        self._failure_count,
                        self.failure_threshold,
                    )

    async def reset(self) -> None:
        """Manually reset circuit breaker to CLOSED state."""
        # NB: не выполнять длительные await внутри with lock
        async with self._lock:
            self._state = CircuitState.CLOSED
            self._failure_count = 0
            self._success_count = 0
            self._last_failure_time = None
            self._logger.info("Circuit breaker for %s manually reset", self.name)

    @asynccontextmanager
    async def track_call(self):
        """
        Async context manager for tracking call success/failure.

        Usage:
            async with breaker.track_call():
                result = await unstable_operation()
                return result
        """
        try:
            yield
            await self.record_success()
        except Exception:
            await self.record_failure()
            raise

    def get_status(self) -> dict:
        """
        Get circuit breaker status as dict.

        Returns:
            dict: {state, failure_count, threshold, time_until_retry}
        """
        self._check_state_transition_unlocked()
        return {
            "state": self._state.value,
            "failure_count": self._failure_count,
            "threshold": self.failure_threshold,
            "time_until_retry": (
                self.time_until_retry if self._state == CircuitState.OPEN else 0
            ),
        }


# Global circuit breaker instance for AI service
ai_circuit_breaker = CircuitBreaker(
    name="AI Service",
    failure_threshold=CIRCUIT_BREAKER_THRESHOLD,
    recovery_timeout=CIRCUIT_BREAKER_TIMEOUT,
)
