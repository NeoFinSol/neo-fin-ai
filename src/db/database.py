from __future__ import annotations

import os
from typing import AsyncGenerator, Optional

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/neofin")

# Engine будет создан лениво при первом вызове get_engine()
_engine: Optional[create_async_engine] = None
AsyncSessionLocal: Optional[async_sessionmaker] = None
Base = declarative_base()


def get_engine() -> create_async_engine:
    """
    Get or create async engine (lazy initialization).
    
    Returns:
        create_async_engine: SQLAlchemy async engine instance
        
    Raises:
        RuntimeError: If engine creation fails
    """
    global _engine, AsyncSessionLocal
    
    if _engine is None:
        try:
            _engine = create_async_engine(DATABASE_URL, echo=False, future=True)
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
