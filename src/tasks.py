import asyncio
import logging
import os

import PyPDF2

from src.analysis import pdf_extractor
from src.analysis.nlp_analysis import analyze_narrative
from src.analysis.ratios import calculate_ratios
from src.analysis.scoring import calculate_integral_score
from src.db.crud import create_analysis, update_analysis

logger = logging.getLogger(__name__)


def _extract_text_from_pdf(pdf_path: str) -> str:
    reader = PyPDF2.PdfReader(pdf_path)
    texts: list[str] = []
    for page_index, page in enumerate(reader.pages, start=1):
        try:
            texts.append(page.extract_text() or "")
        except Exception as exc:
            logger.warning("Failed to extract text from page %s: %s", page_index, exc)
    return "\n".join(texts).strip()


async def process_pdf(task_id: str, file_path: str) -> None:
    existing = await update_analysis(task_id, "processing", None)
    if existing is None:
        await create_analysis(task_id, "processing", None)

    try:
        scanned = await asyncio.to_thread(pdf_extractor.is_scanned_pdf, file_path)
        if scanned:
            text = await asyncio.to_thread(pdf_extractor.extract_text_from_scanned, file_path)
        else:
            text = await asyncio.to_thread(_extract_text_from_pdf, file_path)

        narrative = None
        # if text and len(text) > 500:
        #     narrative = await analyze_narrative(text)

        tables = await asyncio.to_thread(pdf_extractor.extract_tables, file_path)
        metrics = await asyncio.to_thread(pdf_extractor.parse_financial_statements, tables, text)
        ratios = await asyncio.to_thread(calculate_ratios, metrics)
        score = await asyncio.to_thread(calculate_integral_score, ratios)

        await update_analysis(
            task_id,
            "completed",
            {
                "data": {
                    "scanned": scanned,
                    "text": text,
                    "tables": tables,
                    "metrics": metrics,
                    "ratios": ratios,
                    "score": score,
                    "narrative": narrative,
                }
            },
        )
    except Exception as exc:
        logger.exception("Failed to process PDF task %s: %s", task_id, exc)
        await update_analysis(task_id, "failed", {"error": str(exc)})
    finally:
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
        except Exception as exc:
            logger.warning("Failed to удалить временный файл %s: %s", file_path, exc)
