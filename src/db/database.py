from __future__ import annotations

import logging
import os
from typing import AsyncGenerator, Optional

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base

from src.core.security import get_safe_db_url_for_logging
from src.models.settings import app_settings

# DATABASE_URL is read from environment variable via app_settings.
# Validation is deferred to get_engine() to allow module imports during testing.
DATABASE_URL: Optional[str] = app_settings.database_url

# Engine будет создан лениво при первом вызове get_engine()
_engine: Optional[AsyncEngine] = None
AsyncSessionLocal: Optional[async_sessionmaker] = None
Base = declarative_base()

# Logger for database operations
logger = logging.getLogger(__name__)


def get_engine() -> AsyncEngine:
    """
    Get or create async engine (lazy initialization).

    Validates DATABASE_URL presence unless TESTING or CI environment variable is set.

    Returns:
        AsyncEngine: SQLAlchemy async engine instance

    Raises:
        RuntimeError: If DATABASE_URL is not set and not in testing/CI mode
    """
    global _engine, AsyncSessionLocal

    if _engine is None:
        # Check DATABASE_URL - allow bypass for testing
        is_testing = os.getenv("TESTING", "0") == "1"
        is_ci = os.getenv("CI", "0") == "1"

        if not DATABASE_URL and not (is_testing or is_ci):
            raise RuntimeError(
                "DATABASE_URL environment variable is required. "
                "Please set it in your .env file or environment. "
                "For testing, set TESTING=1 or CI=1."
            )

        # Use default for testing if DATABASE_URL not set
        db_url = DATABASE_URL
        if is_testing and not db_url:
            db_url = "postgresql+asyncpg://postgres:postgres@localhost:5432/neofin_test"

        # Connection pool settings from app_settings
        pool_size = app_settings.db_pool_size
        max_overflow = app_settings.db_max_overflow
        pool_timeout = app_settings.db_pool_timeout
        pool_recycle = app_settings.db_pool_recycle
        pool_pre_ping = app_settings.db_pool_pre_ping

        # Validate pool settings to prevent misconfiguration
        if pool_size < 1:
            logger.warning("DB_POOL_SIZE=%d is too low, using 5", pool_size)
            pool_size = 5
        elif pool_size > 50:
            logger.warning("DB_POOL_SIZE=%d is too high, using 50", pool_size)
            pool_size = 50

        if max_overflow < 0:
            logger.warning("DB_MAX_OVERFLOW=%d is negative, using 10", max_overflow)
            max_overflow = 10
        elif max_overflow > 100:
            logger.warning("DB_MAX_OVERFLOW=%d is too high, using 100", max_overflow)
            max_overflow = 100

        logger.info(
            "Database pool configured: pool_size=%d, max_overflow=%d, timeout=%ds, recycle=%ds",
            pool_size, max_overflow, pool_timeout, pool_recycle
        )

        try:
            # For asyncpg, pool settings are handled by the driver itself
            # SQLAlchemy 2.0+ supports these parameters for async engines
            # If asyncpg doesn't support pool kwargs, it will raise TypeError
            _engine = create_async_engine(
                db_url,
                echo=False,  # Disable SQL logging to prevent credential leakage
                future=True,
                # Pool settings - SQLAlchemy 2.0+ passes these to asyncpg
                # If these cause TypeError, asyncpg will use its internal pooling
                pool_size=pool_size,
                max_overflow=max_overflow,
                pool_pre_ping=pool_pre_ping,
                # Note: pool_timeout and pool_recycle may be ignored by asyncpg
            )
            AsyncSessionLocal = async_sessionmaker(
                _engine,
                class_=AsyncSession,
                expire_on_commit=False
            )
            logger.info("Database engine created successfully")
        except TypeError as e:
            # Pool kwargs not supported by this asyncpg version - use defaults
            logger.warning(
                "Pool kwargs not supported by asyncpg (%s), using default pooling",
                type(e).__name__
            )
            _engine = create_async_engine(
                db_url,
                echo=False,
                future=True,
            )
            AsyncSessionLocal = async_sessionmaker(
                _engine,
                class_=AsyncSession,
                expire_on_commit=False
            )
            logger.info("Database engine created with default pool settings")
        except Exception as e:
            # Log error without exposing credentials
            # Use get_safe_db_url_for_logging to ensure no credentials leak
            logger.error(
                "DB engine creation failed: error_type=%s | db=%s",
                type(e).__name__,
                get_safe_db_url_for_logging(db_url),
                exc_info=True
            )
            raise RuntimeError("Failed to create database engine") from e

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
