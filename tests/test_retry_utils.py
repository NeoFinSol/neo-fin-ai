import asyncio

import pytest

from src.utils.retry_utils import retry_with_timeout


@pytest.mark.asyncio
async def test_retry_with_timeout_retries_timeout_errors() -> None:
    attempts = 0

    async def flaky_operation() -> str:
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise asyncio.TimeoutError()
        return "ok"

    result = await retry_with_timeout(
        flaky_operation,
        timeout=0.1,
        max_retries=2,
        initial_delay=0.0,
        backoff_multiplier=1.0,
        operation_name="flaky timeout operation",
    )

    assert result == "ok"
    assert attempts == 3


@pytest.mark.asyncio
async def test_retry_with_timeout_does_not_retry_runtime_error() -> None:
    attempts = 0

    async def broken_operation() -> str:
        nonlocal attempts
        attempts += 1
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError, match="boom"):
        await retry_with_timeout(
            broken_operation,
            timeout=0.1,
            max_retries=3,
            initial_delay=0.0,
            backoff_multiplier=1.0,
            operation_name="broken operation",
        )

    assert attempts == 1


@pytest.mark.asyncio
async def test_retry_with_timeout_stops_after_non_timeout_error() -> None:
    attempts = 0

    async def mixed_failure_operation() -> str:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise asyncio.TimeoutError()
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError, match="boom"):
        await retry_with_timeout(
            mixed_failure_operation,
            timeout=0.1,
            max_retries=3,
            initial_delay=0.0,
            backoff_multiplier=1.0,
            operation_name="mixed failure operation",
        )

    assert attempts == 2
