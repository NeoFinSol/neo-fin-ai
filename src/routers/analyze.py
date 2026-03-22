import base64
import logging
from io import BytesIO

from fastapi import APIRouter, UploadFile, HTTPException

from src.controllers.analyze import analyze_pdf
from src.models.requests import AnalyzePdfRequest

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/analyze", tags=["system"])

PDF_MAGIC_HEADER = b"%PDF-"
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB


def _validate_pdf_content(content: bytes) -> bool:
    """Validate PDF file by checking magic header."""
    if not content or len(content) < 5:
        return False
    return content[:5] == PDF_MAGIC_HEADER


@router.post("/pdf/file")
async def post_analyze_pdf_file(file: UploadFile):
    if file.content_type not in ("application/pdf", "application/octet-stream"):
        raise HTTPException(status_code=400, detail="PDF file expected")
    
    try:
        content = await file.read()
        
        if not content:
            raise HTTPException(status_code=400, detail="Empty file")
        
        if len(content) > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=400,
                detail=f"File too large. Maximum size is {MAX_FILE_SIZE // (1024 * 1024)} MB"
            )
        
        if not _validate_pdf_content(content):
            raise HTTPException(status_code=400, detail="Invalid PDF file format")
        
        return await analyze_pdf(BytesIO(content))
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error processing PDF file: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/pdf/base64")
async def post_analyze_pdf_base64(request: AnalyzePdfRequest):
    try:
        decode_bytes: bytes = base64.b64decode(request.file_data)
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
