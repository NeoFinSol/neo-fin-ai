"""
Upload validation utilities shared across upload routers.

Centralises PDF magic-header check, content-type validation and
size-limited chunked file saving so that no router imports from another.
"""

from __future__ import annotations

import asyncio
import logging
import os
import tempfile

from fastapi import HTTPException, UploadFile

from src.core.constants import (
    FILE_CHUNK_SIZE,
    MAGIC_HEADER_SIZE,
    MAX_FILE_SIZE,
    PDF_MAGIC_HEADER,
)

logger = logging.getLogger(__name__)

_ALLOWED_UPLOAD_CONTENT_TYPES = ("application/pdf", "application/octet-stream")


def validate_pdf_magic(content: bytes) -> bool:
    """Return True when *content* starts with the PDF magic header."""
    if not content or len(content) < 5:
        return False
    return content[:5] == PDF_MAGIC_HEADER


def validate_upload_content_type(file: UploadFile) -> None:
    """Raise HTTP 400 when the uploaded file has an unexpected MIME type."""
    if file.content_type not in _ALLOWED_UPLOAD_CONTENT_TYPES:
        raise HTTPException(status_code=400, detail="PDF file expected")


def _close_quietly(temp_file) -> None:
    if temp_file is None:
        return
    try:
        temp_file.close()
    except Exception:
        logger.debug("Failed to close temporary file", exc_info=True)


async def _read_and_validate_header(file: UploadFile) -> bytes:
    first_chunk = await asyncio.to_thread(file.file.read, MAGIC_HEADER_SIZE)
    if not first_chunk:
        raise HTTPException(status_code=400, detail="Empty file")
    if not validate_pdf_magic(first_chunk):
        raise HTTPException(status_code=400, detail="Invalid PDF file format")
    return first_chunk


async def _write_chunks(file: UploadFile, tmp, *, first_chunk: bytes) -> str:
    """Write *first_chunk* then stream the rest of *file* into *tmp*."""
    tmp.write(first_chunk)
    total_size = len(first_chunk)

    while True:
        chunk = await asyncio.to_thread(file.file.read, FILE_CHUNK_SIZE)
        if not chunk:
            break
        total_size += len(chunk)
        if total_size > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"File too large. Maximum size is "
                    f"{MAX_FILE_SIZE // (1024 * 1024)} MB"
                ),
            )
        tmp.write(chunk)

    tmp.flush()
    return tmp.name


async def save_uploaded_pdf(
    file: UploadFile,
    *,
    storage_dir: str | None = None,
) -> str:
    """Validate and save an uploaded PDF to a temporary file.

    Performs content-type check, magic-header validation and enforces the
    global MAX_FILE_SIZE limit via chunked streaming.

    Args:
        file: The uploaded file from a FastAPI endpoint.
        storage_dir: Optional directory for the temp file (e.g. Celery shared
            storage).  Defaults to the OS temp directory.

    Returns:
        Absolute path of the saved temporary file.

    Raises:
        HTTPException 400: on empty file, invalid header or oversized file.
    """
    first_chunk = await _read_and_validate_header(file)
    tmp = tempfile.NamedTemporaryFile(
        delete=False,
        suffix=".pdf",
        dir=storage_dir,
    )
    tmp_path = tmp.name
    try:
        result = await _write_chunks(file, tmp, first_chunk=first_chunk)
        return result
    except Exception:
        _close_quietly(tmp)
        # Best-effort removal so callers don't need to track partial files
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except OSError:
            logger.warning("Failed to remove partial temp file: %s", tmp_path)
        raise
    finally:
        _close_quietly(tmp)
