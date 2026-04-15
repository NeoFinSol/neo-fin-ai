from __future__ import annotations

import logging
import os
from typing import AsyncGenerator, Optional

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import declarative_base

from src.models.settings import app_settings
from src.utils.security_utils import get_safe_db_url_for_logging

# DATABASE_URL is read from environment variable via app_settings.
# Validation is deferred to get_engine() to allow module imports during testing.
DATABASE_URL: Optional[str] = app_settings.database_url

# Engine будет создан лениво при первом вызове get_engine()
_engine: Optional[AsyncEngine] = None
AsyncSessionLocal: Optional[async_sessionmaker] = None
Base = declarative_base()

# Logger for database operations
logger = logging.getLogger(__name__)

# Pool size bounds (A2.2 — named constants instead of magic numbers)
_DB_POOL_SIZE_MIN: int = 1
_DB_POOL_SIZE_DEFAULT: int = 5
_DB_POOL_SIZE_MAX: int = 50
_DB_MAX_OVERFLOW_MIN: int = 0
_DB_MAX_OVERFLOW_DEFAULT: int = 10
_DB_MAX_OVERFLOW_MAX: int = 100
_DB_TEST_URL_DEFAULT: str = (
    "postgresql+asyncpg://postgres:postgres@localhost:5432/neofin_test"
)


def _resolve_database_url() -> str:
    """Determine the effective DB URL based on environment (testing/CI/production)."""
    is_testing = os.getenv("TESTING", "0") == "1"
    is_ci = os.getenv("CI", "0") == "1"

    if not DATABASE_URL and not (is_testing or is_ci):
        raise RuntimeError(
            "DATABASE_URL environment variable is required. "
            "Please set it in your .env file or environment. "
            "For testing, set TESTING=1 or CI=1."
        )

    db_url = os.getenv("DATABASE_URL") or DATABASE_URL
    test_db_url = os.getenv("TEST_DATABASE_URL")

    if is_testing and test_db_url:
        return test_db_url
    if is_testing and not db_url:
        return _DB_TEST_URL_DEFAULT
    return db_url


def _clamp_pool_settings(pool_size: int, max_overflow: int) -> tuple[int, int]:
    """Validate and clamp pool settings to safe bounds; log warnings on adjustment."""
    if pool_size < _DB_POOL_SIZE_MIN:
        logger.warning(
            "DB_POOL_SIZE=%d is too low, using %d", pool_size, _DB_POOL_SIZE_DEFAULT
        )
        pool_size = _DB_POOL_SIZE_DEFAULT
    elif pool_size > _DB_POOL_SIZE_MAX:
        logger.warning(
            "DB_POOL_SIZE=%d is too high, using %d", pool_size, _DB_POOL_SIZE_MAX
        )
        pool_size = _DB_POOL_SIZE_MAX

    if max_overflow < _DB_MAX_OVERFLOW_MIN:
        logger.warning(
            "DB_MAX_OVERFLOW=%d is negative, using %d",
            max_overflow,
            _DB_MAX_OVERFLOW_DEFAULT,
        )
        max_overflow = _DB_MAX_OVERFLOW_DEFAULT
    elif max_overflow > _DB_MAX_OVERFLOW_MAX:
        logger.warning(
            "DB_MAX_OVERFLOW=%d is too high, using %d",
            max_overflow,
            _DB_MAX_OVERFLOW_MAX,
        )
        max_overflow = _DB_MAX_OVERFLOW_MAX

    return pool_size, max_overflow


def _make_session_maker(engine: AsyncEngine) -> async_sessionmaker:
    """Create an async session maker bound to the given engine."""
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


def _create_engine_with_pool(db_url: str, **pool_kwargs) -> AsyncEngine:
    """
    Create async engine with pool settings; falls back to default pool on TypeError.

    asyncpg may not support all SQLAlchemy pool kwargs — the TypeError fallback
    lets the driver use its own internal pooling instead.
    """
    try:
        engine = create_async_engine(
            db_url,
            echo=False,  # Disable SQL logging to prevent credential leakage
            future=True,
            **pool_kwargs,
        )
        logger.info("Database engine created successfully")
        return engine
    except TypeError as exc:
        # Pool kwargs not supported by this asyncpg version — use defaults
        logger.warning(
            "Pool kwargs not supported by asyncpg (%s), using default pooling",
            type(exc).__name__,
        )
        engine = create_async_engine(db_url, echo=False, future=True)
        logger.info("Database engine created with default pool settings")
        return engine
    except Exception as exc:
        logger.error(
            "DB engine creation failed: error_type=%s | db=%s",
            type(exc).__name__,
            get_safe_db_url_for_logging(db_url),
            exc_info=True,
        )
        raise RuntimeError("Failed to create database engine") from exc


def get_engine() -> AsyncEngine:
    """
    Get or create async engine (lazy initialization).

    Returns:
        AsyncEngine: SQLAlchemy async engine instance

    Raises:
        RuntimeError: If DATABASE_URL is not set and not in testing/CI mode
    """
    global _engine, AsyncSessionLocal

    if _engine is not None:
        return _engine

    db_url = _resolve_database_url()

    pool_size, max_overflow = _clamp_pool_settings(
        app_settings.db_pool_size, app_settings.db_max_overflow
    )
    logger.info(
        "Database pool configured: pool_size=%d, max_overflow=%d, timeout=%ds, recycle=%ds",
        pool_size,
        app_settings.db_max_overflow,
        app_settings.db_pool_timeout,
        app_settings.db_pool_recycle,
    )

    _engine = _create_engine_with_pool(
        db_url,
        pool_size=pool_size,
        max_overflow=max_overflow,
        pool_timeout=app_settings.db_pool_timeout,
        pool_recycle=app_settings.db_pool_recycle,
        pool_pre_ping=app_settings.db_pool_pre_ping,
    )
    AsyncSessionLocal = _make_session_maker(_engine)
    return _engine


def get_session_maker() -> async_sessionmaker:
    """
    Get or create session maker (lazy initialization).

    Returns:
        async_sessionmaker: Session maker instance

    Raises:
        RuntimeError: If session maker is not initialized
    """
    global AsyncSessionLocal

    if AsyncSessionLocal is None:
        get_engine()

    if AsyncSessionLocal is None:
        raise RuntimeError("Session maker failed to initialize")

    return AsyncSessionLocal


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Get database session context manager.

    Yields:
        AsyncSession: SQLAlchemy async session

    Raises:
        RuntimeError: If session creation fails
    """
    try:
        session_maker = get_session_maker()
        async with session_maker() as session:
            yield session
    except Exception as e:
        logger.error("Failed to get database session: %s", e)
        raise RuntimeError(f"Failed to get database session: {e}") from e


async def dispose_engine() -> None:
    """
    Dispose of the engine and clean up resources.
    Should be called on application shutdown.
    """
    global _engine, AsyncSessionLocal

    if _engine is not None:
        await _engine.dispose()
        _engine = None
        AsyncSessionLocal = None
        logger.info("Database engine disposed")
