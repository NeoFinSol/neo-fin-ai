import asyncio
import io
import logging
import os
from pathlib import Path

import PyPDF2

from src.analysis import pdf_extractor
from src.analysis.ratios import calculate_ratios
from src.analysis.scoring import calculate_integral_score
from src.db.crud import create_analysis, update_analysis, AnalysisAlreadyExistsError
from sqlalchemy.exc import SQLAlchemyError

logger = logging.getLogger(__name__)


async def _ensure_analysis_exists(task_id: str) -> bool:
    """
    Ensure Analysis record exists for task_id.
    
    Uses upsert pattern to handle race conditions.
    
    Args:
        task_id: Unique task identifier
        
    Returns:
        bool: True if record exists/created, False if DB unavailable
    """
    existing = await update_analysis(task_id, "processing", None)
    if existing is not None:
        return True
    
    try:
        await create_analysis(task_id, "processing", None)
        return True
    except AnalysisAlreadyExistsError:
        # Race condition - another process created it
        result = await update_analysis(task_id, "processing", None)
        if result is None:
            logger.critical("Failed to ensure analysis exists for task %s", task_id)
            return False
        return True
    except SQLAlchemyError as e:
        logger.exception("DB error ensuring analysis for task %s", task_id)
        return False


def _cleanup_temp_file(file_path: str | os.PathLike | io.IOBase | None) -> None:
    """
    Safely cleanup temporary file or file-like object.
    
    Supports:
    - str: File path
    - os.PathLike: Path object
    - io.IOBase: file-like objects (BytesIO, StringIO, open files)
    - None: No-op
    
    Args:
        file_path: Path to file or file-like object
    """
    if file_path is None:
        return
    
    # 1. File-like objects (BytesIO, StringIO, open files)
    if hasattr(file_path, 'close') and callable(getattr(file_path, 'close')):
        try:
            file_path.close()
            logger.debug("Closed file-like object: %s", type(file_path).__name__)
        except Exception as exc:
            logger.warning("Failed to close file-like object: %s", exc)
        return
    
    # 2. Path as str/Path/PathLike
    from pathlib import Path, PurePath
    try:
        # Path() accepts str, Path, PathLike — but not bytes without decoding
        if isinstance(file_path, (str, PurePath)):
            path = Path(file_path)
        else:
            path = Path(str(file_path))
        
        if path.is_file():
            path.unlink(missing_ok=True)
            logger.debug("Deleted temporary file: %s", path)
    except (TypeError, OSError, ValueError) as exc:
        logger.warning("Failed to cleanup path %r: %s", file_path, type(exc).__name__)

# Маппинг русских ключей ratios → camelCase English для frontend
RATIO_KEY_MAP = {
    "Коэффициент текущей ликвидности": "current_ratio",
    "Коэффициент автономии": "equity_ratio",
    "Рентабельность активов (ROA)": "roa",
    "Рентабельность собственного капитала (ROE)": "roe",
    "Долговая нагрузка": "debt_to_revenue",
}

# Маппинг Russian metric keys → English for frontend FinancialMetrics
METRIC_KEY_MAP = {
    "revenue": "revenue",
    "net_profit": "net_profit",
    "total_assets": "total_assets",
    "equity": "equity",
    "liabilities": "liabilities",
    "current_assets": "current_assets",
    "short_term_liabilities": "short_term_liabilities",
    "accounts_receivable": "accounts_receivable",
}


def _translate_ratios(ratios: dict) -> dict:
    """
    Convert Russian ratio keys to camelCase English for frontend.
    
    Args:
        ratios: Dictionary with Russian keys from calculate_ratios
        
    Returns:
        dict: Dictionary with English keys
        
    Side Effects:
        Logs warning for unmapped keys (for monitoring)
    """
    result = {}
    unknown_keys = []
    
    for k, v in ratios.items():
        en_key = RATIO_KEY_MAP.get(k)
        if en_key:
            result[en_key] = v
        else:
            # Keep unmapped keys but log them for monitoring
            unknown_keys.append(k)
            result[k] = v
    
    if unknown_keys:
        logger.warning("Unmapped ratio keys (frontend may break): %s", unknown_keys)
    
    return result


def _build_score_payload(raw_score: dict, ratios_en: dict) -> dict:
    """
    Transform backend score structure to match frontend ScoreData interface.

    Frontend expects:
      { score, risk_level, factors: [{name, description, impact}],
        normalized_scores: {current_ratio, equity_ratio, roa, roe, debt_to_revenue} }
    """
    details = raw_score.get("details", {})  # normalized 0-1 values per ratio

    # Build factors list from details
    FACTOR_DESCRIPTIONS = {
        "Коэффициент текущей ликвидности": ("Ликвидность", "current_ratio"),
        "Коэффициент автономии": ("Финансовая устойчивость", "equity_ratio"),
        "Рентабельность активов (ROA)": ("Рентабельность активов", "roa"),
        "Рентабельность собственного капитала (ROE)": ("Рентабельность капитала", "roe"),
        "Долговая нагрузка": ("Долговая нагрузка", "debt_to_revenue"),
    }

    THRESHOLDS = {
        "current_ratio": (1.5, True),
        "equity_ratio": (0.4, True),
        "roa": (0.05, True),
        "roe": (0.1, True),
        "debt_to_revenue": (1.5, False),  # lower is better
    }

    factors = []
    normalized_scores = {
        k: None for k in ["current_ratio", "equity_ratio", "roa", "roe", "debt_to_revenue"]
    }

    for ru_name, norm_val in details.items():
        en_key = RATIO_KEY_MAP.get(ru_name)
        if not en_key:
            continue

        normalized_scores[en_key] = norm_val
        threshold, higher_is_better = THRESHOLDS.get(en_key, (0.5, True))
        actual_val = ratios_en.get(en_key)

        if norm_val is None or actual_val is None:
            impact = "neutral"
        elif higher_is_better:
            impact = "positive" if norm_val >= 0.6 else ("neutral" if norm_val >= 0.3 else "negative")
        else:
            # debt_to_revenue: high norm means low debt (good)
            impact = "positive" if norm_val >= 0.6 else ("neutral" if norm_val >= 0.3 else "negative")

        friendly_name, _ = FACTOR_DESCRIPTIONS.get(ru_name, (ru_name, en_key))
        # Safe numeric formatting with type check
        if actual_val is None:
            actual_str = "—"
        elif isinstance(actual_val, (int, float)):
            actual_str = f"{actual_val:.2f}"
        else:
            # Handle non-numeric values (strings, etc.)
            try:
                actual_str = f"{float(actual_val):.2f}"
            except (TypeError, ValueError):
                actual_str = str(actual_val)

        factors.append({
            "name": friendly_name,
            "description": f"Значение: {actual_str}",
            "impact": impact,
        })

    return {
        "score": raw_score.get("score", 0),
        "risk_level": _translate_risk_level(raw_score.get("risk_level", "высокий")),
        "factors": factors,
        "normalized_scores": normalized_scores,
    }


def _translate_risk_level(ru: str) -> str:
    """Translate Russian risk level to English."""
    return {"низкий": "low", "средний": "medium", "высокий": "high"}.get(ru, "high")


def _extract_text_from_pdf(pdf_path: str) -> str:
    """
    Extract text from PDF using PyPDF2.

    Args:
        pdf_path: Path to PDF file

    Returns:
        str: Extracted text content
    """
    reader = PyPDF2.PdfReader(pdf_path)
    texts: list[str] = []
    for page_index, page in enumerate(reader.pages, start=1):
        try:
            texts.append(page.extract_text() or "")
        except Exception as exc:
            logger.warning("Failed to extract text from page %s: %s", page_index, exc)
    return "\n".join(texts).strip()


async def process_pdf(task_id: str, file_path: str) -> None:
    """
    Process PDF file and update analysis results.

    Args:
        task_id: Unique task identifier
        file_path: Path to temporary PDF file
    """
    try:
        # Ensure analysis record exists (upsert pattern)
        db_available = await _ensure_analysis_exists(task_id)
        if not db_available:
            logger.critical("Database unavailable for task %s - aborting processing", task_id)
            return

        # Process PDF
        scanned = await asyncio.to_thread(pdf_extractor.is_scanned_pdf, file_path)
        if scanned:
            text = await asyncio.to_thread(pdf_extractor.extract_text_from_scanned, file_path)
        else:
            text = await asyncio.to_thread(_extract_text_from_pdf, file_path)

        # Extract tables and calculate metrics
        tables = await asyncio.to_thread(pdf_extractor.extract_tables, file_path)
        metrics = await asyncio.to_thread(pdf_extractor.parse_financial_statements, tables, text)
        ratios_ru = await asyncio.to_thread(calculate_ratios, metrics)
        raw_score = await asyncio.to_thread(calculate_integral_score, ratios_ru)

        # Translate for frontend compatibility
        ratios_en = _translate_ratios(ratios_ru)
        score_payload = _build_score_payload(raw_score, ratios_en)

        # NLP analysis — graceful degradation if AI not configured
        nlp_result = {"risks": [], "key_factors": [], "recommendations": []}
        if text and len(text) > 500:
            try:
                from src.analysis.nlp_analysis import analyze_narrative
                nlp_result = await asyncio.wait_for(
                    analyze_narrative(text),
                    timeout=60.0  # Don't block forever if AI is slow
                )
            except ImportError:
                logger.debug("NLP analysis module not available for task %s", task_id)
            except asyncio.TimeoutError:
                logger.warning("NLP analysis timed out for task %s", task_id)
            except Exception as nlp_exc:
                logger.warning("NLP analysis failed for task %s: %s", task_id, nlp_exc)

        # Generate data-driven recommendations with references to metrics
        try:
            from src.analysis.recommendations import generate_recommendations
            recommendations = await asyncio.wait_for(
                generate_recommendations(metrics, ratios_en, nlp_result),
                timeout=65.0  # Allow up to 65 seconds for AI generation
            )
            nlp_result["recommendations"] = recommendations
            logger.debug("Generated %d recommendations with data references for task %s",
                        len(recommendations), task_id)
        except ImportError:
            logger.debug("Recommendations module not available for task %s", task_id)
        except asyncio.TimeoutError:
            logger.warning("Recommendations generation timed out for task %s", task_id)
        except Exception as rec_exc:
            logger.warning("Recommendations generation failed for task %s: %s", task_id, rec_exc)

        await update_analysis(
            task_id,
            "completed",
            {
                "data": {
                    "scanned": scanned,
                    "text": text[:5000],  # Limit text size stored in DB
                    "tables": tables[:10],  # Limit tables stored
                    "metrics": metrics,
                    "ratios": ratios_en,   # English keys for frontend
                    "score": score_payload,  # Full ScoreData shape
                    "nlp": nlp_result,
                }
            },
        )
    except Exception as exc:
        logger.exception("Failed to process PDF task %s: %s", task_id, exc)
        try:
            await update_analysis(task_id, "failed", {"error": str(exc)})
        except Exception as update_exc:
            logger.critical("Failed to update task %s status to 'failed': %s", task_id, update_exc)
    finally:
        # Clean up temporary file with safer deletion pattern
        _cleanup_temp_file(file_path)
