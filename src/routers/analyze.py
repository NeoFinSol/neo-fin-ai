import base64
import logging
from io import BytesIO
from tempfile import SpooledTemporaryFile

from fastapi import APIRouter, Depends, Request, UploadFile, HTTPException

from src.controllers.analyze import analyze_pdf
from src.core.auth import get_api_key
from src.core.constants import PDF_MAGIC_HEADER, MAX_FILE_SIZE, MAGIC_HEADER_SIZE
from src.models.requests import AnalyzePdfRequest

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/analyze", tags=["system"])


# Limiter will be accessed via request.app.state.limiter through SlowAPIMiddleware


def _validate_pdf_content(content: bytes) -> bool:
    """Validate PDF file by checking magic header."""
    if not content or len(content) < 5:
        return False
    return content[:5] == PDF_MAGIC_HEADER


def _read_and_validate_stream(file: UploadFile, max_size: int = MAX_FILE_SIZE) -> SpooledTemporaryFile:
    """
    Read uploaded file stream with memory-efficient spooled temporary file.
    
    Args:
        file: UploadedFile instance
        max_size: Maximum file size in bytes
        
    Returns:
        SpooledTemporaryFile: File-like object that spills to disk after threshold
        
    Raises:
        HTTPException: If file is empty, too large, or invalid PDF
    """
    # Create spooled temp file (keeps first 1MB in memory, then spills to disk)
    spooled_file = SpooledTemporaryFile(max_size=1024 * 1024, mode='w+b')
    
    try:
        # Read in chunks to avoid loading entire file into memory
        chunk_size = 8192  # 8KB chunks
        total_size = 0
        header_checked = False
        
        while True:
            chunk = file.file.read(chunk_size)
            if not chunk:
                break
                
            total_size += len(chunk)
            
            # Check size limit
            if total_size > max_size:
                raise HTTPException(
                    status_code=400,
                    detail=f"File too large. Maximum size is {MAX_FILE_SIZE // (1024 * 1024)} MB"
                )
            
            # Check magic header from first chunk
            if not header_checked:
                if not _validate_pdf_content(chunk):
                    raise HTTPException(status_code=400, detail="Invalid PDF file format")
                header_checked = True
            
            spooled_file.write(chunk)
        
        # Check if file is empty
        if total_size == 0:
            raise HTTPException(status_code=400, detail="Empty file")
        
        # Rewind to beginning
        spooled_file.seek(0)
        return spooled_file
        
    except HTTPException:
        spooled_file.close()
        raise
    except Exception as e:
        logger.exception("Error reading file stream: %s", e)
        spooled_file.close()
        raise HTTPException(status_code=500, detail="Failed to read file")


@router.post("/pdf/file")
async def post_analyze_pdf_file(request: Request, file: UploadFile, api_key: str = Depends(get_api_key)):
    if file.content_type not in ("application/pdf", "application/octet-stream"):
        raise HTTPException(status_code=400, detail="PDF file expected")

    spooled_file = None
    try:
        # Read and validate file efficiently
        spooled_file = _read_and_validate_stream(file)

        # Pass spooled file to analyzer
        return await analyze_pdf(spooled_file)

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error processing PDF file: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error")
    finally:
        # Clean up spooled file
        if spooled_file:
            try:
                spooled_file.close()
            except Exception:
                pass


@router.post("/pdf/base64")
async def post_analyze_pdf_base64(request: Request, request_data: AnalyzePdfRequest, api_key: str = Depends(get_api_key)):
    try:
        # Decode base64 in chunks for large files
        decode_bytes: bytes = base64.b64decode(request_data.file_data)
        
        if not decode_bytes:
            raise HTTPException(status_code=400, detail="Empty decoded data")
        
        if len(decode_bytes) > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=400,
                detail=f"File too large. Maximum size is {MAX_FILE_SIZE // (1024 * 1024)} MB"
            )
        
        if not _validate_pdf_content(decode_bytes):
            raise HTTPException(status_code=400, detail="Invalid PDF file format")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.warning("Failed to decode base64: %s", e)
        raise HTTPException(status_code=400, detail=f"Failed to decode base64: {str(e)}")
    
    try:
        return await analyze_pdf(BytesIO(decode_bytes))
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error processing PDF from base64: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error")
