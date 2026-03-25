"""
Router for multi-period analysis endpoints.
Feature: neofin-competition-release
Requirements: 2.5, 2.9, 2.10, 2.11
"""
from __future__ import annotations

import logging
import tempfile
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile

from src.core.auth import get_api_key
from src.db.crud import create_multi_session, get_multi_session
from src.models.schemas import (
    MultiAnalysisAcceptedResponse,
    MultiAnalysisCompletedResponse,
    MultiAnalysisProcessingResponse,
    MultiAnalysisProgress,
    PeriodInput,
)
from src.tasks import process_multi_analysis

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/multi-analysis", tags=["multi-analysis"])


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
    for file, label in zip(files, periods):
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
        content = await file.read()
        tmp.write(content)
        tmp.close()
        period_inputs.append(PeriodInput(period_label=label, file_path=tmp.name))

    session_id = str(uuid4())
    await create_multi_session(session_id)
    background_tasks.add_task(process_multi_analysis, session_id, period_inputs)
    return MultiAnalysisAcceptedResponse(session_id=session_id, status="processing")


@router.get(
    "/{session_id}",
    response_model=MultiAnalysisProcessingResponse | MultiAnalysisCompletedResponse,
)
async def get_multi_analysis_status(
    session_id: str,
    _api_key: str = Depends(get_api_key),
) -> MultiAnalysisProcessingResponse | MultiAnalysisCompletedResponse:
    """Return current status of a multi-period analysis session."""
    session = await get_multi_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    if session.status == "completed":
        result = session.result or {}
        return MultiAnalysisCompletedResponse(
            session_id=session_id,
            status="completed",
            periods=result.get("periods", []),
        )

    if session.status == "failed":
        raise HTTPException(status_code=422, detail="Session processing failed")

    progress_raw = session.progress or {}
    return MultiAnalysisProcessingResponse(
        session_id=session_id,
        status="processing",
        progress=MultiAnalysisProgress(
            completed=progress_raw.get("completed", 0),
            total=progress_raw.get("total", 0),
        ),
    )
