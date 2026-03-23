from __future__ import annotations

import logging
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from src.db.database import get_session_maker
from src.db.models import Analysis

logger = logging.getLogger(__name__)


class AnalysisAlreadyExistsError(IntegrityError):
    """
    Raised when an analysis with the same task_id already exists.
    
    Inherits from SQLAlchemy IntegrityError to maintain compatibility
    with existing exception handling code.
    
    Usage:
        raise AnalysisAlreadyExistsError(task_id, orig=e) from e
    """
    def __init__(self, task_id: str, message: str = None, orig: Exception = None):
        # Positional args as required by SQLAlchemy IntegrityError
        stmt = message or f"Analysis with task_id '{task_id}' already exists"
        super().__init__(stmt, {'task_id': task_id}, orig)
        self.task_id = task_id
        self.orig = orig


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
        AnalysisAlreadyExistsError: If task_id already exists
        SQLAlchemyError: On database errors
    """
    session_maker = get_session_maker()
    async with session_maker() as session:
        try:
            analysis = Analysis(task_id=task_id, status=status, result=result)
            session.add(analysis)
            await session.commit()
            await session.refresh(analysis)
            logger.info("Created analysis record: task_id=%s", task_id)
            return analysis
        except IntegrityError as e:
            await session.rollback()
            logger.error("Analysis with task_id '%s' already exists: %s", task_id, e)
            raise AnalysisAlreadyExistsError(task_id, orig=e) from e
        except SQLAlchemyError as e:
            await session.rollback()
            logger.error("Database error creating analysis: %s", e)
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
                logger.debug("Analysis with task_id '%s' not found", task_id)
                return None

            existing.status = status
            existing.result = result
            await session.commit()
            await session.refresh(existing)
            logger.info("Updated analysis record: task_id=%s, status=%s", task_id, status)
            return existing
        except SQLAlchemyError as e:
            await session.rollback()
            logger.error("Database error updating analysis: %s", e)
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
        except SQLAlchemyError as e:
            logger.error("Database error getting analysis: %s", e)
            return None
