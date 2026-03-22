import logging
import tempfile
import uuid

from fastapi import APIRouter, BackgroundTasks, HTTPException, UploadFile

from src.db.crud import create_analysis, get_analysis
from src.tasks import process_pdf

logger = logging.getLogger(__name__)

router = APIRouter(tags=["pdf"])


@router.post("/upload")
async def upload_pdf(file: UploadFile, background_tasks: BackgroundTasks):
    if file.content_type not in ("application/pdf", "application/octet-stream"):
        raise HTTPException(status_code=400, detail="PDF file expected")

    try:
        suffix = ".pdf"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_file:
            content = await file.read()
            tmp_file.write(content)
            tmp_path = tmp_file.name
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
