import base64
from io import BytesIO

from fastapi import APIRouter, UploadFile, HTTPException

from src.controllers.analyze import analyze_pdf
from src.models.requests import AnalyzePdfRequest

router = APIRouter(prefix="/analyze", tags=["system"])


@router.post("/pdf/file")
async def post_analyze_pdf_file(file: UploadFile):
	if file.content_type not in ("application/pdf", "application/octet-stream"):
		raise HTTPException(status_code=400, detail="PDF file expected")
	return await analyze_pdf(file.file)


@router.post("/pdf/base64")
async def post_analyze_pdf_base64(request: AnalyzePdfRequest):
	try:
		decode_bytes: bytes = base64.b64decode(request.file_data)
	except Exception as e:
		raise HTTPException(status_code=400, detail=f"Failed to decode base64: {e}")
	return await analyze_pdf(BytesIO(decode_bytes))
