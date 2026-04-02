"""
Router for multi-period analysis endpoints.
Feature: neofin-competition-release
Requirements: 2.5, 2.9, 2.10, 2.11
"""

from __future__ import annotations

import logging
import os
import tempfile
from uuid import uuid4

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
)
from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError

from src.core.auth import get_api_key
from src.core.task_queue import dispatch_multi_analysis_task
from src.db.crud import (
    create_multi_session,
    get_multi_session,
    is_multi_session_cancellation_pending,
    update_multi_session,
)
from src.exceptions import DatabaseError, TaskRuntimeError
from src.models.schemas import (
    MultiAnalysisAcceptedResponse,
    MultiAnalysisCancelledResponse,
    MultiAnalysisCompletedResponse,
    MultiAnalysisProcessingResponse,
    MultiAnalysisProgress,
    PeriodInput,
)
from src.models.settings import app_settings
from src.tasks import process_multi_analysis, request_multi_session_cancellation
from src.utils.file_utils import ensure_directory

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/multi-analysis", tags=["multi-analysis"])


def _cleanup_temp_files(paths: list[str]) -> None:
    """Best-effort cleanup for temporary PDF files before background handoff."""
    for path in paths:
        try:
            os.remove(path)
        except FileNotFoundError:
            continue
        except OSError as exc:
            logger.warning("Failed to remove temp file %s: %s", path, exc)


def _multi_session_runtime_status(session) -> str:
    if is_multi_session_cancellation_pending(session):
        return "cancelling"
    return session.status


def _task_storage_dir() -> str | None:
    if app_settings.task_runtime != "celery":
        return None
    return ensure_directory(app_settings.task_storage_dir)


@router.post("", status_code=202, response_model=MultiAnalysisAcceptedResponse)
async def start_multi_analysis(
    background_tasks: BackgroundTasks,
    files: list[UploadFile] = File(...),
    periods: list[str] = Form(...),
    _api_key: str = Depends(get_api_key),
) -> MultiAnalysisAcceptedResponse:
    """Accept multi-period analysis request and start background processing."""
    if len(files) != len(periods):
        raise HTTPException(
            status_code=422,
            detail="Количество файлов должно совпадать с количеством меток периодов",
        )
    if len(files) > 5:
        raise HTTPException(status_code=422, detail="Максимум 5 периодов")

    period_inputs: list[PeriodInput] = []
    temp_paths: list[str] = []
    handed_off = False
    session_id = ""
    try:
        for file, label in zip(files, periods):
            tmp = tempfile.NamedTemporaryFile(
                delete=False,
                suffix=".pdf",
                dir=_task_storage_dir(),
            )
            temp_paths.append(tmp.name)
            try:
                content = await file.read()
                tmp.write(content)
            finally:
                tmp.close()

            period_inputs.append(PeriodInput(period_label=label, file_path=tmp.name))

        session_id = str(uuid4())
        await create_multi_session(session_id)
        periods_payload = [period.model_dump() for period in period_inputs]
        await dispatch_multi_analysis_task(
            background_tasks,
            session_id=session_id,
            periods_payload=periods_payload,
            background_callable=process_multi_analysis,
        )
        handed_off = True
        return MultiAnalysisAcceptedResponse(session_id=session_id, status="processing")
    except ValidationError as exc:
        logger.warning("Validation failed for multi-analysis input: %s", exc.errors())
        raise HTTPException(
            status_code=422,
            detail="Invalid multi-analysis request",
        ) from exc
    except SQLAlchemyError as exc:
        logger.error("Failed to create multi-analysis session %s: %s", session_id, exc)
        raise DatabaseError("Database operation failed") from exc
    except TaskRuntimeError:
        if session_id:
            await update_multi_session(
                session_id,
                status="failed",
                progress={"completed": 0, "total": len(period_inputs)},
                result={"error": "Task dispatch failed"},
            )
        raise
    finally:
        if not handed_off:
            _cleanup_temp_files(temp_paths)


@router.get(
    "/{session_id}",
    response_model=(
        MultiAnalysisProcessingResponse
        | MultiAnalysisCompletedResponse
        | MultiAnalysisCancelledResponse
    ),
)
async def get_multi_analysis_status(
    session_id: str,
    _api_key: str = Depends(get_api_key),
) -> (
    MultiAnalysisProcessingResponse
    | MultiAnalysisCompletedResponse
    | MultiAnalysisCancelledResponse
):
    """Return current status of a multi-period analysis session."""
    try:
        session = await get_multi_session(session_id)
    except SQLAlchemyError as exc:
        logger.error("Failed to load multi-analysis session %s: %s", session_id, exc)
        raise DatabaseError("Database operation failed") from exc
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    if session.status == "completed":
        result = session.result or {}
        return MultiAnalysisCompletedResponse(
            session_id=session_id,
            status="completed",
            periods=result.get("periods", []),
        )

    if session.status == "cancelled":
        progress_raw = session.progress or {}
        return MultiAnalysisCancelledResponse(
            session_id=session_id,
            status="cancelled",
            progress=MultiAnalysisProgress(
                completed=progress_raw.get("completed", 0),
                total=progress_raw.get("total", 0),
            ),
        )

    if session.status == "failed":
        raise HTTPException(status_code=422, detail="Session processing failed")

    progress_raw = session.progress or {}
    return MultiAnalysisProcessingResponse(
        session_id=session_id,
        status=_multi_session_runtime_status(session),
        progress=MultiAnalysisProgress(
            completed=progress_raw.get("completed", 0),
            total=progress_raw.get("total", 0),
        ),
    )


@router.delete("/{session_id}")
async def cancel_multi_analysis(
    session_id: str,
    _api_key: str = Depends(get_api_key),
):
    """Request cancellation for an in-progress multi-period analysis session."""
    try:
        session = await get_multi_session(session_id)
    except SQLAlchemyError as exc:
        logger.error(
            "Failed to load multi-analysis session %s for cancellation: %s",
            session_id,
            exc,
        )
        raise DatabaseError("Database operation failed") from exc

    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    if session.status != "processing":
        return {"status": session.status, "message": "Session already finished"}

    await request_multi_session_cancellation(session_id)
    return {"status": "cancelling", "session_id": session_id}
