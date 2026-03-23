import asyncio
import io
import json
import logging
from typing import BinaryIO

import pdfplumber
from fastapi import HTTPException

from src.core.ai_service import ai_service

logger = logging.getLogger(__name__)


def _read_pdf_file(file: io.BytesIO) -> list[dict]:
    """
    Read PDF file and extract table data.
    
    Args:
        file: BytesIO instance with PDF content
        
    Returns:
        list[dict]: List of page data with extracted tables
    """
    file_data = []

    # Reset file pointer to beginning
    file.seek(0)
    
    try:
        with pdfplumber.open(file) as pdf:
            for page_num, page in enumerate(pdf.pages, start=1):
                tables = page.extract_tables(table_settings={
                    "vertical_strategy": "lines",
                    "horizontal_strategy": "lines",
                    "min_words_vertical": 3,
                    "snap_tolerance": 3
                })

                page_data = {
                    "page": page_num,
                    # "text": page.extract_text(),
                    "tables": []
                }

                for table_idx, table in enumerate(tables):
                    if not table:
                        continue

                    cleaned_rows = [
                        [cell.strip() if cell else "" for cell in row]
                        for row in table
                    ]

                    page_data["tables"].append({
                        "table_index": table_idx,
                        "rows": cleaned_rows
                    })

                file_data.append(page_data)
    except Exception as e:
        logger.exception("Failed to extract tables from PDF: %s", e)
        raise ValueError(f"PDF table extraction failed: {e}") from e

    return file_data


async def analyze_pdf(file: io.BytesIO | BinaryIO):
    """
    Analyze PDF document using AI agent.
    
    Args:
        file: BytesIO or BinaryIO instance with PDF content
        
    Returns:
        dict: Analysis results
        
    Raises:
        HTTPException: If processing fails
    """
    try:
        # Convert BinaryIO to BytesIO if needed
        if isinstance(file, io.BytesIO):
            pdf_file = file
        else:
            # For BinaryIO, we need to read the content and create BytesIO
            content = file.read()
            if not content:
                raise ValueError("Empty file content")
            pdf_file = io.BytesIO(content)

        file_content = _read_pdf_file(pdf_file)
    except ValueError as e:
        logger.exception("Invalid PDF file: %s", e)
        raise HTTPException(status_code=400, detail="Invalid or corrupted PDF file")
    except Exception as e:
        logger.exception("PDF processing failed: %s", e)
        raise HTTPException(status_code=400, detail="PDF processing failed")

    logger.info("Starting AI analysis for %d pages", len(file_content))

    # Iterate pages by step and prepare for AI
    step = 20
    all_results = []
    for page_idx in range(0, len(file_content), step):
        end_idx = min(page_idx + step, len(file_content))
        logger.debug("Processing pages %d-%d", page_idx + 1, end_idx)

        prompt = ""
        for i in range(page_idx, end_idx):
            prompt += f"=== PAGE {i + 1} ===\n"
            prompt += json.dumps(file_content[i]) + "\n"

        # Call the AI agent with the prepared prompt
        try:
            res = await agent.invoke(
                input={
                    "tool_input": prompt,
                    "intermediate_steps": []
                },
                timeout=120
            )
            if res is not None:
                logger.info("Successfully received AI response for pages %d-%d", page_idx + 1, end_idx)
                all_results.append(json.loads(res))
        except asyncio.TimeoutError:
            logger.error("AI request timeout for pages %d-%d", page_idx + 1, end_idx)
            raise HTTPException(status_code=504, detail="AI service timeout")
        except Exception as e:
            logger.exception("AI processing failed for pages %d-%d: %s", page_idx + 1, end_idx, e)
            raise HTTPException(status_code=500, detail="AI processing failed")

    # Combine results from all pages
    if all_results:
        return all_results[0] if len(all_results) == 1 else {"pages": all_results}
    return {}
