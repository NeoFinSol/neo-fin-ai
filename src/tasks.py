import asyncio
import io
import logging
import os
import re
import time
from pathlib import Path

import PyPDF2

from src.analysis import pdf_extractor
from src.analysis.pdf_extractor import ExtractionMetadata
from src.analysis.ratios import calculate_ratios
from src.analysis.scoring import calculate_integral_score
from src.db.crud import create_analysis, update_analysis, update_multi_session, AnalysisAlreadyExistsError
from src.utils.logging_config import get_logger, metrics
from sqlalchemy.exc import SQLAlchemyError

logger = get_logger(__name__)

_RAW_THRESHOLD = os.getenv("CONFIDENCE_THRESHOLD", "0.5")
try:
    CONFIDENCE_THRESHOLD: float = float(_RAW_THRESHOLD)
    if not (0.0 <= CONFIDENCE_THRESHOLD <= 1.0):
        logger.warning(
            "CONFIDENCE_THRESHOLD=%s out of [0.0, 1.0], using default 0.5", _RAW_THRESHOLD
        )
        CONFIDENCE_THRESHOLD = 0.5
except ValueError:
    logger.warning(
        "CONFIDENCE_THRESHOLD=%r is not a valid float, using default 0.5", _RAW_THRESHOLD
    )
    CONFIDENCE_THRESHOLD = 0.5


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


def _apply_confidence_filter(
    metadata: dict[str, ExtractionMetadata],
    threshold: float | None = None,
) -> tuple[dict[str, float | None], dict[str, dict]]:
    """
    Filter extraction metadata by confidence threshold.

    Args:
        metadata: Per-metric extraction results from parse_financial_statements_with_metadata.
        threshold: Minimum confidence to keep a value. Defaults to CONFIDENCE_THRESHOLD.
                   confidence >= threshold → keep value; confidence < threshold → None.
                   value=None is always preserved as None regardless of confidence.

    Returns:
        filtered_metrics: All keys preserved; low-confidence values replaced with None.
        extraction_metadata_payload: {key: {"confidence": float, "source": str}} for all keys.
    """
    if threshold is None:
        threshold = CONFIDENCE_THRESHOLD

    filtered_metrics: dict[str, float | None] = {}
    extraction_metadata_payload: dict[str, dict] = {}

    for key, meta in metadata.items():
        if meta.value is None or meta.confidence < threshold:
            filtered_metrics[key] = None
        else:
            filtered_metrics[key] = meta.value

        extraction_metadata_payload[key] = {
            "confidence": meta.confidence,
            "source": meta.source,
        }

    return filtered_metrics, extraction_metadata_payload


# Маппинг русских ключей ratios → snake_case English для frontend
# Порядок соответствует группам: ликвидность, рентабельность, устойчивость, активность
RATIO_KEY_MAP = {
    # Liquidity
    "Коэффициент текущей ликвидности": "current_ratio",
    "Коэффициент быстрой ликвидности": "quick_ratio",
    "Коэффициент абсолютной ликвидности": "absolute_liquidity_ratio",
    # Profitability
    "Рентабельность активов (ROA)": "roa",
    "Рентабельность собственного капитала (ROE)": "roe",
    "Рентабельность продаж (ROS)": "ros",
    "EBITDA маржа": "ebitda_margin",
    # Financial stability
    "Коэффициент автономии": "equity_ratio",
    "Финансовый рычаг": "financial_leverage",
    "Покрытие процентов": "interest_coverage",
    # Business activity
    "Оборачиваемость активов": "asset_turnover",
    "Оборачиваемость запасов": "inventory_turnover",
    "Оборачиваемость дебиторской задолженности": "receivables_turnover",
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
        normalized_scores: {en_key: float | null, ...} }
    """
    details = raw_score.get("details", {})  # normalized 0-1 values per ratio (RU keys)

    # Human-readable names for frontend display
    FRIENDLY_NAMES: dict[str, str] = {
        "Коэффициент текущей ликвидности": "Текущая ликвидность",
        "Коэффициент быстрой ликвидности": "Быстрая ликвидность",
        "Коэффициент абсолютной ликвидности": "Абсолютная ликвидность",
        "Рентабельность активов (ROA)": "Рентабельность активов",
        "Рентабельность собственного капитала (ROE)": "Рентабельность капитала",
        "Рентабельность продаж (ROS)": "Рентабельность продаж",
        "EBITDA маржа": "EBITDA маржа",
        "Коэффициент автономии": "Финансовая независимость",
        "Финансовый рычаг": "Финансовый рычаг",
        "Покрытие процентов": "Покрытие процентов",
        "Оборачиваемость активов": "Оборачиваемость активов",
        "Оборачиваемость запасов": "Оборачиваемость запасов",
        "Оборачиваемость дебиторской задолженности": "Оборачиваемость ДЗ",
    }

    factors = []
    normalized_scores: dict[str, float | None] = {
        en_key: None for en_key in RATIO_KEY_MAP.values()
    }

    for ru_name, norm_val in details.items():
        en_key = RATIO_KEY_MAP.get(ru_name)
        if not en_key:
            continue

        normalized_scores[en_key] = norm_val
        actual_val = ratios_en.get(en_key)

        # Determine impact based on normalized score
        if norm_val is None:
            impact = "neutral"
        elif norm_val >= 0.65:
            impact = "positive"
        elif norm_val >= 0.35:
            impact = "neutral"
        else:
            impact = "negative"

        friendly_name = FRIENDLY_NAMES.get(ru_name, ru_name)

        if actual_val is None:
            actual_str = "—"
        elif isinstance(actual_val, (int, float)):
            actual_str = f"{actual_val:.2f}"
        else:
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
    
    Logs all key events with task_id correlation and timing.
    Records metrics for success/failure/ai failures.
    
    Args:
        task_id: Unique task identifier
        file_path: Path to temporary PDF file
    """
    start_time = time.monotonic()
    metrics.record_task_start()
    
    # Create logger with task context
    task_logger = get_logger(__name__, task_id=task_id)
    
    try:
        task_logger.info("PDF processing started")
        
        # Ensure analysis record exists (upsert pattern)
        db_available = await _ensure_analysis_exists(task_id)
        if not db_available:
            task_logger.critical("Database unavailable - aborting processing")
            metrics.record_task_failure()
            return

        # --- Extraction Phase ---
        extract_start = time.monotonic()
        scanned = await asyncio.to_thread(pdf_extractor.is_scanned_pdf, file_path)
        if scanned:
            text = await asyncio.to_thread(pdf_extractor.extract_text_from_scanned, file_path)
        else:
            text = await asyncio.to_thread(_extract_text_from_pdf, file_path)

        tables = await asyncio.to_thread(pdf_extractor.extract_tables, file_path)
        metadata = await asyncio.to_thread(
            pdf_extractor.parse_financial_statements_with_metadata, tables, text
        )
        metrics_filtered, extraction_metadata_payload = _apply_confidence_filter(metadata)
        
        # Fallback: if critical metrics are missing, use regex extraction from text
        critical_missing = not metrics_filtered.get("revenue") or not metrics_filtered.get("total_assets")
        if critical_missing and text:
            task_logger.warning("Critical metrics missing, using regex fallback")
            from src.controllers.analyze import _extract_metrics_with_regex
            regex_metrics = _extract_metrics_with_regex(text)
            # Merge: regex metrics only for missing keys
            for key, value in regex_metrics.items():
                if value is not None and metrics_filtered.get(key) is None:
                    metrics_filtered[key] = value
                    task_logger.info(f"Filled {key} from regex fallback: {value}")
        
        extract_duration = (time.monotonic() - extract_start) * 1000
        task_logger.info(f"PDF extraction completed", extra={"duration_ms": extract_duration})

        # --- Ratios & Scoring Phase ---
        ratios_start = time.monotonic()
        ratios_ru = await asyncio.to_thread(calculate_ratios, metrics_filtered)
        ratios_duration = (time.monotonic() - ratios_start) * 1000
        task_logger.info(f"Ratios calculation completed", extra={"duration_ms": ratios_duration})
        
        scoring_start = time.monotonic()
        raw_score = await asyncio.to_thread(calculate_integral_score, ratios_ru)
        scoring_duration = (time.monotonic() - scoring_start) * 1000
        task_logger.info(f"Scoring completed", extra={"duration_ms": scoring_duration})

        # Translate for frontend compatibility
        ratios_en = _translate_ratios(ratios_ru)
        score_payload = _build_score_payload(raw_score, ratios_en)

        # --- NLP Analysis Phase ---
        nlp_result = {"risks": [], "key_factors": [], "recommendations": []}
        if text and len(text) > 500:
            nlp_start = time.monotonic()
            try:
                from src.analysis.nlp_analysis import analyze_narrative
                nlp_result = await asyncio.wait_for(
                    analyze_narrative(text),
                    timeout=60.0
                )
                nlp_duration = (time.monotonic() - nlp_start) * 1000
                task_logger.info(f"NLP analysis completed", extra={"duration_ms": nlp_duration})
            except ImportError:
                task_logger.debug("NLP analysis module not available")
            except asyncio.TimeoutError:
                task_logger.warning("NLP analysis timed out")
                metrics.record_ai_failure()
            except Exception as nlp_exc:
                task_logger.warning(f"NLP analysis failed: {nlp_exc}", exc_info=True)
                metrics.record_ai_failure()

        # --- Recommendations Phase ---
        try:
            from src.analysis.recommendations import generate_recommendations
            rec_start = time.monotonic()
            recommendations = await asyncio.wait_for(
                generate_recommendations(metrics_filtered, ratios_en, nlp_result),
                timeout=65.0
            )
            rec_duration = (time.monotonic() - rec_start) * 1000
            nlp_result["recommendations"] = recommendations
            task_logger.info(f"Generated {len(recommendations)} recommendations", extra={"duration_ms": rec_duration})
        except ImportError:
            task_logger.debug("Recommendations module not available")
        except asyncio.TimeoutError:
            task_logger.warning("Recommendations generation timed out")
            metrics.record_ai_failure()
        except Exception as rec_exc:
            task_logger.warning(f"Recommendations generation failed: {rec_exc}", exc_info=True)
            metrics.record_ai_failure()

        # --- Update Database ---
        total_duration = (time.monotonic() - start_time) * 1000
        await update_analysis(
            task_id,
            "completed",
            {
                "data": {
                    "scanned": scanned,
                    "text": text[:5000],  # Limit text size stored in DB
                    "tables": tables[:10],  # Limit tables stored
                    "metrics": metrics_filtered,
                    "ratios": ratios_en,   # English keys for frontend
                    "score": score_payload,  # Full ScoreData shape
                    "nlp": nlp_result,
                    "extraction_metadata": extraction_metadata_payload,
                }
            },
        )
        
        task_logger.info(f"PDF processing completed successfully", extra={"duration_ms": total_duration})
        metrics.record_task_success(total_duration)
        
    except Exception as exc:
        total_duration = (time.monotonic() - start_time) * 1000
        task_logger.exception(f"PDF processing failed: {exc}", extra={"duration_ms": total_duration})
        metrics.record_task_failure()
        
        try:
            await update_analysis(task_id, "failed", {"error": str(exc)})
        except Exception as update_exc:
            task_logger.critical(f"Failed to update task status to 'failed': {update_exc}")
    finally:
        # Clean up temporary file with safer deletion pattern
        _cleanup_temp_file(file_path)


# ---------------------------------------------------------------------------
# Multi-Period Analysis (neofin-competition-release)
# Requirements: 2.4
# ---------------------------------------------------------------------------

_MULTI_ANALYSIS_TIMEOUT = 600  # seconds


def parse_period_label(label: str) -> tuple[int, int]:
    """
    Parse period label into a sortable (year, quarter) tuple.

    Formats:
        "YYYY"      → (year, 0)
        "Qn/YYYY"   → (year, n)
        invalid     → (9999, 0)
    """
    label = label.strip()

    m = re.fullmatch(r"Q([1-4])/(\d{4})", label, re.IGNORECASE)
    if m:
        return int(m.group(2)), int(m.group(1))

    m = re.fullmatch(r"(\d{4})", label)
    if m:
        return int(m.group(1)), 0

    return 9999, 0


def sort_periods_chronologically(periods: list[dict]) -> list[dict]:
    """Sort period result dicts by parse_period_label on 'period_label' key."""
    return sorted(periods, key=lambda p: parse_period_label(p.get("period_label", "")))


async def _process_single_period(period_label: str, file_path: str) -> dict:
    """
    Run the full financial analysis pipeline for one period's PDF.

    Reuses existing pipeline functions: extractor → confidence filter → ratios → scoring.
    NLP/recommendations are skipped for multi-period to keep latency bounded.

    Args:
        period_label: Human-readable period identifier (e.g. "2023", "Q1/2023")
        file_path: Path to the PDF file for this period

    Returns:
        dict with keys: period_label, ratios, score, risk_level, extraction_metadata
        On failure: {period_label, error: "processing_failed"}
    """
    try:
        scanned = await asyncio.to_thread(pdf_extractor.is_scanned_pdf, file_path)
        if scanned:
            text = await asyncio.to_thread(pdf_extractor.extract_text_from_scanned, file_path)
        else:
            text = await asyncio.to_thread(_extract_text_from_pdf, file_path)

        tables = await asyncio.to_thread(pdf_extractor.extract_tables, file_path)
        metadata = await asyncio.to_thread(
            pdf_extractor.parse_financial_statements_with_metadata, tables, text
        )
        metrics, extraction_metadata_payload = _apply_confidence_filter(metadata)
        ratios_ru = await asyncio.to_thread(calculate_ratios, metrics)
        raw_score = await asyncio.to_thread(calculate_integral_score, ratios_ru)

        ratios_en = _translate_ratios(ratios_ru)
        score_payload = _build_score_payload(raw_score, ratios_en)

        return {
            "period_label": period_label,
            "ratios": ratios_en,
            "score": score_payload.get("score", None),
            "risk_level": score_payload.get("risk_level", None),
            "extraction_metadata": extraction_metadata_payload,
        }
    except Exception as exc:
        logger.warning(
            "Period '%s' processing failed: %s", period_label, exc, exc_info=True
        )
        return {"period_label": period_label, "error": "processing_failed"}


async def process_multi_analysis(
    session_id: str,
    periods: list,  # list[PeriodInput] — avoid circular import; duck-typed
) -> None:
    """
    Orchestrate multi-period financial analysis.
    
    Logs all key events with session_id correlation.
    Records metrics for success/failure.
    
    Args:
        session_id: Unique multi-analysis session identifier
        periods: List of PeriodInput objects with .period_label and .file_path attributes
    """
    start_time = time.monotonic()
    total = len(periods)
    
    # Create logger with session context
    session_logger = get_logger(__name__, session_id=session_id)
    session_logger.info(f"Multi-analysis session started: {total} periods")

    await update_multi_session(
        session_id,
        status="processing",
        progress={"completed": 0, "total": total},
    )

    collected: list[dict] = []
    failed_count = 0

    for idx, period in enumerate(periods):
        if time.monotonic() - start_time > _MULTI_ANALYSIS_TIMEOUT:
            session_logger.error(
                f"Session exceeded timeout ({_MULTI_ANALYSIS_TIMEOUT}s) after {idx}/{total} periods"
            )
            await update_multi_session(
                session_id,
                status="failed",
                progress={"completed": idx, "total": total},
            )
            metrics.record_task_failure()
            return

        period_label: str = period.period_label
        file_path: str = period.file_path
        
        period_logger = get_logger(__name__, session_id=session_id, task_id=period_label)
        period_logger.info(f"Processing period {idx + 1}/{total}")

        result = await _process_single_period(period_label, file_path)
        
        if "error" in result:
            failed_count += 1
            period_logger.warning(f"Period failed: {result['error']}")
        else:
            period_logger.info(f"Period completed successfully")
        
        collected.append(result)

        await update_multi_session(
            session_id,
            progress={"completed": idx + 1, "total": total},
        )

    sorted_results = sort_periods_chronologically(collected)
    
    total_duration = (time.monotonic() - start_time) * 1000
    
    # Determine final status
    if failed_count == total:
        final_status = "failed"
        session_logger.error(f"Session failed: all {total} periods failed", extra={"duration_ms": total_duration})
        metrics.record_task_failure()
    elif failed_count > 0:
        final_status = "completed_with_errors"
        session_logger.warning(
            f"Session completed with errors: {failed_count}/{total} periods failed",
            extra={"duration_ms": total_duration}
        )
        metrics.record_task_success(total_duration)
    else:
        final_status = "completed"
        session_logger.info(f"Session completed successfully", extra={"duration_ms": total_duration})
        metrics.record_task_success(total_duration)

    await update_multi_session(
        session_id,
        status=final_status,
        progress={"completed": total, "total": total},
        result={"periods": sorted_results},
    )
