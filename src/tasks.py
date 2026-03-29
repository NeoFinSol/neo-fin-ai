import asyncio
import logging
import os
import re
import time
from dataclasses import dataclass

from src.analysis import pdf_extractor
from src.analysis.nlp_analysis import analyze_narrative
from src.analysis.pdf_extractor import (
    extract_metrics_regex,
    apply_confidence_filter,
    extract_text,
    is_scanned_pdf,
    extract_text_from_scanned,
    extract_tables,
    parse_financial_statements_with_metadata,
)

# Alias expected by tests (БАГ 10 — module-level import requirement)
_extract_metrics_with_regex = extract_metrics_regex
from src.analysis.ratios import calculate_ratios, translate_ratios
from src.analysis.recommendations import generate_recommendations
from src.analysis.scoring import (
    apply_data_quality_guardrails,
    calculate_integral_score, 
    build_score_payload
)
from src.core.runtime_events import broadcast_task_event
from src.core.task_queue import revoke_runtime_task
from src.db.crud import (
    AnalysisAlreadyExistsError,
    create_analysis,
    get_analysis,
    is_analysis_cancel_requested,
    is_analysis_cancellation_pending,
    is_multi_session_cancel_requested,
    is_multi_session_cancellation_pending,
    mark_analysis_cancelled,
    mark_multi_session_cancelled,
    request_analysis_cancel,
    request_multi_session_cancel,
    touch_analysis_runtime_heartbeat,
    touch_multi_session_runtime_heartbeat,
    update_analysis,
    update_multi_session,
)
from src.models.settings import app_settings
from src.analysis.llm_extractor import extract_with_llm, is_clean_financial_text
from src.core.ai_service import ai_service
from src.utils.logging_config import get_logger, metrics
from src.utils.file_utils import cleanup_temp_file
from sqlalchemy.exc import SQLAlchemyError
logger = get_logger(__name__)


@dataclass(slots=True)
class RuntimePeriodInput:
    period_label: str
    file_path: str


_CANCELLED_ERROR = "Task cancelled by user"


def _cancelled_payload() -> dict[str, str]:
    return {
        "error": _CANCELLED_ERROR,
        "reason_code": "cancelled_by_request",
    }


async def request_analysis_cancellation(task_id: str):
    """Persist cancellation request and try to revoke runtime execution."""
    record = await request_analysis_cancel(task_id)
    if is_analysis_cancellation_pending(record):
        revoke_runtime_task(task_id)
        logger.info("Analysis task %s marked for cancellation", task_id)
    return record


async def request_multi_session_cancellation(session_id: str):
    """Persist multi-session cancellation request and try to revoke runtime execution."""
    record = await request_multi_session_cancel(session_id)
    if is_multi_session_cancellation_pending(record):
        revoke_runtime_task(session_id)
        logger.info("Multi-analysis session %s marked for cancellation", session_id)
    return record


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
    existing = await get_analysis(task_id)
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
    except SQLAlchemyError:
        logger.exception("DB error ensuring analysis for task %s", task_id)
        return False


async def _finalize_analysis_cancellation(task_id: str, task_logger: logging.Logger) -> None:
    payload = _cancelled_payload()
    await mark_analysis_cancelled(task_id, payload)
    await broadcast_task_event(task_id, {
        "type": "status_update",
        "task_id": task_id,
        "status": "cancelled",
        "error": payload["error"],
    })
    metrics.record_task_failure()
    task_logger.info("Analysis task cancelled")


async def _maybe_cancel_analysis(task_id: str, task_logger: logging.Logger) -> bool:
    if not await is_analysis_cancel_requested(task_id):
        return False
    await _finalize_analysis_cancellation(task_id, task_logger)
    return True








async def process_pdf(task_id: str, file_path: str) -> None:
    """
    Process PDF file and update analysis results.
    
    Orchestrates the full pipeline:
    1. Extraction (text, tables, metrics)
    2. Ratios & Scoring
    3. AI Analysis (NLP, recommendations)
    4. Database Update & WS Notification
    """
    start_time = time.monotonic()
    metrics.record_task_start()
    
    task_logger = get_logger(__name__, task_id=task_id)
    
    try:
        task_logger.info("PDF processing started")
        
        if not await _ensure_analysis_exists(task_id):
            task_logger.critical("Database unavailable - aborting processing")
            metrics.record_task_failure()
            return

        await touch_analysis_runtime_heartbeat(task_id)

        if await _maybe_cancel_analysis(task_id, task_logger):
            return

        await broadcast_task_event(task_id, {
            "type": "status_update",
            "task_id": task_id,
            "status": "extracting",
            "progress": 25,
        })

        # 1. Extraction Phase
        extraction_results = await _run_extraction_phase(file_path, task_logger)
        text = extraction_results["text"]
        metrics_filtered = extraction_results["metrics"]
        metadata_payload = extraction_results["metadata"]
        scanned = extraction_results["scanned"]
        tables = extraction_results["tables"]

        await touch_analysis_runtime_heartbeat(task_id)

        if await _maybe_cancel_analysis(task_id, task_logger):
            return

        await broadcast_task_event(task_id, {
            "type": "status_update",
            "task_id": task_id,
            "status": "scoring",
            "progress": 55,
        })

        # 2. Ratios & Scoring Phase
        scoring_results = await _run_scoring_phase(metrics_filtered, task_logger)
        ratios_en = scoring_results["ratios_en"]
        score_payload = scoring_results["score_payload"]

        await touch_analysis_runtime_heartbeat(task_id)

        if await _maybe_cancel_analysis(task_id, task_logger):
            return

        await broadcast_task_event(task_id, {
            "type": "status_update",
            "task_id": task_id,
            "status": "analyzing",
            "progress": 80,
        })

        # 3. AI Analysis Phase
        nlp_result = await _run_ai_analysis_phase(text, metrics_filtered, ratios_en, task_logger)

        await touch_analysis_runtime_heartbeat(task_id)

        if await _maybe_cancel_analysis(task_id, task_logger):
            return

        # 4. Save & Notify
        total_duration = (time.monotonic() - start_time) * 1000
        analysis_record = await get_analysis(task_id)
        filename = None
        if analysis_record and isinstance(analysis_record.result, dict):
            filename = analysis_record.result.get("filename")
        result_payload = {
            "filename": filename,
            "data": {
                "scanned": scanned,
                "text": text[:5000],
                "tables": tables[:10],
                "metrics": metrics_filtered,
                "ratios": ratios_en,
                "score": score_payload,
                "nlp": nlp_result,
                "extraction_metadata": metadata_payload,
            }
        }

        await _finalize_task(task_id, result_payload, total_duration, task_logger)
        
    except Exception as exc:
        await _handle_task_failure(task_id, exc, start_time, task_logger)
    finally:
        # Unified cleanup for both success and failure cases
        cleanup_temp_file(file_path)


async def _try_llm_extraction(
    text: str,
    tables: list,
    task_logger: logging.Logger,
) -> dict:
    """Attempt LLM-based metric extraction with fallback to regex/camelot.

    Returns a tuple-compatible dict from parse_financial_statements_with_metadata
    or LLM extraction result, always as dict[str, ExtractionMetadata].
    Logs the reason for any fallback switch.
    """
    fallback = await asyncio.to_thread(
        parse_financial_statements_with_metadata, tables, text
    )

    if not ai_service.is_configured:
        task_logger.warning(
            "LLM extraction skipped: reason=%s", "llm_unavailable"
        )
        return fallback

    try:
        result = await extract_with_llm(
            text,
            ai_service,
            chunk_size=app_settings.llm_chunk_size,
            max_chunks=app_settings.llm_max_chunks,
            token_budget=app_settings.llm_token_budget,
        )
    except Exception as exc:
        task_logger.warning(
            "LLM extraction failed: reason=%s error=%s", "llm_error", repr(exc)
        )
        return fallback

    if result is None:
        task_logger.warning(
            "LLM extraction returned None: reason=%s", "llm_error"
        )
        return fallback

    # Count non-null metrics
    non_null = sum(1 for m in result.values() if m.value is not None)

    if non_null < 3:
        missing = [
            k for k in ("revenue", "total_assets", "equity")
            if result.get(k) is None or result[k].value is None
        ]
        task_logger.warning(
            "LLM extraction insufficient (%d metrics): reason=%s missing=%s",
            non_null, "insufficient_metrics", missing,
        )
        # Merge: fill missing keys from fallback
        for key, meta in fallback.items():
            if result.get(key) is None or result[key].value is None:
                result[key] = meta
        return result

    return result


async def _run_extraction_phase(file_path: str, logger: logging.Logger) -> dict:
    """Run text and table extraction from PDF."""
    start = time.monotonic()
    
    scanned = await asyncio.to_thread(is_scanned_pdf, file_path)
    if scanned:
        text = await asyncio.to_thread(extract_text_from_scanned, file_path)
        if not is_clean_financial_text(text):
            logger.warning(
                "OCR text quality is poor (%d chars) — financial keywords not found",
                len(text),
            )
    else:
        text = await asyncio.to_thread(extract_text, file_path)

    # Skip camelot for scanned/glyph-encoded PDFs — it can't read raster images
    # and wastes 5-8 minutes processing pages that yield no tables
    if scanned:
        tables = []
        logger.info("Skipping camelot table extraction for scanned/OCR PDF")
    else:
        tables = await asyncio.to_thread(extract_tables, file_path)
    if app_settings.llm_extraction_enabled:
        metadata = await _try_llm_extraction(text, tables, logger)
    else:
        metadata = await asyncio.to_thread(
            parse_financial_statements_with_metadata, tables, text
        )
    metrics_filtered, metadata_payload = apply_confidence_filter(metadata)

    # NOTE: scale factor is already applied inside parse_financial_statements_with_metadata.
    # Do NOT call _detect_scale_factor here again — that would double-scale all values.

    # Regex fallback for critical metrics
    if (not metrics_filtered.get("revenue") or not metrics_filtered.get("total_assets")) and text:
        logger.warning("Critical metrics missing, using regex fallback")
        regex_metrics = extract_metrics_regex(text)
        for key, value in regex_metrics.items():
            if value is not None and metrics_filtered.get(key) is None:
                metrics_filtered[key] = value
    
    logger.info("PDF extraction completed", extra={"duration_ms": (time.monotonic() - start) * 1000})
    return {
        "text": text,
        "metrics": metrics_filtered,
        "metadata": metadata_payload,
        "scanned": scanned,
        "tables": tables
    }


async def _run_scoring_phase(metrics_filtered: dict, logger: logging.Logger) -> dict:
    """Calculate ratios and integral score."""
    start = time.monotonic()
    
    ratios_ru = await asyncio.to_thread(calculate_ratios, metrics_filtered)
    raw_score = await asyncio.to_thread(calculate_integral_score, ratios_ru)
    
    ratios_en = translate_ratios(ratios_ru)
    score_payload = build_score_payload(raw_score, ratios_en)
    score_payload = apply_data_quality_guardrails(score_payload, metrics_filtered)
    
    logger.info("Scoring completed", extra={"duration_ms": (time.monotonic() - start) * 1000})
    return {"ratios_en": ratios_en, "score_payload": score_payload}


async def _run_ai_analysis_phase(text: str, extracted_metrics: dict, ratios: dict, task_logger: logging.Logger) -> dict:
    """Run NLP narrative analysis and generate recommendations."""
    nlp_result = {"risks": [], "key_factors": [], "recommendations": []}

    if text and len(text) > 500:
        try:
            nlp_result = await asyncio.wait_for(analyze_narrative(text), timeout=60.0)
        except Exception as e:
            task_logger.warning("NLP analysis failed: %s", e)

    try:
        recommendations = await asyncio.wait_for(
            generate_recommendations(extracted_metrics, ratios, nlp_result),
            timeout=90.0
        )
        nlp_result["recommendations"] = recommendations
    except Exception as e:
        task_logger.warning("Recommendations generation failed: %s", e)

    return nlp_result


async def _finalize_task(task_id: str, payload: dict, duration: float, logger: logging.Logger) -> None:
    """Update DB and broadcast success."""
    await update_analysis(task_id, "completed", payload)
    await broadcast_task_event(task_id, {
        "type": "status_update",
        "task_id": task_id,
        "status": "completed",
        "progress": 100,
        "result": payload
    })
    logger.info("PDF processing completed successfully", extra={"duration_ms": duration})
    metrics.record_task_success(duration)


async def _handle_task_failure(task_id: str, exc: Exception, start_time: float, logger: logging.Logger) -> None:
    """Handle task errors and notify clients."""
    duration = (time.monotonic() - start_time) * 1000
    logger.exception("PDF processing failed: %s", exc, extra={"duration_ms": duration})
    metrics.record_task_failure()
    
    try:
        error_msg = str(exc)
        await update_analysis(task_id, "failed", {"error": error_msg})
        await broadcast_task_event(task_id, {
            "type": "status_update",
            "task_id": task_id,
            "status": "failed",
            "error": error_msg
        })
    except Exception as update_exc:
        logger.critical("Failed to update task status: %s", update_exc)


# ---------------------------------------------------------------------------
# Multi-period analysis orchestrator

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


def _normalize_runtime_periods(periods: list) -> list[RuntimePeriodInput]:
    normalized: list[RuntimePeriodInput] = []
    for period in periods:
        if isinstance(period, dict):
            normalized.append(
                RuntimePeriodInput(
                    period_label=str(period["period_label"]),
                    file_path=str(period["file_path"]),
                )
            )
            continue

        normalized.append(
            RuntimePeriodInput(
                period_label=str(period.period_label),
                file_path=str(period.file_path),
            )
        )
    return normalized


def _build_multi_cancelled_result(collected: list[dict]) -> dict:
    payload = _cancelled_payload()
    if collected:
        payload["periods"] = sort_periods_chronologically(collected)
    return payload


async def _finalize_multi_analysis_cancellation(
    session_id: str,
    progress: dict[str, int],
    collected: list[dict],
    session_logger: logging.Logger,
) -> None:
    result_payload = _build_multi_cancelled_result(collected)
    await mark_multi_session_cancelled(
        session_id,
        progress=progress,
        result=result_payload,
    )
    await broadcast_task_event(session_id, {
        "type": "status_update",
        "session_id": session_id,
        "status": "cancelled",
        "progress": progress,
        "result": result_payload,
    })
    metrics.record_task_failure()
    session_logger.info("Multi-analysis session cancelled")


async def _maybe_cancel_multi_analysis(
    session_id: str,
    progress: dict[str, int],
    collected: list[dict],
    session_logger: logging.Logger,
) -> bool:
    if not await is_multi_session_cancel_requested(session_id):
        return False
    await _finalize_multi_analysis_cancellation(
        session_id,
        progress,
        collected,
        session_logger,
    )
    return True


async def _process_single_period(period_label: str, file_path: str, session_id: str | None = None) -> dict:
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
            text = await asyncio.to_thread(pdf_extractor.extract_text, file_path)

        tables = await asyncio.to_thread(pdf_extractor.extract_tables, file_path)
        if session_id is not None:
            await touch_multi_session_runtime_heartbeat(session_id)
        metadata = await asyncio.to_thread(
            pdf_extractor.parse_financial_statements_with_metadata, tables, text
        )
        metrics, extraction_metadata_payload = apply_confidence_filter(metadata)
        ratios_ru = await asyncio.to_thread(calculate_ratios, metrics)
        if session_id is not None:
            await touch_multi_session_runtime_heartbeat(session_id)
        raw_score = await asyncio.to_thread(calculate_integral_score, ratios_ru)

        ratios_en = translate_ratios(ratios_ru)
        score_payload = build_score_payload(raw_score, ratios_en)
        score_payload = apply_data_quality_guardrails(score_payload, metrics)

        return {
            "period_label": period_label,
            "ratios": ratios_en,
            "score": score_payload.get("score", None),
            "risk_level": score_payload.get("risk_level", None),
            "extraction_metadata": extraction_metadata_payload,
        }
    except FileNotFoundError:
        logger.warning("Period '%s' file not found: %s", period_label, file_path)
        return {"period_label": period_label, "error": "file_not_found"}
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
    periods = _normalize_runtime_periods(periods)
    total = len(periods)
    
    # Create logger with session context
    session_logger = get_logger(__name__, session_id=session_id)
    session_logger.info("Multi-analysis session started: %d periods", total)

    collected: list[dict] = []
    failed_count = 0
    remaining_paths = [period.file_path for period in periods]

    try:
        await update_multi_session(
            session_id,
            status="processing",
            progress={"completed": 0, "total": total},
        )
        await touch_multi_session_runtime_heartbeat(session_id)

        if await _maybe_cancel_multi_analysis(
            session_id,
            {"completed": 0, "total": total},
            collected,
            session_logger,
        ):
            return

        for idx, period in enumerate(periods):
            if time.monotonic() - start_time > _MULTI_ANALYSIS_TIMEOUT:
                session_logger.error(
                    "Session exceeded timeout (%ds) after %d/%d periods",
                    _MULTI_ANALYSIS_TIMEOUT, idx, total
                )
                await update_multi_session(
                    session_id,
                    status="failed",
                    progress={"completed": idx, "total": total},
                )
                metrics.record_task_failure()
                return

            progress_payload = {"completed": idx, "total": total}
            if await _maybe_cancel_multi_analysis(
                session_id,
                progress_payload,
                collected,
                session_logger,
            ):
                return

            period_label: str = period.period_label
            file_path: str = period.file_path

            period_logger = get_logger(__name__, session_id=session_id, task_id=period_label)
            period_logger.info("Processing period %d/%d", idx + 1, total)

            result = await _process_single_period(period_label, file_path, session_id)
            cleanup_temp_file(file_path)
            if file_path in remaining_paths:
                remaining_paths.remove(file_path)

            if "error" in result:
                failed_count += 1
                period_logger.warning("Period failed: %s", result["error"])
            else:
                period_logger.info("Period completed successfully")

            collected.append(result)

            progress_payload = {"completed": idx + 1, "total": total}
            await update_multi_session(
                session_id,
                progress=progress_payload,
            )
            await touch_multi_session_runtime_heartbeat(session_id)

            await broadcast_task_event(session_id, {
                "type": "progress_update",
                "session_id": session_id,
                "status": "processing",
                "progress": progress_payload
            })

        if await _maybe_cancel_multi_analysis(
            session_id,
            {"completed": total, "total": total},
            collected,
            session_logger,
        ):
            return

        sorted_results = sort_periods_chronologically(collected)
        total_duration = (time.monotonic() - start_time) * 1000

        if failed_count == total:
            final_status = "failed"
            session_logger.error("Session failed: all %d periods failed", total, extra={"duration_ms": total_duration})
            metrics.record_task_failure()
        elif failed_count > 0:
            final_status = "completed"
            session_logger.warning(
                "Session completed with errors: %d/%d periods failed",
                failed_count, total,
                extra={"duration_ms": total_duration}
            )
            metrics.record_task_success(total_duration)
        else:
            final_status = "completed"
            session_logger.info("Session completed successfully", extra={"duration_ms": total_duration})
            metrics.record_task_success(total_duration)

        final_payload = {
            "periods": sorted_results
        }
        await update_multi_session(
            session_id,
            status=final_status,
            progress={"completed": total, "total": total},
            result=final_payload,
        )

        await broadcast_task_event(session_id, {
            "type": "status_update",
            "session_id": session_id,
            "status": final_status,
            "progress": {"completed": total, "total": total},
            "result": final_payload
        })
    finally:
        for file_path in remaining_paths:
            cleanup_temp_file(file_path)



