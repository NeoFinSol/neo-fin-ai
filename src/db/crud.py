from __future__ import annotations

import logging
from datetime import datetime, timezone
from sqlalchemy import delete, func, or_, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from src.db.database import get_session_maker
from src.db.models import Analysis, MultiAnalysisSession, RISK_LEVELS

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


_TERMINAL_ANALYSIS_STATUSES = ("completed", "failed", "cancelled")
_PROCESSING_ANALYSIS_STATUSES = ("uploading", "processing")
_TERMINAL_MULTI_SESSION_STATUSES = ("completed", "failed")


def _coerce_float(value) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _coerce_bool(value) -> bool | None:
    if isinstance(value, bool):
        return value
    return None


def _derive_analysis_summary(status: str, result: dict | None) -> dict[str, object | None]:
    if not isinstance(result, dict):
        return {
            "filename": None,
            "score": None,
            "risk_level": None,
            "scanned": None,
            "confidence_score": None,
            "completed_at": None,
            "error_message": None,
        }

    data = result.get("data") if isinstance(result.get("data"), dict) else {}
    score_block = data.get("score") if isinstance(data.get("score"), dict) else {}
    risk_level = score_block.get("risk_level")
    if risk_level not in RISK_LEVELS:
        risk_level = None

    score = _coerce_float(score_block.get("score"))
    if score is not None and not (0.0 <= score <= 100.0):
        score = None

    confidence_score = _coerce_float(score_block.get("confidence_score"))
    if confidence_score is not None and not (0.0 <= confidence_score <= 1.0):
        confidence_score = None

    filename = result.get("filename")
    if not isinstance(filename, str):
        filename = None

    error_message = result.get("error")
    if not isinstance(error_message, str):
        error_message = None

    return {
        "filename": filename,
        "score": score,
        "risk_level": risk_level,
        "scanned": _coerce_bool(data.get("scanned")),
        "confidence_score": confidence_score,
        "completed_at": datetime.now(timezone.utc) if status == "completed" else None,
        "error_message": error_message,
    }


def _apply_analysis_summary_fields(
    analysis: Analysis,
    status: str,
    result: dict | None,
) -> None:
    summary = _derive_analysis_summary(status, result)
    analysis.status = status
    analysis.result = result
    analysis.filename = summary["filename"]
    analysis.score = summary["score"]
    analysis.risk_level = summary["risk_level"]
    analysis.scanned = summary["scanned"]
    analysis.confidence_score = summary["confidence_score"]
    analysis.completed_at = summary["completed_at"]
    analysis.error_message = summary["error_message"]


def _build_analysis_cleanup_filters(
    *,
    terminal_before: datetime | None = None,
    stale_processing_before: datetime | None = None,
) -> list[object]:
    filters = []
    if terminal_before is not None:
        filters.append(
            (Analysis.status.in_(_TERMINAL_ANALYSIS_STATUSES))
            & (Analysis.created_at < terminal_before)
        )
    if stale_processing_before is not None:
        filters.append(
            (Analysis.status.in_(_PROCESSING_ANALYSIS_STATUSES))
            & (Analysis.created_at < stale_processing_before)
        )
    return filters


def _build_multi_session_cleanup_filters(
    *,
    terminal_before: datetime | None = None,
    stale_processing_before: datetime | None = None,
) -> list[object]:
    filters = []
    if terminal_before is not None:
        filters.append(
            (MultiAnalysisSession.status.in_(_TERMINAL_MULTI_SESSION_STATUSES))
            & (MultiAnalysisSession.updated_at < terminal_before)
        )
    if stale_processing_before is not None:
        filters.append(
            (MultiAnalysisSession.status == "processing")
            & (MultiAnalysisSession.updated_at < stale_processing_before)
        )
    return filters


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
            analysis = Analysis(task_id=task_id)
            _apply_analysis_summary_fields(analysis, status, result)
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

            next_result = existing.result if result is None else result
            _apply_analysis_summary_fields(existing, status, next_result)
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


async def find_analysis_cleanup_candidates(
    *,
    terminal_before: datetime | None = None,
    stale_processing_before: datetime | None = None,
    limit: int = 100,
) -> list[Analysis]:
    """
    Return analyses eligible for maintenance cleanup.

    Only terminal rows older than ``terminal_before`` and/or stuck uploading/processing
    rows older than ``stale_processing_before`` are returned.
    """
    session_maker = get_session_maker()
    async with session_maker() as session:
        try:
            filters = _build_analysis_cleanup_filters(
                terminal_before=terminal_before,
                stale_processing_before=stale_processing_before,
            )
            if not filters:
                return []

            stmt = (
                select(Analysis)
                .where(or_(*filters))
                .order_by(Analysis.created_at.asc())
                .limit(limit)
            )
            result = await session.scalars(stmt)
            return list(result.all())
        except SQLAlchemyError as e:
            logger.error("Database error finding analysis cleanup candidates: %s", e)
            raise


async def cleanup_analyses(
    *,
    terminal_before: datetime | None = None,
    stale_processing_before: datetime | None = None,
    limit: int = 100,
    dry_run: bool = True,
) -> dict[str, object]:
    """
    Delete stale analysis rows in bounded batches.

    Returns counts and task_ids of matching rows. ``dry_run=True`` only reports candidates.
    """
    candidates = await find_analysis_cleanup_candidates(
        terminal_before=terminal_before,
        stale_processing_before=stale_processing_before,
        limit=limit,
    )
    task_ids = [row.task_id for row in candidates]
    if dry_run or not task_ids:
        return {"count": len(task_ids), "task_ids": task_ids, "deleted": False}

    session_maker = get_session_maker()
    async with session_maker() as session:
        try:
            delete_filters = _build_analysis_cleanup_filters(
                terminal_before=terminal_before,
                stale_processing_before=stale_processing_before,
            )
            stmt = delete(Analysis).where(Analysis.task_id.in_(task_ids)).where(
                or_(*delete_filters)
            )
            result = await session.execute(stmt)
            await session.commit()
            deleted_count = result.rowcount or 0
            return {"count": deleted_count, "task_ids": task_ids, "deleted": True}
        except SQLAlchemyError as e:
            await session.rollback()
            logger.error("Database error cleaning analyses: %s", e)
            raise


async def find_multi_session_cleanup_candidates(
    *,
    terminal_before: datetime | None = None,
    stale_processing_before: datetime | None = None,
    limit: int = 100,
) -> list[MultiAnalysisSession]:
    """
    Return multi-analysis sessions eligible for cleanup.
    """
    session_maker = get_session_maker()
    async with session_maker() as session:
        try:
            filters = _build_multi_session_cleanup_filters(
                terminal_before=terminal_before,
                stale_processing_before=stale_processing_before,
            )
            if not filters:
                return []

            stmt = (
                select(MultiAnalysisSession)
                .where(or_(*filters))
                .order_by(MultiAnalysisSession.updated_at.asc())
                .limit(limit)
            )
            result = await session.scalars(stmt)
            return list(result.all())
        except SQLAlchemyError as e:
            logger.error("Database error finding multi-session cleanup candidates: %s", e)
            raise


async def cleanup_multi_sessions(
    *,
    terminal_before: datetime | None = None,
    stale_processing_before: datetime | None = None,
    limit: int = 100,
    dry_run: bool = True,
) -> dict[str, object]:
    """
    Delete stale multi-analysis sessions in bounded batches.
    """
    candidates = await find_multi_session_cleanup_candidates(
        terminal_before=terminal_before,
        stale_processing_before=stale_processing_before,
        limit=limit,
    )
    session_ids = [row.session_id for row in candidates]
    if dry_run or not session_ids:
        return {"count": len(session_ids), "session_ids": session_ids, "deleted": False}

    session_maker = get_session_maker()
    async with session_maker() as session:
        try:
            delete_filters = _build_multi_session_cleanup_filters(
                terminal_before=terminal_before,
                stale_processing_before=stale_processing_before,
            )
            stmt = delete(MultiAnalysisSession).where(
                MultiAnalysisSession.session_id.in_(session_ids)
            ).where(
                or_(*delete_filters)
            )
            result = await session.execute(stmt)
            await session.commit()
            deleted_count = result.rowcount or 0
            return {"count": deleted_count, "session_ids": session_ids, "deleted": True}
        except SQLAlchemyError as e:
            await session.rollback()
            logger.error("Database error cleaning multi-analysis sessions: %s", e)
            raise
