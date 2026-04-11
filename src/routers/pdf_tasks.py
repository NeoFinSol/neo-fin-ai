import asyncio
import logging
import os
import tempfile
import uuid
from pathlib import Path
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
from src.core.constants import MAGIC_HEADER_SIZE, MAX_FILE_SIZE, PDF_MAGIC_HEADER
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

logger = logging.getLogger(__name__)

router = APIRouter(tags=["pdf"])


def _validate_pdf_file(content: bytes) -> bool:
    """Validate PDF file by checking magic header."""
    if not content or len(content) < 5:
        return False
    return content[:5] == PDF_MAGIC_HEADER


async def _cleanup_temp_file(file_path: str) -> None:
    """
    Safely cleanup temporary file.

    Uses asyncio.to_thread for sync file operations to avoid blocking.
    Handles race conditions where file may already be deleted.
    """
    try:
        if file_path and os.path.exists(file_path):
            await asyncio.to_thread(os.remove, file_path)
            logger.debug("Cleaned up temporary file: %s", file_path)
    except FileNotFoundError:
        # File already deleted - this is fine
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


@router.post("/upload")
async def upload_pdf(
    file: UploadFile,
    background_tasks: BackgroundTasks,
    ai_provider: Annotated[str | None, Form()] = None,
    debug_trace: Annotated[str, Form()] = "false",
    api_key: str = Depends(get_api_key),
    request: Request = None,  # keyword-only, not used directly (rate limiting via middleware)
):
    if file.content_type not in ("application/pdf", "application/octet-stream"):
        raise HTTPException(status_code=400, detail="PDF file expected")

    temp_file = None
    tmp_path = None

    try:
        # Read first chunk to check header and size
        header_size = MAGIC_HEADER_SIZE
        first_chunk = await asyncio.to_thread(file.file.read, header_size)

        if not first_chunk:
            raise HTTPException(status_code=400, detail="Empty file")

        # Validate magic header before reading full file
        if not _validate_pdf_file(first_chunk):
            raise HTTPException(status_code=400, detail="Invalid PDF file format")

        # Create temporary file and write in chunks
        suffix = ".pdf"
        # Use delete=False so we can pass the path to background task
        temp_file = tempfile.NamedTemporaryFile(
            delete=False,
            suffix=suffix,
            dir=_task_storage_dir(),
        )
        temp_file.write(first_chunk)

        # Read remaining content in chunks
        chunk_size = 8192  # 8KB
        total_size = len(first_chunk)

        while True:
            chunk = await asyncio.to_thread(file.file.read, chunk_size)
            if not chunk:
                break

            total_size += len(chunk)

            # Check size limit during read
            if total_size > MAX_FILE_SIZE:
                # Close and cleanup - use asyncio.to_thread for safety
                temp_file.close()
                await _cleanup_temp_file(temp_file.name)
                raise HTTPException(
                    status_code=400,
                    detail=f"File too large. Maximum size is {MAX_FILE_SIZE // (1024 * 1024)} MB",
                )

            temp_file.write(chunk)

        temp_file.flush()
        temp_file.close()
        tmp_path = temp_file.name

    except HTTPException:
        # Clean up on HTTP errors
        if temp_file:
            try:
                temp_file.close()
            except Exception:
                # Ignore close errors during cleanup
                pass
        if tmp_path:
            await _cleanup_temp_file(tmp_path)
        raise
    except Exception as exc:
        logger.exception("Failed to save uploaded file: %s", exc)
        # Clean up on general errors
        if temp_file:
            try:
                temp_file.close()
            except Exception:
                # Ignore close errors during cleanup
                pass
        if tmp_path:
            await _cleanup_temp_file(tmp_path)
        raise HTTPException(status_code=500, detail="Failed to save uploaded file")

    try:
        requested_provider = ai_service.normalize_requested_provider(ai_provider)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    if requested_provider and requested_provider not in ai_service.available_providers:
        raise HTTPException(
            status_code=400,
            detail=f"AI provider '{requested_provider}' is not available",
        )

    task_id = str(uuid.uuid4())
    try:
        await create_analysis(task_id, "processing", {"filename": file.filename})
    except SQLAlchemyError as exc:
        logger.exception("Failed to create analysis record: %s", exc)
        # Clean up temp file if DB operation fails
        await _cleanup_temp_file(tmp_path)
        raise DatabaseError("Database operation failed") from exc
    except Exception as exc:
        logger.exception("Failed to create analysis record: %s", exc)
        await _cleanup_temp_file(tmp_path)
        raise HTTPException(status_code=500, detail="Failed to create analysis record")

    try:
        _debug_trace_bool = debug_trace.strip().lower() == "true"
        await dispatch_pdf_task(
            background_tasks,
            task_id=task_id,
            file_path=tmp_path,
            background_callable=process_pdf,
            ai_provider=requested_provider,
            debug_trace=_debug_trace_bool,
        )
    except TaskRuntimeError:
        await _cleanup_temp_file(tmp_path)
        await update_analysis(task_id, "failed", {"error": "Task dispatch failed"})
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
