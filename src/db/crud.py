from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from src.db.database import get_session_maker
from src.db.models import Analysis


async def create_analysis(task_id: str, status: str, result: dict | None = None) -> Analysis:
    """
    Create a new analysis record.
    
    Args:
        task_id: Unique task identifier
        status: Analysis status
        result: Analysis result data
        
    Returns:
        Analysis: Created analysis object
        
    Raises:
        IntegrityError: If task_id already exists
        SQLAlchemyError: On database errors
    """
    session_maker = get_session_maker()
    async with session_maker() as session:
        try:
            analysis = Analysis(task_id=task_id, status=status, result=result)
            session.add(analysis)
            await session.commit()
            await session.refresh(analysis)
            return analysis
        except IntegrityError as e:
            await session.rollback()
            raise IntegrityError(f"Analysis with task_id '{task_id}' already exists") from e
        except SQLAlchemyError as e:
            await session.rollback()
            raise


async def update_analysis(task_id: str, status: str, result: dict | None = None) -> Analysis | None:
    """
    Update an existing analysis record.
    
    Args:
        task_id: Unique task identifier
        status: New status value
        result: New result data
        
    Returns:
        Analysis | None: Updated analysis object or None if not found
    """
    session_maker = get_session_maker()
    async with session_maker() as session:
        try:
            stmt = select(Analysis).where(Analysis.task_id == task_id)
            existing = await session.scalar(stmt)
            
            if existing is None:
                return None
                
            existing.status = status
            existing.result = result
            await session.commit()
            await session.refresh(existing)
            return existing
        except SQLAlchemyError as e:
            await session.rollback()
            raise


async def get_analysis(task_id: str) -> Analysis | None:
    """
    Get analysis by task_id.
    
    Args:
        task_id: Unique task identifier
        
    Returns:
        Analysis | None: Analysis object or None if not found
    """
    session_maker = get_session_maker()
    async with session_maker() as session:
        try:
            stmt = select(Analysis).where(Analysis.task_id == task_id)
            return await session.scalar(stmt)
        except SQLAlchemyError:
            return None
