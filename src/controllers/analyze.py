import asyncio
import io
import json
import logging
import os
from typing import BinaryIO

import pdfplumber
from fastapi import HTTPException

from src.core.ai_service import ai_service
from src.core.constants import MAX_PDF_PAGES, AI_TIMEOUT

logger = logging.getLogger(__name__)


def _extract_metrics_with_regex(text: str) -> dict[str, float | None]:
    """
    Extract financial metrics from text using regex patterns.
    
    Fallback method when table extraction fails.
    
    Args:
        text: PDF text content
        
    Returns:
        Dictionary with metric keys and extracted values
    """
    import re
    
    def _parse_russian_number(raw: str) -> float | None:
        """Parse numbers like '1 234 567,89' or '1234567.89' or '(123)'."""
        if not raw:
            return None
        negative = bool(re.search(r"\(.*\d.*\)", raw))
        cleaned = raw.replace("\u00a0", " ").strip()
        cleaned = cleaned.replace(",", ".")
        cleaned = re.sub(r"[^0-9.\-\s]", "", cleaned)
        cleaned = cleaned.replace(" ", "")
        try:
            val = (
                float(cleaned)
                if cleaned and cleaned not in ("", "-", ".")
                else None
            )
            if val is not None and negative:
                return -abs(val)
            return val
        except ValueError:
            return None
    
    num_group = r"(\d[\d\s,\.]*\d|\d)"
    
    patterns = {
        "revenue": [
            r"Выручка от реализации\s*\|\s*" + num_group,
            r"Выручка\s*\|\s*" + num_group,
            r"Выручка от реализации[^\d]{0,80}" + num_group,
            r"Выручка[^\d]{0,60}" + num_group,
            r"Доходы от реализации\s*\|\s*" + num_group,
            r"Совокупный доход\s*\|\s*" + num_group,
            # Формат Магнита: "Выручка" в одной строке, значение в следующей
            r"выручка.*?(\d[\d\s,\.]*\d)",
        ],
        "net_profit": [
            r"Чистая прибыль\s*\|\s*" + num_group,
            r"Чистая прибыль[^\d]{0,60}" + num_group,
            r"Прибыль после налогообложения\s*\|\s*" + num_group,
            r"Нераспределенная прибыль\s*\|\s*" + num_group,
            r"чистая прибыль.*?(\d[\d\s,\.]*\d)",
        ],
        "total_assets": [
            r"Итого активов\s*\|\s*" + num_group,
            r"Итого активов[^\d]{0,60}" + num_group,
            r"БАЛАНС\s*\|\s*" + num_group,
            r"БАЛАНС[^\d]{0,60}" + num_group,
            r"актив[аыо].*?(\d[\d\s,\.]*\d)",
        ],
        "equity": [
            r"Итого капитала\s*\|\s*" + num_group,
            r"Итого капитала[^\d]{0,60}" + num_group,
            r"Собственный капитал\s*\|\s*" + num_group,
            r"Капитал и резервы\s*\|\s*" + num_group,
            r"Итого по разделу III\s*\|\s*" + num_group,
            r"капитал[ауоы].*?(\d[\d\s,\.]*\d)",
        ],
        "liabilities": [
            r"Итого обязательств\s*\|\s*" + num_group,
            r"Итого обязательств[^\d]{0,60}" + num_group,
            r"Итого долгосрочных обязательств\s*\|\s*" + num_group,
            r"Итого краткосрочных обязательств\s*\|\s*" + num_group,
            r"обязательств[ауы].*?(\d[\d\s,\.]*\d)",
        ],
        "current_assets": [
            r"Итого оборотных активов\s*\|\s*" + num_group,
            r"Итого оборотных активов[^\d]{0,60}" + num_group,
            r"Оборотные активы\s*\|\s*" + num_group,
            r"Итого по разделу II\s*\|\s*" + num_group,
            r"оборотн[ыыхи].*?(\d[\d\s,\.]*\d)",
        ],
        "short_term_liabilities": [
            r"Итого краткосрочных обязательств\s*\|\s*" + num_group,
            r"Итого краткосрочных обязательств[^\d]{0,80}" + num_group,
            r"Краткосрочные обязательства\s*\|\s*" + num_group,
            r"Итого по разделу V\s*\|\s*" + num_group,
            r"краткосрочн[ыыхи].*?(\d[\d\s,\.]*\d)",
        ],
        "accounts_receivable": [
            r"Дебиторская задолженность\s*\|\s*" + num_group,
            r"Дебиторская задолженность[^\d]{0,60}" + num_group,
            r"задолженност[ьи].*?(\d[\d\s,\.]*\d)",
        ],
        "inventory": [
            r"Запасы\s*\|\s*" + num_group,
            r"Запасы[^\d]{0,60}" + num_group,
            r"Товарно-материальные ценности\s*\|\s*" + num_group,
            r"запас[аыов].*?(\d[\d\s,\.]*\d)",
        ],
        "cash_and_equivalents": [
            r"Денежные средства\s*\|\s*" + num_group,
            r"Денежные средства[^\d]{0,60}" + num_group,
            r"Наличные\s*\|\s*" + num_group,
            r"денежн[ыыхи].*?(\d[\d\s,\.]*\d)",
        ],
        "ebitda": [
            r"EBITDA\s*\|\s*" + num_group,
            r"EBITDA[^\d]{0,60}" + num_group,
            r"ebitda.*?(\d[\d\s,\.]*\d)",
        ],
        "ebit": [
            r"EBIT\s*\|\s*" + num_group,
            r"EBIT[^\d]{0,60}" + num_group,
            r"Операционная прибыль\s*\|\s*" + num_group,
            r"операционн[аыя].*?(\d[\d\s,\.]*\d)",
        ],
        "interest_expense": [
            r"Процентные расходы\s*\|\s*" + num_group,
            r"Процентные расходы[^\d]{0,60}" + num_group,
            r"процентн[ыыхи].*?(\d[\d\s,\.]*\d)",
        ],
        "cost_of_goods_sold": [
            r"Себестоимость продаж\s*\|\s*" + num_group,
            r"Себестоимость продаж[^\d]{0,80}" + num_group,
            r"Себестоимость реализованной продукции\s*\|\s*" + num_group,
            r"себестоимост[ьи].*?(\d[\d\s,\.]*\d)",
        ],
        "average_inventory": [
            r"Средний запас\s*\|\s*" + num_group,
            r"Средний запас[^\d]{0,60}" + num_group,
            r"средн.*?запас[аы].*?(\d[\d\s,\.]*\d)",
        ],
    }
    
    metrics: dict[str, float | None] = {}
    text_lower = text.lower()
    
    for field, pattern_list in patterns.items():
        for pattern in pattern_list:
            match = re.search(pattern, text_lower, re.IGNORECASE)
            if match:
                value = _parse_russian_number(match.group(1))
                if value is not None and value > 0:
                    metrics[field] = value
                    break
    
    return metrics


def _extract_json_from_response(text: str) -> str:
    """Extract JSON from AI response that may contain markdown code blocks."""
    import re

    # Try to find JSON inside ```json ... ``` blocks
    json_block_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if json_block_match:
        return json_block_match.group(1).strip()

    # Try to find JSON inside ``` ... ``` blocks
    code_block_match = re.search(r"```\s*(\{.*?\})\s*```", text, re.DOTALL)
    if code_block_match:
        return code_block_match.group(1).strip()

    # Try to find raw JSON object in the text
    json_match = re.search(r"(\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\})", text, re.DOTALL)
    if json_match:
        return json_match.group(1).strip()

    # Return the original text as-is
    return text.strip()


def _read_pdf_file(file: io.BytesIO) -> list[dict]:
    """
    Read PDF file and extract table data.

    Args:
        file: BytesIO instance with PDF content

    Returns:
        list[dict]: List of page data with extracted tables
    """
    file_data = []

    file.seek(0)
    file_path = None

    try:
        # Create a temporary file to store PDF content
        import tempfile

        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(file.read())
            file_path = tmp.name

        from src.analysis import pdf_extractor

        tables = pdf_extractor.extract_tables(file_path)

        # Extract text from PDF
        text = ""
        try:
            with pdfplumber.open(file_path) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text() or ""
                    text += page_text + "\n"
        except Exception as e:
            logger.warning("Could not extract text: %s", e)

        # Combine tables and text
        file_data.append(
            {
                "tables": tables,
                "text": text[:5000],  # Limit text length
            }
        )

        logger.info(
            "Extracted %d tables from PDF, text length: %d", len(tables), len(text)
        )

    finally:
        if file_path and os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception:
                pass

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

        # Check page limit to prevent DoS attacks
        if len(file_content) > MAX_PDF_PAGES:
            raise HTTPException(
                status_code=400,
                detail=f"PDF has too many pages. Maximum is {MAX_PDF_PAGES} pages.",
            )
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

        # Call the AI service with the prepared prompt
        try:
            res = await ai_service.invoke(
                input={"tool_input": prompt, "intermediate_steps": []},
                timeout=AI_TIMEOUT,
                use_retry=True,
            )
            if res is not None:
                logger.info(
                    "Successfully received AI response for pages %d-%d",
                    page_idx + 1,
                    end_idx,
                )
                try:
                    # Try to extract JSON from the response (handle markdown code blocks)
                    json_str = _extract_json_from_response(res)
                    result = json.loads(json_str)
                    all_results.append(result)
                except json.JSONDecodeError as json_exc:
                    logger.error(
                        "Failed to parse AI response as JSON for pages %d-%d: %s. Response: %s",
                        page_idx + 1,
                        end_idx,
                        json_exc,
                        res[:200] if res else "None",
                    )
                    # Skip this batch and continue with others
                    continue
        except asyncio.TimeoutError:
            logger.error("AI request timeout for pages %d-%d", page_idx + 1, end_idx)
            raise HTTPException(status_code=504, detail="AI service timeout")
        except Exception as e:
            logger.exception(
                "AI processing failed for pages %d-%d: %s", page_idx + 1, end_idx, e
            )
            raise HTTPException(status_code=500, detail="AI processing failed")

    # Combine results from all pages
    if all_results:
        return all_results[0] if len(all_results) == 1 else {"pages": all_results}

    # If no AI results, try to calculate basic ratios from extracted data
    try:
        from src.analysis.ratios import calculate_ratios
        from src.analysis.scoring import calculate_integral_score
        from src.analysis.pdf_extractor import parse_financial_statements

        metrics = {}
        if file_content and len(file_content) > 0:
            # Collect all tables and text across pages
            all_tables = []
            all_text = ""
            for page_data in file_content:
                all_tables.extend(page_data.get("tables", []))
                all_text += page_data.get("text", "") + "\n"

            # Use the full extraction pipeline (keyword matching + regex)
            extracted = parse_financial_statements(all_tables, all_text)
            metrics = {k: v for k, v in extracted.items() if v is not None}

            # If we're missing critical metrics, use regex fallback
            critical_missing = not metrics.get("revenue") or not metrics.get("total_assets")
            if (
                not metrics
                or len([v for v in metrics.values() if v is not None]) < 3
                or critical_missing
            ):
                regex_metrics = _extract_metrics_with_regex(all_text)
                # Merge: regex metrics only for missing keys
                for key, value in regex_metrics.items():
                    if value is not None and metrics.get(key) is None:
                        metrics[key] = value

        if metrics:
            ratios = calculate_ratios(metrics)
            raw_score = calculate_integral_score(ratios)

            from src.tasks import _translate_ratios, _build_score_payload

            # Ensure metrics has all required fields
            default_metrics = {
                "revenue": None,
                "net_profit": None,
                "total_assets": None,
                "equity": None,
                "liabilities": None,
                "current_assets": None,
                "short_term_liabilities": None,
                "accounts_receivable": None,
            }
            final_metrics = {**default_metrics, **{k: v for k, v in metrics.items() if k in default_metrics}}

            ratios_en = _translate_ratios(ratios)
            score_payload = _build_score_payload(raw_score, ratios_en)

            # Build proper AnalysisData response
            return {
                "scanned": False,
                "text": file_content[0].get("text", "") if file_content else "",
                "tables": file_content[0].get("tables", []) if file_content else [],
                "metrics": final_metrics,
                "ratios": ratios_en,
                "score": score_payload,
            }

    except Exception as e:
        logger.warning("Could not calculate ratios: %s", e)

    # Return default AnalysisData when calculation fails
    return {
        "scanned": False,
        "text": "",
        "tables": [],
        "metrics": {
            "revenue": None,
            "net_profit": None,
            "total_assets": None,
            "equity": None,
            "liabilities": None,
            "current_assets": None,
            "short_term_liabilities": None,
            "accounts_receivable": None,
        },
        "ratios": {
            "current_ratio": None,
            "equity_ratio": None,
            "roa": None,
            "roe": None,
            "debt_to_revenue": None,
        },
        "score": {
            "score": 0.0,
            "risk_level": "medium",
            "factors": [],
            "normalized_scores": {
                "current_ratio": None,
                "equity_ratio": None,
                "roa": None,
                "roe": None,
                "debt_to_revenue": None,
            },
        },
    }
