from __future__ import annotations

import logging
from datetime import datetime, timezone
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from src.db.database import get_session_maker
from src.db.models import Analysis, MultiAnalysisSession

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


async def get_analyses_list(page: int, page_size: int) -> tuple[list[Analysis], int]:
    """
    Get paginated list of analyses ordered by created_at DESC.

    Args:
        page: Page number (1-based)
        page_size: Number of records per page

    Returns:
        tuple[list[Analysis], int]: (items, total) where total is the overall count
    """
    session_maker = get_session_maker()
    async with session_maker() as session:
        try:
            offset = (page - 1) * page_size
            items_stmt = (
                select(Analysis)
                .order_by(Analysis.created_at.desc())
                .limit(page_size)
                .offset(offset)
            )
            count_stmt = select(func.count()).select_from(Analysis)

            items_result = await session.scalars(items_stmt)
            total_result = await session.scalar(count_stmt)

            items = list(items_result.all())
            total = total_result or 0
            logger.debug("get_analyses_list: page=%s, page_size=%s, total=%s", page, page_size, total)
            return items, total
        except SQLAlchemyError as e:
            logger.error("Database error listing analyses: %s", e)
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
            raise


async def create_multi_session(
    session_id: str,
    user_id: str | None = None,
) -> MultiAnalysisSession:
    """
    Create a new multi-analysis session record.

    Args:
        session_id: Unique session identifier
        user_id: Optional user identifier

    Returns:
        MultiAnalysisSession: Created session object
    """
    session_maker = get_session_maker()
    async with session_maker() as session:
        try:
            record = MultiAnalysisSession(
                session_id=session_id,
                user_id=user_id,
                status="processing",
                progress={"completed": 0, "total": 0},
            )
            session.add(record)
            await session.commit()
            await session.refresh(record)
            logger.info("Created multi_analysis_session: session_id=%s", session_id)
            return record
        except SQLAlchemyError as e:
            await session.rollback()
            logger.error("Database error creating multi_analysis_session: %s", e)
            raise


async def update_multi_session(
    session_id: str,
    *,
    status: str | None = None,
    progress: dict | None = None,
    result: dict | None = None,
) -> MultiAnalysisSession | None:
    """
    Update an existing multi-analysis session.

    Args:
        session_id: Unique session identifier
        status: New status value (optional)
        progress: New progress dict (optional)
        result: New result dict (optional)

    Returns:
        MultiAnalysisSession | None: Updated object or None if not found
    """
    session_maker = get_session_maker()
    async with session_maker() as session:
        try:
            stmt = select(MultiAnalysisSession).where(
                MultiAnalysisSession.session_id == session_id
            )
            record = await session.scalar(stmt)

            if record is None:
                logger.debug("MultiAnalysisSession '%s' not found", session_id)
                return None

            if status is not None:
                record.status = status
            if progress is not None:
                record.progress = progress
            if result is not None:
                record.result = result
            record.updated_at = datetime.now(timezone.utc)

            await session.commit()
            await session.refresh(record)
            logger.info("Updated multi_analysis_session: session_id=%s, status=%s", session_id, record.status)
            return record
        except SQLAlchemyError as e:
            await session.rollback()
            logger.error("Database error updating multi_analysis_session: %s", e)
            raise


async def get_multi_session(session_id: str) -> MultiAnalysisSession | None:
    """
    Get multi-analysis session by session_id.

    Args:
        session_id: Unique session identifier

    Returns:
        MultiAnalysisSession | None: Session object or None if not found
    """
    session_maker = get_session_maker()
    async with session_maker() as session:
        try:
            stmt = select(MultiAnalysisSession).where(
                MultiAnalysisSession.session_id == session_id
            )
            return await session.scalar(stmt)
        except SQLAlchemyError as e:
            logger.error("Database error getting multi_analysis_session: %s", e)
            raise
