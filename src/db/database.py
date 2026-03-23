from __future__ import annotations

import os
from typing import AsyncGenerator, Optional

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base

# DATABASE_URL is read from environment variable.
# Validation is deferred to get_engine() to allow module imports during testing.
# Set TESTING=1 or CI=1 to bypass validation during tests.
DATABASE_URL: Optional[str] = os.getenv("DATABASE_URL")

# Engine будет создан лениво при первом вызове get_engine()
_engine: Optional[AsyncEngine] = None
AsyncSessionLocal: Optional[async_sessionmaker] = None
Base = declarative_base()


def get_engine() -> create_async_engine:
    """
    Get or create async engine (lazy initialization).
    
    Validates DATABASE_URL presence unless TESTING or CI environment variable is set.

    Returns:
        create_async_engine: SQLAlchemy async engine instance

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
        
        try:
            _engine = create_async_engine(
                db_url,
                echo=False,
                future=True,
                pool_size=20,
                max_overflow=40,
                pool_timeout=30,
                pool_recycle=3600,
                pool_pre_ping=True
            )
            AsyncSessionLocal = async_sessionmaker(
                _engine,
                class_=AsyncSession,
                expire_on_commit=False
            )
        except Exception as e:
            raise RuntimeError(f"Failed to create database engine: {e}") from e

    return _engine


def get_session_maker() -> async_sessionmaker:
    """
    Get or create session maker (lazy initialization).
    
    Returns:
        async_sessionmaker: Session maker instance
        
    Raises:
        RuntimeError: If session maker is not initialized
    """
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
