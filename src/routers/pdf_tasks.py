import logging
import os
import tempfile
import uuid

from fastapi import APIRouter, BackgroundTasks, HTTPException, UploadFile

from src.core.constants import PDF_MAGIC_HEADER, MAX_FILE_SIZE, MAGIC_HEADER_SIZE
from src.db.crud import create_analysis, get_analysis
from src.tasks import process_pdf

logger = logging.getLogger(__name__)

router = APIRouter(tags=["pdf"])


def _validate_pdf_file(content: bytes) -> bool:
    """Validate PDF file by checking magic header."""
    if not content or len(content) < 5:
        return False
    return content[:5] == PDF_MAGIC_HEADER


@router.post("/upload")
async def upload_pdf(file: UploadFile, background_tasks: BackgroundTasks):
    if file.content_type not in ("application/pdf", "application/octet-stream"):
        raise HTTPException(status_code=400, detail="PDF file expected")

    temp_file = None
    tmp_path = None
    
    try:
        # Read first chunk to check header and size
        header_size = MAGIC_HEADER_SIZE
        first_chunk = await file.file.read(header_size)
        
        if not first_chunk:
            raise HTTPException(status_code=400, detail="Empty file")
        
        # Validate magic header before reading full file
        if not _validate_pdf_file(first_chunk):
            raise HTTPException(status_code=400, detail="Invalid PDF file format")
        
        # Create temporary file and write in chunks
        suffix = ".pdf"
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
        temp_file.write(first_chunk)
        
        # Read remaining content in chunks
        chunk_size = 8192  # 8KB
        total_size = len(first_chunk)
        
        while True:
            chunk = await file.file.read(chunk_size)
            if not chunk:
                break
            
            total_size += len(chunk)
            
            # Check size limit during read
            if total_size > MAX_FILE_SIZE:
                temp_file.close()
                if os.path.exists(temp_file.name):
                    os.remove(temp_file.name)
                raise HTTPException(
                    status_code=400,
                    detail=f"File too large. Maximum size is {MAX_FILE_SIZE // (1024 * 1024)} MB"
                )
            
            temp_file.write(chunk)
        
        temp_file.flush()
        temp_file.close()
        tmp_path = temp_file.name
        
    except HTTPException:
        if temp_file:
            try:
                temp_file.close()
                if tmp_path and os.path.exists(tmp_path):
                    os.remove(tmp_path)
            except Exception:
                pass
        raise
    except Exception as exc:
        logger.exception("Failed to save uploaded file: %s", exc)
        if temp_file:
            try:
                temp_file.close()
                if tmp_path and os.path.exists(tmp_path):
                    os.remove(tmp_path)
            except Exception:
                pass
        raise HTTPException(status_code=500, detail="Failed to save uploaded file")

    task_id = str(uuid.uuid4())
    try:
        await create_analysis(task_id, "processing", None)
    except Exception as exc:
        logger.exception("Failed to create analysis record: %s", exc)
        if temp_file:
            try:
                temp_file.close()
                if tmp_path and os.path.exists(tmp_path):
                    os.remove(tmp_path)
            except Exception:
                pass
        raise HTTPException(status_code=500, detail="Failed to create analysis record")
    
    background_tasks.add_task(process_pdf, task_id, tmp_path)
    return {"task_id": task_id}


@router.get("/result/{task_id}")
async def get_result(task_id: str):
    analysis = await get_analysis(task_id)
    if analysis is None:
        raise HTTPException(status_code=404, detail="Task not found")
    payload = {"status": analysis.status}
    if analysis.result and isinstance(analysis.result, dict):
        payload.update(analysis.result)
    return payload
