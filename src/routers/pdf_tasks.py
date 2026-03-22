import logging
import tempfile
import uuid

from fastapi import APIRouter, BackgroundTasks, HTTPException, UploadFile

from src.db.crud import create_analysis, get_analysis
from src.tasks import process_pdf

logger = logging.getLogger(__name__)

# PDF magic numbers: %PDF-
PDF_MAGIC_HEADER = b"%PDF-"
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB

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

    try:
        content = await file.read()
        
        if not content:
            raise HTTPException(status_code=400, detail="Empty file")
        
        if len(content) > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=400, 
                detail=f"File too large. Maximum size is {MAX_FILE_SIZE // (1024 * 1024)} MB"
            )
        
        if not _validate_pdf_file(content):
            raise HTTPException(status_code=400, detail="Invalid PDF file format")
        
        suffix = ".pdf"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_file:
            tmp_file.write(content)
            tmp_path = tmp_file.name
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Failed to save uploaded file: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to save uploaded file")

    task_id = str(uuid.uuid4())
    try:
        await create_analysis(task_id, "processing", None)
    except Exception as exc:
        logger.exception("Failed to create analysis record: %s", exc)
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
