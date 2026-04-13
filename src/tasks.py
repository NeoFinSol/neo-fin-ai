import asyncio
import logging
import os
import time
from dataclasses import dataclass
from typing import Any

from src.analysis.extractor import semantics as extractor_semantics
from src.analysis.extractor.confidence_policy import (
    CALIBRATED_RUNTIME_CONFIDENCE_POLICY,
)
from src.analysis.extractor.decision_trace import (
    LLMMergeTrace,
    RejectionTrace,
    build_decision_trace,
    decision_trace_to_dict,
)
from src.analysis.extractor.pipeline import parse_financial_statements_debug
from src.analysis.extractor.runtime_decisions import (
    _llm_rejection_reason,
    should_prefer_llm_metric,
)
from src.analysis.extractor.types import ExtractionMetadata as ExtractionMetadataType
from src.analysis.extractor.types import RawCandidates
from src.analysis.issuer_fallback import apply_issuer_metric_overrides
from src.analysis.math.comparative import ComparativePeriodInput, run_comparative_math
from src.analysis.math.periods import compatibility_sort_key
from src.analysis.math.projections import project_legacy_ratios
from src.analysis.nlp_analysis import analyze_narrative_with_runtime
from src.analysis.pdf_extractor import (
    apply_confidence_filter,
    extract_metrics_regex,
    extract_tables,
    extract_text,
    extract_text_from_scanned,
    is_scanned_pdf,
    parse_financial_statements_with_metadata,
)

# Alias expected by tests (БАГ 10 — module-level import requirement)
_extract_metrics_with_regex = extract_metrics_regex
from sqlalchemy.exc import SQLAlchemyError

from src.analysis.llm_extractor import extract_with_llm, is_clean_financial_text
from src.analysis.ratios import (  # backward-compatible test patch surface
    calculate_ratios,
    translate_ratios,
)
from src.analysis.recommendations import generate_recommendations
from src.analysis.scoring import (  # backward-compatible test patch surface
    annualize_metrics_for_period,
    calculate_integral_score,
    calculate_score_from_precomputed_ratios,
    calculate_score_with_context,
    resolve_scoring_methodology,
)
from src.core.ai_service import ai_service
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
from src.utils.file_utils import cleanup_temp_file
from src.utils.logging_config import get_logger, metrics

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


CONFIDENCE_THRESHOLD: float = app_settings.confidence_threshold


async def _ensure_analysis_exists(task_id: str) -> bool:
    """
    Ensure Analysis record exists for task_id.

    Uses upsert pattern to handle race conditions.

    Args:
        task_id: Unique task identifier

    Returns:
        bool: True if record exists/created, False if DB unavailable
    """
    try:
        existing = await get_analysis(task_id)
    except SQLAlchemyError:
        logger.exception("DB error reading analysis for task %s", task_id)
        return False
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


async def _finalize_analysis_cancellation(
    task_id: str, task_logger: logging.Logger
) -> None:
    payload = _cancelled_payload()
    await mark_analysis_cancelled(task_id, payload)
    await broadcast_task_event(
        task_id,
        {
            "type": "status_update",
            "task_id": task_id,
            "status": "cancelled",
            "error": payload["error"],
        },
    )
    metrics.record_task_failure()
    task_logger.info("Analysis task cancelled")


async def _maybe_cancel_analysis(task_id: str, task_logger: logging.Logger) -> bool:
    if not await is_analysis_cancel_requested(task_id):
        return False
    await _finalize_analysis_cancellation(task_id, task_logger)
    return True


async def _start_analysis_processing(
    task_id: str,
    task_logger: logging.Logger,
) -> bool:
    task_logger.info("PDF processing started")

    if not await _ensure_analysis_exists(task_id):
        task_logger.critical("Database unavailable - aborting processing")
        metrics.record_task_failure()
        return False

    await touch_analysis_runtime_heartbeat(task_id)
    return not await _maybe_cancel_analysis(task_id, task_logger)


async def _broadcast_analysis_status(
    task_id: str,
    status: str,
    progress: int,
) -> None:
    await broadcast_task_event(
        task_id,
        {
            "type": "status_update",
            "task_id": task_id,
            "status": status,
            "progress": progress,
        },
    )


async def _checkpoint_analysis_phase(
    task_id: str,
    task_logger: logging.Logger,
    *,
    next_status: str | None = None,
    progress: int | None = None,
) -> bool:
    await touch_analysis_runtime_heartbeat(task_id)
    if await _maybe_cancel_analysis(task_id, task_logger):
        return False
    if next_status is not None and progress is not None:
        await _broadcast_analysis_status(task_id, next_status, progress)
    return True


async def _load_analysis_filename(task_id: str) -> str | None:
    analysis_record = await get_analysis(task_id)
    if analysis_record and isinstance(analysis_record.result, dict):
        return analysis_record.result.get("filename")
    return None


def _build_result_payload(
    *,
    filename: str | None,
    scanned: bool,
    text: str,
    tables: list,
    metrics_filtered: dict,
    ratios_en: dict,
    score_payload: dict,
    nlp_result: dict,
    ai_runtime: dict,
    metadata_payload: dict,
) -> dict:
    return {
        "filename": filename,
        "data": {
            "scanned": scanned,
            "text": text[:5000],
            "tables": tables[:10],
            "metrics": metrics_filtered,
            "ratios": ratios_en,
            "score": score_payload,
            "nlp": nlp_result,
            "ai_runtime": ai_runtime,
            "extraction_metadata": metadata_payload,
        },
    }


def _coerce_final_metadata(
    metadata_payload: dict,
) -> dict[str, ExtractionMetadataType]:
    final_metadata: dict[str, ExtractionMetadataType] = {}
    for metric_key, metric_value in metadata_payload.items():
        if isinstance(metric_value, dict) and "confidence" in metric_value:
            final_metadata[metric_key] = ExtractionMetadataType(**metric_value)
        elif isinstance(metric_value, ExtractionMetadataType):
            final_metadata[metric_key] = metric_value
    return final_metadata


def _build_result_decision_trace(
    extraction_results: dict,
    metadata_payload: dict,
) -> dict:
    extractor_debug = extraction_results.get("extractor_debug")
    raw_candidates = (
        extractor_debug.raw_candidates if extractor_debug else RawCandidates()
    )
    decision_logs = extractor_debug.decision_logs if extractor_debug else {}
    guardrail_events = extractor_debug.guardrail_events if extractor_debug else []
    winner_map = extractor_debug.winner_map if extractor_debug else {}

    decision_trace = build_decision_trace(
        raw_candidates=raw_candidates,
        metadata=_coerce_final_metadata(metadata_payload),
        decision_logs=decision_logs,
        guardrail_events=guardrail_events,
        winner_map=winner_map,
        llm_merge_trace=extraction_results.get("llm_merge_trace"),
        issuer_overrides=extraction_results.get("issuer_override_traces", []),
        confidence_threshold=CALIBRATED_RUNTIME_CONFIDENCE_POLICY.strong_direct_threshold,
        policy_name=CALIBRATED_RUNTIME_CONFIDENCE_POLICY.name,
    )
    return decision_trace_to_dict(decision_trace)


def _attach_decision_trace(
    result_payload: dict,
    extraction_results: dict,
    metadata_payload: dict,
) -> None:
    result_payload["data"]["decision_trace"] = _build_result_decision_trace(
        extraction_results,
        metadata_payload,
    )


async def _run_analysis_extraction_step(
    task_id: str,
    file_path: str,
    task_logger: logging.Logger,
    *,
    ai_provider: str | None,
    debug_trace: bool,
) -> dict | None:
    await _broadcast_analysis_status(task_id, "extracting", 25)
    extraction_results = await _run_extraction_phase(
        file_path,
        task_logger,
        ai_provider=ai_provider,
        debug_trace=debug_trace,
    )
    if not await _checkpoint_analysis_phase(
        task_id,
        task_logger,
        next_status="scoring",
        progress=55,
    ):
        return None
    return extraction_results


async def _run_analysis_scoring_step(
    task_id: str,
    extraction_results: dict,
    task_logger: logging.Logger,
) -> tuple[str | None, dict] | None:
    filename = await _load_analysis_filename(task_id)
    scoring_results = await _run_scoring_phase(
        extraction_results["metrics"],
        task_logger,
        filename=filename,
        text=extraction_results["text"],
        extraction_metadata=extraction_results["metadata"],
    )
    if not await _checkpoint_analysis_phase(
        task_id,
        task_logger,
        next_status="analyzing",
        progress=80,
    ):
        return None
    return filename, scoring_results


async def _run_analysis_ai_step(
    task_id: str,
    extraction_results: dict,
    scoring_results: dict,
    task_logger: logging.Logger,
    *,
    ai_provider: str | None,
) -> tuple[dict, dict] | None:
    ai_results = await _run_ai_analysis_phase(
        extraction_results["text"],
        extraction_results["metrics"],
        scoring_results["ratios_en"],
        task_logger,
        ai_provider=ai_provider,
    )
    if not await _checkpoint_analysis_phase(task_id, task_logger):
        return None
    return ai_results


async def _finalize_analysis_success(
    task_id: str,
    start_time: float,
    task_logger: logging.Logger,
    *,
    filename: str | None,
    extraction_results: dict,
    scoring_results: dict,
    nlp_result: dict,
    ai_runtime: dict,
    debug_trace: bool,
) -> None:
    result_payload = _build_result_payload(
        filename=filename,
        scanned=extraction_results["scanned"],
        text=extraction_results["text"],
        tables=extraction_results["tables"],
        metrics_filtered=extraction_results["metrics"],
        ratios_en=scoring_results["ratios_en"],
        score_payload=scoring_results["score_payload"],
        nlp_result=nlp_result,
        ai_runtime=ai_runtime,
        metadata_payload=extraction_results["metadata"],
    )
    if debug_trace:
        _attach_decision_trace(
            result_payload,
            extraction_results,
            extraction_results["metadata"],
        )

    total_duration = (time.monotonic() - start_time) * 1000
    await _finalize_task(task_id, result_payload, total_duration, task_logger)


async def _run_process_pdf(
    task_id: str,
    file_path: str,
    task_logger: logging.Logger,
    *,
    ai_provider: str | None,
    debug_trace: bool,
    start_time: float,
) -> None:
    if not await _start_analysis_processing(task_id, task_logger):
        return

    extraction_results = await _run_analysis_extraction_step(
        task_id,
        file_path,
        task_logger,
        ai_provider=ai_provider,
        debug_trace=debug_trace,
    )
    if extraction_results is None:
        return

    scoring_step = await _run_analysis_scoring_step(
        task_id, extraction_results, task_logger
    )
    if scoring_step is None:
        return
    filename, scoring_results = scoring_step

    ai_step = await _run_analysis_ai_step(
        task_id,
        extraction_results,
        scoring_results,
        task_logger,
        ai_provider=ai_provider,
    )
    if ai_step is None:
        return
    nlp_result, ai_runtime = ai_step

    await _finalize_analysis_success(
        task_id,
        start_time,
        task_logger,
        filename=filename,
        extraction_results=extraction_results,
        scoring_results=scoring_results,
        nlp_result=nlp_result,
        ai_runtime=ai_runtime,
        debug_trace=debug_trace,
    )


async def process_pdf(
    task_id: str,
    file_path: str,
    ai_provider: str | None = None,
    debug_trace: bool = False,
) -> None:
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
        await _run_process_pdf(
            task_id,
            file_path,
            task_logger,
            ai_provider=ai_provider,
            debug_trace=debug_trace,
            start_time=start_time,
        )
    except Exception as exc:
        await _handle_task_failure(task_id, exc, start_time, task_logger)
    finally:
        cleanup_temp_file(file_path)


async def _try_llm_extraction(
    text: str,
    tables: list,
    task_logger: logging.Logger,
    ai_provider: str | None = None,
    debug_trace: bool = False,
) -> dict:
    """Attempt LLM-based metric extraction with fallback to regex/camelot.

    Returns dict with keys:
      metadata: dict[str, ExtractionMetadata] — merged result
      llm_merge_trace: LLMMergeTrace | None — structured LLM merge trace
      extractor_debug: ExtractionDebugTrace | None — pipeline debug data (when debug_trace)
    """

    if debug_trace:
        debug_data = await asyncio.to_thread(
            parse_financial_statements_debug, tables, text
        )
        fallback = dict(debug_data.metadata)
        extractor_debug = debug_data
    else:
        fallback = await asyncio.to_thread(
            parse_financial_statements_with_metadata, tables, text
        )
        extractor_debug = None

    if not ai_service.is_provider_available(ai_provider):
        task_logger.warning("LLM extraction skipped: reason=%s", "llm_unavailable")
        return {
            "metadata": fallback,
            "llm_merge_trace": None,
            "extractor_debug": extractor_debug,
        }

    try:
        extraction_run = await extract_with_llm(
            text,
            ai_service,
            chunk_size=app_settings.llm_chunk_size,
            max_chunks=app_settings.llm_max_chunks,
            token_budget=app_settings.llm_token_budget,
            ai_provider=ai_provider,
        )
    except Exception as exc:
        task_logger.warning(
            "LLM extraction failed: reason=%s error=%s", "llm_error", repr(exc)
        )
        return {
            "metadata": fallback,
            "llm_merge_trace": None,
            "extractor_debug": extractor_debug,
        }

    if extraction_run.metrics is None:
        task_logger.warning(
            "LLM extraction returned None: reason=%s",
            extraction_run.failure_reason or "llm_error",
        )
        return {
            "metadata": fallback,
            "llm_merge_trace": None,
            "extractor_debug": extractor_debug,
        }

    llm_result = extraction_run.metrics

    non_null = sum(1 for m in llm_result.values() if m.value is not None)

    result = {}
    llm_contributed: list[str] = []
    llm_rejected: list[RejectionTrace] = []
    for key, fallback_meta in fallback.items():
        llm_meta = llm_result.get(key)
        if should_prefer_llm_metric(
            llm_meta,
            fallback_meta,
            threshold=CONFIDENCE_THRESHOLD,
        ):
            result[key] = llm_meta
            llm_contributed.append(key)
            continue

        result[key] = fallback_meta
        if llm_meta is not None and llm_meta.value is not None:
            reason = _llm_rejection_reason(
                llm_meta,
                fallback_meta,
                threshold=CONFIDENCE_THRESHOLD,
            )
            fallback_norm = extractor_semantics.normalize_legacy_metadata(fallback_meta)
            llm_norm = extractor_semantics.normalize_legacy_metadata(llm_meta)
            llm_rejected.append(
                RejectionTrace(
                    metric_key=key,
                    winner_profile=(
                        fallback_norm.source,
                        fallback_norm.match_semantics,
                        fallback_norm.inference_mode,
                    ),
                    loser_profile=(
                        llm_norm.source,
                        llm_norm.match_semantics,
                        llm_norm.inference_mode,
                    ),
                    reason_code=reason or "llm_rejected_unknown",
                    reason_detail=None,
                )
            )

    llm_merge_trace = (
        LLMMergeTrace(
            contributed=llm_contributed,
            rejected=llm_rejected,
        )
        if (llm_contributed or llm_rejected)
        else None
    )

    if non_null < 3:
        missing = [
            k
            for k in ("revenue", "total_assets", "equity")
            if llm_result.get(k) is None or llm_result[k].value is None
        ]
        task_logger.warning(
            "LLM extraction insufficient (%d metrics): reason=%s missing=%s",
            non_null,
            "insufficient_metrics",
            missing,
        )
    if llm_contributed:
        task_logger.info(
            "LLM extraction contributed metrics after fallback merge: %s",
            llm_contributed,
        )
    if llm_rejected:
        task_logger.warning(
            "LLM extraction rejected for existing fallback metrics: %s",
            [r.metric_key for r in llm_rejected],
        )

    return {
        "metadata": result,
        "llm_merge_trace": llm_merge_trace,
        "extractor_debug": extractor_debug,
    }


async def _run_extraction_phase(
    file_path: str,
    logger: logging.Logger,
    ai_provider: str | None = None,
    debug_trace: bool = False,
) -> dict:
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

    if scanned:
        tables = []
        logger.info("Skipping camelot table extraction for scanned/OCR PDF")
    else:
        tables = await asyncio.to_thread(extract_tables, file_path)

    llm_merge_trace = None
    extractor_debug = None

    if app_settings.llm_extraction_enabled:
        llm_result = await _try_llm_extraction(
            text,
            tables,
            logger,
            ai_provider=ai_provider,
            debug_trace=debug_trace,
        )
        metadata = llm_result["metadata"]
        llm_merge_trace = llm_result.get("llm_merge_trace")
        extractor_debug = llm_result.get("extractor_debug")
    else:
        if debug_trace:
            debug_data = await asyncio.to_thread(
                parse_financial_statements_debug, tables, text
            )
            metadata = dict(debug_data.metadata)
            extractor_debug = debug_data
        else:
            metadata = await asyncio.to_thread(
                parse_financial_statements_with_metadata, tables, text
            )

    metadata, issuer_override_traces = apply_issuer_metric_overrides(
        metadata,
        filename=os.path.basename(file_path),
        text=text,
    )
    metrics_filtered, metadata_payload = apply_confidence_filter(metadata)

    # NOTE: scale factor is already applied inside parse_financial_statements_with_metadata.
    # Do NOT call _detect_scale_factor here again — that would double-scale all values.

    # Regex fallback for critical metrics
    if (
        not metrics_filtered.get("revenue") or not metrics_filtered.get("total_assets")
    ) and text:
        logger.warning("Critical metrics missing, using regex fallback")
        regex_metrics = extract_metrics_regex(text)
        regex_blocklist: set[str] = set()
        if (
            metrics_filtered.get("revenue") is None
            and metrics_filtered.get("net_profit") is not None
            and metrics_filtered.get("total_assets") is not None
        ):
            regex_blocklist.add("revenue")
        min_monetary_abs = 1000.0
        monetary_keys = {
            "revenue",
            "net_profit",
            "total_assets",
            "liabilities",
            "equity",
            "current_assets",
            "short_term_liabilities",
            "accounts_receivable",
            "inventory",
            "cash_and_equivalents",
        }
        for key, value in regex_metrics.items():
            if value is None:
                continue
            if key in regex_blocklist:
                logger.info(
                    "Skipping regex fallback for %s because deterministic parser kept stronger balance/P&L signals",
                    key,
                )
                continue
            if key in monetary_keys and abs(value) < min_monetary_abs:
                logger.debug(
                    "Skipping regex fallback for %s due to low absolute value: %s",
                    key,
                    value,
                )
                continue
            if value is not None and metrics_filtered.get(key) is None:
                metrics_filtered[key] = value

    logger.info(
        "PDF extraction completed",
        extra={"duration_ms": (time.monotonic() - start) * 1000},
    )
    return {
        "text": text,
        "metrics": metrics_filtered,
        "metadata": metadata_payload,
        "scanned": scanned,
        "tables": tables,
        "llm_merge_trace": llm_merge_trace,
        "issuer_override_traces": issuer_override_traces,
        "extractor_debug": extractor_debug,
    }


async def _run_scoring_phase(
    metrics_filtered: dict,
    logger: logging.Logger,
    filename: str | None = None,
    text: str | None = None,
    extraction_metadata: dict[str, dict] | None = None,
) -> dict:
    """Calculate ratios and integral score."""
    start = time.monotonic()
    score_context = calculate_score_with_context(
        metrics_filtered,
        filename=filename,
        text=text,
        extraction_metadata=extraction_metadata,
    )

    logger.info(
        "Scoring completed", extra={"duration_ms": (time.monotonic() - start) * 1000}
    )
    return {
        "ratios_en": score_context["ratios_en"],
        "score_payload": score_context["score_payload"],
    }


async def _run_ai_analysis_phase(
    text: str,
    extracted_metrics: dict,
    ratios: dict,
    task_logger: logging.Logger,
    ai_provider: str | None = None,
) -> tuple[dict, dict]:
    """Run NLP narrative analysis and generate recommendations."""
    nlp_result = {"risks": [], "key_factors": [], "recommendations": []}
    requested_provider = ai_provider or "auto"
    ai_provider_available = ai_service.is_provider_available(ai_provider)
    ai_runtime = {
        "requested_provider": requested_provider,
        "effective_provider": (
            (ai_provider or ai_service.provider) if ai_provider_available else None
        ),
        "status": "skipped",
        "reason_code": "insufficient_text",
    }

    if text and len(text) > 500:
        try:
            nlp_result, narrative_runtime = await asyncio.wait_for(
                analyze_narrative_with_runtime(text, ai_provider=ai_provider),
                timeout=60.0,
            )
            ai_runtime["status"] = narrative_runtime["status"]
            ai_runtime["reason_code"] = narrative_runtime["reason_code"]
        except Exception as e:
            task_logger.warning("NLP analysis failed: %s", e)
            ai_runtime["status"] = "failed"
            ai_runtime["reason_code"] = "provider_error"

    try:
        recommendations = await asyncio.wait_for(
            generate_recommendations(
                extracted_metrics,
                ratios,
                nlp_result,
                ai_provider=ai_provider,
            ),
            timeout=90.0,
        )
        nlp_result["recommendations"] = recommendations
    except Exception as e:
        task_logger.warning("Recommendations generation failed: %s", e)

    return nlp_result, ai_runtime


async def _finalize_task(
    task_id: str, payload: dict, duration: float, logger: logging.Logger
) -> None:
    """Update DB and broadcast success."""
    await update_analysis(task_id, "completed", payload)
    await broadcast_task_event(
        task_id,
        {
            "type": "status_update",
            "task_id": task_id,
            "status": "completed",
            "progress": 100,
            "result": payload,
        },
    )
    logger.info(
        "PDF processing completed successfully", extra={"duration_ms": duration}
    )
    metrics.record_task_success(duration)


async def _handle_task_failure(
    task_id: str, exc: Exception, start_time: float, logger: logging.Logger
) -> None:
    """Handle task errors and notify clients."""
    duration = (time.monotonic() - start_time) * 1000
    logger.exception("PDF processing failed: %s", exc, extra={"duration_ms": duration})
    metrics.record_task_failure()

    try:
        error_msg = str(exc)
        await update_analysis(task_id, "failed", {"error": error_msg})
        await broadcast_task_event(
            task_id,
            {
                "type": "status_update",
                "task_id": task_id,
                "status": "failed",
                "error": error_msg,
            },
        )
    except Exception as update_exc:
        logger.critical("Failed to update task status: %s", update_exc)


# ---------------------------------------------------------------------------
# Multi-period analysis orchestrator

_MULTI_ANALYSIS_TIMEOUT = 600  # seconds


def parse_period_label(label: str) -> tuple[int, int]:
    """Compatibility wrapper around the canonical period parser sort key."""
    return compatibility_sort_key(label)


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


def _build_multi_period_error_result(period_label: str, error: str) -> dict[str, Any]:
    return {
        "period_label": period_label,
        "ratios": {},
        "score": None,
        "risk_level": None,
        "score_methodology": None,
        "extraction_metadata": {},
        "error": error,
    }


async def _finalize_multi_analysis_cancellation(
    session_id: str,
    progress: dict[str, int],
    extracted_periods: list[dict[str, Any]],
    failed_periods: list[dict[str, Any]],
    session_logger: logging.Logger,
) -> None:
    collected = await _assemble_multi_period_results(extracted_periods, failed_periods)
    result_payload = _build_multi_cancelled_result(collected)
    await mark_multi_session_cancelled(
        session_id,
        progress=progress,
        result=result_payload,
    )
    await broadcast_task_event(
        session_id,
        {
            "type": "status_update",
            "session_id": session_id,
            "status": "cancelled",
            "progress": progress,
            "result": result_payload,
        },
    )
    metrics.record_task_failure()
    session_logger.info("Multi-analysis session cancelled")


async def _maybe_cancel_multi_analysis(
    session_id: str,
    progress: dict[str, int],
    extracted_periods: list[dict[str, Any]],
    failed_periods: list[dict[str, Any]],
    session_logger: logging.Logger,
) -> bool:
    if not await is_multi_session_cancel_requested(session_id):
        return False
    await _finalize_multi_analysis_cancellation(
        session_id,
        progress,
        extracted_periods,
        failed_periods,
        session_logger,
    )
    return True


async def _process_single_period(
    period_label: str, file_path: str, session_id: str | None = None
) -> dict:
    """
    Extract one period for later batch comparative processing.

    Args:
        period_label: Human-readable period identifier (e.g. "2023", "Q1/2023")
        file_path: Path to the PDF file for this period

    Returns:
        dict with extracted data or a period-shaped error result.
    """
    period_logger = get_logger(__name__, session_id=session_id, task_id=period_label)
    try:
        extraction = await _run_extraction_phase(file_path, period_logger)
        if session_id is not None:
            await touch_multi_session_runtime_heartbeat(session_id)
        return {
            "period_label": period_label,
            "text": extraction["text"],
            "metrics": extraction["metrics"],
            "extraction_metadata": extraction["metadata"],
        }
    except FileNotFoundError:
        period_logger.warning("Period '%s' file not found: %s", period_label, file_path)
        return _build_multi_period_error_result(period_label, "file_not_found")
    except Exception as exc:
        period_logger.warning(
            "Period '%s' processing failed: %s", period_label, exc, exc_info=True
        )
        return _build_multi_period_error_result(period_label, "processing_failed")


def _resolve_multi_period_methodology(period_result: dict[str, Any]) -> dict[str, Any]:
    base_ratios_ru = calculate_ratios(period_result["metrics"])
    base_ratios_en = translate_ratios(base_ratios_ru)
    return resolve_scoring_methodology(
        period_result["metrics"],
        ratios_en=base_ratios_en,
        filename=period_result["period_label"],
        text=period_result["text"],
    )


def _prepare_period_for_comparative(
    period_result: dict[str, Any],
) -> tuple[dict[str, Any], ComparativePeriodInput]:
    methodology = _resolve_multi_period_methodology(period_result)
    basis_metrics = annualize_metrics_for_period(
        period_result["metrics"],
        methodology["period_basis"],
    )
    prepared_period = {
        "period_label": period_result["period_label"],
        "basis_metrics": basis_metrics,
        "extraction_metadata": period_result["extraction_metadata"],
        "methodology": methodology,
    }
    comparative_input = ComparativePeriodInput(
        period_label=period_result["period_label"],
        metrics=basis_metrics,
        extraction_metadata=period_result["extraction_metadata"],
    )
    return prepared_period, comparative_input


def _score_comparative_period(
    prepared_period: dict[str, Any],
    comparative_result,
) -> dict[str, Any]:
    ratios_ru, _projection_trace = project_legacy_ratios(
        comparative_result.derived_metrics
    )
    ratios_en = translate_ratios(ratios_ru)
    score_context = calculate_score_from_precomputed_ratios(
        metrics=prepared_period["basis_metrics"],
        ratios_ru=ratios_ru,
        ratios_en=ratios_en,
        methodology=prepared_period["methodology"],
        extraction_metadata=prepared_period["extraction_metadata"],
    )
    score_payload = score_context["score_payload"]
    return {
        "period_label": prepared_period["period_label"],
        "ratios": ratios_en,
        "score": score_payload.get("score"),
        "risk_level": score_payload.get("risk_level"),
        "score_methodology": score_payload.get("methodology"),
        "extraction_metadata": prepared_period["extraction_metadata"],
    }


def _build_multi_period_results(extracted_periods: list[dict[str, Any]]) -> list[dict]:
    prepared_periods: list[dict[str, Any]] = []
    comparative_inputs: list[ComparativePeriodInput] = []
    for period_result in extracted_periods:
        prepared_period, comparative_input = _prepare_period_for_comparative(
            period_result
        )
        prepared_periods.append(prepared_period)
        comparative_inputs.append(comparative_input)

    comparative_results = run_comparative_math(comparative_inputs)
    return [
        _score_comparative_period(prepared_period, comparative_result)
        for prepared_period, comparative_result in zip(
            prepared_periods,
            comparative_results,
            strict=True,
        )
    ]


async def _assemble_multi_period_results(
    extracted_periods: list[dict[str, Any]],
    failed_periods: list[dict[str, Any]],
) -> list[dict]:
    if not extracted_periods:
        return list(failed_periods)
    successful_results = await asyncio.to_thread(
        _build_multi_period_results,
        list(extracted_periods),
    )
    return [*failed_periods, *successful_results]


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

    extracted_periods: list[dict[str, Any]] = []
    failed_periods: list[dict[str, Any]] = []
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
            extracted_periods,
            failed_periods,
            session_logger,
        ):
            return

        for idx, period in enumerate(periods):
            if time.monotonic() - start_time > _MULTI_ANALYSIS_TIMEOUT:
                session_logger.error(
                    "Session exceeded timeout (%ds) after %d/%d periods",
                    _MULTI_ANALYSIS_TIMEOUT,
                    idx,
                    total,
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
                extracted_periods,
                failed_periods,
                session_logger,
            ):
                return

            period_label: str = period.period_label
            file_path: str = period.file_path

            period_logger = get_logger(
                __name__, session_id=session_id, task_id=period_label
            )
            period_logger.info("Processing period %d/%d", idx + 1, total)

            result = await _process_single_period(period_label, file_path, session_id)
            cleanup_temp_file(file_path)
            if file_path in remaining_paths:
                remaining_paths.remove(file_path)

            if "error" in result:
                failed_periods.append(result)
                period_logger.warning("Period failed: %s", result["error"])
            else:
                extracted_periods.append(result)
                period_logger.info("Period completed successfully")

            progress_payload = {"completed": idx + 1, "total": total}
            await update_multi_session(
                session_id,
                progress=progress_payload,
            )
            await touch_multi_session_runtime_heartbeat(session_id)

            await broadcast_task_event(
                session_id,
                {
                    "type": "progress_update",
                    "session_id": session_id,
                    "status": "processing",
                    "progress": progress_payload,
                },
            )

        if await _maybe_cancel_multi_analysis(
            session_id,
            {"completed": total, "total": total},
            extracted_periods,
            failed_periods,
            session_logger,
        ):
            return

        await touch_multi_session_runtime_heartbeat(session_id)
        collected = await _assemble_multi_period_results(
            extracted_periods,
            failed_periods,
        )
        await touch_multi_session_runtime_heartbeat(session_id)
        failed_count = len(failed_periods)
        sorted_results = sort_periods_chronologically(collected)
        total_duration = (time.monotonic() - start_time) * 1000

        if failed_count == total:
            final_status = "failed"
            session_logger.error(
                "Session failed: all %d periods failed",
                total,
                extra={"duration_ms": total_duration},
            )
            metrics.record_task_failure()
        elif failed_count > 0:
            final_status = "completed"
            session_logger.warning(
                "Session completed with errors: %d/%d periods failed",
                failed_count,
                total,
                extra={"duration_ms": total_duration},
            )
            metrics.record_task_success(total_duration)
        else:
            final_status = "completed"
            session_logger.info(
                "Session completed successfully", extra={"duration_ms": total_duration}
            )
            metrics.record_task_success(total_duration)

        final_payload = {"periods": sorted_results}
        await update_multi_session(
            session_id,
            status=final_status,
            progress={"completed": total, "total": total},
            result=final_payload,
        )

        await broadcast_task_event(
            session_id,
            {
                "type": "status_update",
                "session_id": session_id,
                "status": final_status,
                "progress": {"completed": total, "total": total},
                "result": final_payload,
            },
        )
    finally:
        for file_path in remaining_paths:
            cleanup_temp_file(file_path)
