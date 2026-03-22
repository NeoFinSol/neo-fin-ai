import base64
import logging
from io import BytesIO

from fastapi import APIRouter, UploadFile, HTTPException

from src.controllers.analyze import analyze_pdf
from src.models.requests import AnalyzePdfRequest

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/analyze", tags=["system"])


@router.post("/pdf/file")
async def post_analyze_pdf_file(file: UploadFile):
	if file.content_type not in ("application/pdf", "application/octet-stream"):
		raise HTTPException(status_code=400, detail="PDF file expected")
	try:
		return await analyze_pdf(file.file)
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
			raise ValueError("Empty decoded data")
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
