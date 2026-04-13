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


def _validate_upload_content_type(file: UploadFile) -> None:
    if file.content_type not in ("application/pdf", "application/octet-stream"):
        raise HTTPException(status_code=400, detail="PDF file expected")


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


def _close_temp_file_quietly(temp_file) -> None:
    if temp_file is None:
        return
    try:
        temp_file.close()
    except Exception:
        logger.debug("Failed to close temporary file", exc_info=True)


def _analysis_runtime_status(analysis) -> str:
    if is_analysis_cancellation_pending(analysis):
        return "cancelling"
    return analysis.status


def _task_storage_dir() -> str | None:
    if app_settings.task_runtime != "celery":
        return None
    return ensure_directory(app_settings.task_storage_dir)


async def _read_upload_header(file: UploadFile) -> bytes:
    first_chunk = await asyncio.to_thread(file.file.read, MAGIC_HEADER_SIZE)
    if not first_chunk:
        raise HTTPException(status_code=400, detail="Empty file")
    if not _validate_pdf_file(first_chunk):
        raise HTTPException(status_code=400, detail="Invalid PDF file format")
    return first_chunk


def _create_upload_temp_file():
    return tempfile.NamedTemporaryFile(
        delete=False,
        suffix=".pdf",
        dir=_task_storage_dir(),
    )


async def _write_upload_chunks(
    file: UploadFile, temp_file, *, first_chunk: bytes
) -> str:
    temp_file.write(first_chunk)
    total_size = len(first_chunk)
    chunk_size = 8192

    while True:
        chunk = await asyncio.to_thread(file.file.read, chunk_size)
        if not chunk:
            break

        total_size += len(chunk)
        if total_size > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=400,
                detail=f"File too large. Maximum size is {MAX_FILE_SIZE // (1024 * 1024)} MB",
            )
        temp_file.write(chunk)

    temp_file.flush()
    return temp_file.name


async def _save_uploaded_pdf(file: UploadFile) -> str:
    first_chunk = await _read_upload_header(file)
    temp_file = _create_upload_temp_file()

    try:
        return await _write_upload_chunks(file, temp_file, first_chunk=first_chunk)
    except Exception:
        await _cleanup_temp_file(temp_file.name)
        raise
    finally:
        _close_temp_file_quietly(temp_file)


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
