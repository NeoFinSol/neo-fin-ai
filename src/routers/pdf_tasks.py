import asyncio
import logging
import os
import uuid
from typing import Annotated

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    Form,
    HTTPException,
    Request,
    UploadFile,
)
from sqlalchemy.exc import SQLAlchemyError

from src.core.ai_service import ai_service
from src.core.auth import get_api_key
from src.core.task_queue import dispatch_pdf_task
from src.db.crud import (
    create_analysis,
    get_analysis,
    is_analysis_cancellation_pending,
    update_analysis,
)
from src.exceptions import DatabaseError, TaskRuntimeError
from src.models.settings import app_settings
from src.tasks import process_pdf, request_analysis_cancellation
from src.utils.file_utils import ensure_directory
from src.utils.masking import mask_analysis_data
from src.utils.upload_validation import (
    save_uploaded_pdf,
    validate_pdf_magic,
    validate_upload_content_type,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["pdf"])


def _validate_pdf_file(content: bytes) -> bool:
    """Validate PDF file by checking magic header."""
    return validate_pdf_magic(content)


def _validate_upload_content_type(file: UploadFile) -> None:
    validate_upload_content_type(file)


async def _cleanup_temp_file(file_path: str) -> None:
    """Safely remove a temporary file without raising on missing file."""
    try:
        if file_path and os.path.exists(file_path):
            await asyncio.to_thread(os.remove, file_path)
            logger.debug("Cleaned up temporary file: %s", file_path)
    except FileNotFoundError:
        logger.debug("Temporary file already deleted: %s", file_path)
    except Exception as exc:
        logger.warning("Failed to delete temporary file %s: %s", file_path, exc)


def _analysis_runtime_status(analysis) -> str:
    if is_analysis_cancellation_pending(analysis):
        return "cancelling"
    return analysis.status


def _task_storage_dir() -> str | None:
    if app_settings.task_runtime != "celery":
        return None
    return ensure_directory(app_settings.task_storage_dir)


async def _save_uploaded_pdf(file: UploadFile) -> str:
    """Save uploaded PDF via shared upload_validation helper."""
    return await save_uploaded_pdf(file, storage_dir=_task_storage_dir())


def _resolve_requested_provider(ai_provider: str | None) -> str | None:
    try:
        requested_provider = ai_service.normalize_requested_provider(ai_provider)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    if requested_provider and requested_provider not in ai_service.available_providers:
        raise HTTPException(
            status_code=400,
            detail=f"AI provider '{requested_provider}' is not available",
        )
    return requested_provider


async def _create_upload_analysis_record(task_id: str, filename: str | None) -> None:
    try:
        await create_analysis(task_id, "processing", {"filename": filename})
    except SQLAlchemyError as exc:
        logger.exception("Failed to create analysis record: %s", exc)
        raise DatabaseError("Database operation failed") from exc
    except Exception as exc:
        logger.exception("Failed to create analysis record: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to create analysis record")


def _parse_debug_trace_flag(debug_trace: str) -> bool:
    return debug_trace.strip().lower() == "true"


async def _dispatch_upload_task(
    background_tasks: BackgroundTasks,
    *,
    task_id: str,
    file_path: str,
    requested_provider: str | None,
    debug_trace: bool,
) -> None:
    await dispatch_pdf_task(
        background_tasks,
        task_id=task_id,
        file_path=file_path,
        background_callable=process_pdf,
        ai_provider=requested_provider,
        debug_trace=debug_trace,
    )


@router.post("/upload")
async def upload_pdf(
    file: UploadFile,
    background_tasks: BackgroundTasks,
    ai_provider: Annotated[str | None, Form()] = None,
    debug_trace: Annotated[str, Form()] = "false",
    api_key: str = Depends(get_api_key),
    request: Request = None,  # keyword-only, not used directly (rate limiting via middleware)
) -> dict[str, str]:
    _validate_upload_content_type(file)
    filename = getattr(file, "filename", None)

    try:
        tmp_path = await _save_uploaded_pdf(file)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Failed to save uploaded file: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to save uploaded file")

    task_id = str(uuid.uuid4())
    try:
        requested_provider = _resolve_requested_provider(ai_provider)
        await _create_upload_analysis_record(task_id, filename)
        await _dispatch_upload_task(
            background_tasks,
            task_id=task_id,
            file_path=tmp_path,
            requested_provider=requested_provider,
            debug_trace=_parse_debug_trace_flag(debug_trace),
        )
    except TaskRuntimeError:
        await _cleanup_temp_file(tmp_path)
        await update_analysis(task_id, "failed", {"error": "Task dispatch failed"})
        raise
    except Exception:
        await _cleanup_temp_file(tmp_path)
        raise

    return {"task_id": task_id}


@router.get("/result/{task_id}")
async def get_result(
    task_id: str,
    api_key: str = Depends(get_api_key),
    request: Request = None,  # keyword-only, not used directly (rate limiting via middleware)
):
    try:
        analysis = await get_analysis(task_id)
    except SQLAlchemyError as exc:
        logger.error("Failed to load result for task %s: %s", task_id, exc)
        raise DatabaseError("Database operation failed") from exc
    if analysis is None:
        raise HTTPException(status_code=404, detail="Task not found")
    result = (
        analysis.result if analysis.result and isinstance(analysis.result, dict) else {}
    )
    demo_mode = os.getenv("DEMO_MODE", "0") == "1"
    result = mask_analysis_data(result, demo_mode)
    payload = {"status": _analysis_runtime_status(analysis)}
    payload.update(result)
    return payload


@router.delete("/cancel/{task_id}")
async def cancel_analysis(
    task_id: str,
    api_key: str = Depends(get_api_key),
):
    """Cancel an in-progress analysis task."""
    try:
        analysis = await get_analysis(task_id)
    except SQLAlchemyError as exc:
        logger.error("Failed to load task %s for cancellation: %s", task_id, exc)
        raise DatabaseError("Database operation failed") from exc
    if analysis is None:
        raise HTTPException(status_code=404, detail="Task not found")
    if analysis.status not in ("processing", "uploading"):
        return {"status": analysis.status, "message": "Task already finished"}
    await request_analysis_cancellation(task_id)
    return {"status": "cancelling", "task_id": task_id}
