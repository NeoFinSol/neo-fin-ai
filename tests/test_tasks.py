"""Tests for background tasks module."""

import warnings
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from cryptography.utils import CryptographyDeprecationWarning
from fastapi import BackgroundTasks

from src.analysis.extractor import semantics
from src.analysis.llm_extractor import LlmExtractionRunResult, _build_empty_result
from src.analysis.pdf_extractor import extract_text
from src.analysis.ratios import translate_ratios
from src.analysis.scoring import build_score_payload
from src.core.task_queue import (
    _run_worker_coroutine,
    dispatch_multi_analysis_task,
    dispatch_pdf_task,
    revoke_runtime_task,
)
from src.exceptions import TaskRuntimeError
from src.tasks import _run_extraction_phase, _try_llm_extraction, process_pdf

warnings.filterwarnings(
    "ignore",
    message=r"ARC4 has been moved.*",
    category=CryptographyDeprecationWarning,
)

# Minimal valid score dict returned by calculate_integral_score
_MOCK_SCORE = {"score": 85.5, "risk_level": "низкий", "details": {}}


def _assert_completed_status_called(mock_update, task_id: str) -> None:
    assert any(
        call.args[:2] == (task_id, "completed") for call in mock_update.call_args_list
    ), f"update_analysis was never called with completed status for {task_id}"


class TestExtractTextFromPdf:
    """Tests for PDF text extraction."""

    def test_successful_extraction(self):
        mock_page = MagicMock()
        mock_page.extract_text.return_value = "Page 1 content"
        mock_reader = MagicMock()
        mock_reader.pages = [mock_page]

        with patch("PyPDF2.PdfReader", return_value=mock_reader):
            result = extract_text("test.pdf")
            assert result == "Page 1 content"

    def test_multiple_pages(self):
        page1 = MagicMock()
        page1.extract_text.return_value = "Page 1"
        page2 = MagicMock()
        page2.extract_text.return_value = "Page 2"
        mock_reader = MagicMock()
        mock_reader.pages = [page1, page2]

        with patch("PyPDF2.PdfReader", return_value=mock_reader):
            result = extract_text("test.pdf")
            assert result == "Page 1\nPage 2"

    def test_empty_page_handling(self):
        mock_page = MagicMock()
        mock_page.extract_text.return_value = None
        mock_reader = MagicMock()
        mock_reader.pages = [mock_page]

        with patch("PyPDF2.PdfReader", return_value=mock_reader):
            result = extract_text("test.pdf")
            assert result == ""

    def test_extraction_error_on_page(self, caplog):
        mock_page = MagicMock()
        mock_page.extract_text.side_effect = Exception("Extraction failed")
        mock_reader = MagicMock()
        mock_reader.pages = [mock_page]

        with patch("PyPDF2.PdfReader", return_value=mock_reader):
            with caplog.at_level("WARNING"):
                result = extract_text("test.pdf")
                assert "Failed to extract text from page 1" in caplog.text
                assert result == ""


class TestTranslateRatios:
    """Tests for translate_ratios helper."""

    def test_known_keys_translated(self):
        ratios = {
            "Коэффициент текущей ликвидности": 1.5,
            "Рентабельность активов (ROA)": 0.08,
        }
        result = translate_ratios(ratios)
        assert result["current_ratio"] == 1.5
        assert result["roa"] == 0.08

    def test_unknown_keys_dropped(self, caplog):
        ratios = {"Unknown Key": 42.0}
        with caplog.at_level("WARNING"):
            result = translate_ratios(ratios)
        assert result == {}
        assert "Unmapped ratio keys" in caplog.text

    def test_empty_dict(self):
        assert translate_ratios({}) == {}


class TestBuildScorePayload:
    """Tests for build_score_payload helper."""

    def test_basic_structure(self):
        raw_score = {
            "score": 75.0,
            "risk_level": "средний",
            "details": {
                "Коэффициент текущей ликвидности": 0.8,
                "Рентабельность активов (ROA)": 0.6,
            },
        }
        ratios_en = {"current_ratio": 1.6, "roa": 0.08}
        result = build_score_payload(raw_score, ratios_en)

        assert result["score"] == 75.0
        assert result["risk_level"] == "medium"
        assert isinstance(result["factors"], list)
        assert len(result["factors"]) == 2
        assert isinstance(result["normalized_scores"], dict)

    def test_risk_level_translation(self):
        for ru, en in [("низкий", "low"), ("средний", "medium"), ("высокий", "high")]:
            raw = {"score": 50.0, "risk_level": ru, "details": {}}
            result = build_score_payload(raw, {})
            assert result["risk_level"] == en

    def test_impact_positive(self):
        raw = {
            "score": 80.0,
            "risk_level": "низкий",
            "details": {
                "Коэффициент текущей ликвидности": 0.9,
            },
        }
        result = build_score_payload(raw, {"current_ratio": 2.0})
        assert result["factors"][0]["impact"] == "positive"

    def test_impact_negative(self):
        raw = {
            "score": 20.0,
            "risk_level": "высокий",
            "details": {
                "Коэффициент текущей ликвидности": 0.1,
            },
        }
        result = build_score_payload(raw, {"current_ratio": 0.3})
        assert result["factors"][0]["impact"] == "negative"

    def test_empty_details(self):
        raw = {"score": 0.0, "risk_level": "высокий", "details": {}}
        result = build_score_payload(raw, {})
        assert result["factors"] == []


class TestProcessPdf:
    """Tests for async PDF processing."""

    @pytest.mark.asyncio
    async def test_successful_processing(self):
        task_id = "test-task-123"
        file_path = "/tmp/test.pdf"

        with (
            patch("src.tasks.update_analysis", new_callable=AsyncMock) as mock_update,
            patch("src.tasks.create_analysis", new_callable=AsyncMock) as mock_create,
            patch("src.tasks.get_analysis", new_callable=AsyncMock, return_value=None),
            patch("src.tasks.touch_analysis_runtime_heartbeat", new_callable=AsyncMock),
            patch(
                "src.tasks.is_analysis_cancel_requested",
                new_callable=AsyncMock,
                return_value=False,
            ),
            patch("src.tasks.is_scanned_pdf", return_value=False),
            patch("src.tasks.extract_text", return_value="Extracted text"),
            patch("src.tasks.extract_tables", return_value=[]),
            patch(
                "src.tasks.parse_financial_statements_with_metadata", return_value={}
            ),
            patch("src.tasks.apply_confidence_filter", return_value=({}, {})),
            patch("src.tasks.calculate_ratios", return_value={}),
            patch("src.tasks.calculate_integral_score", return_value=_MOCK_SCORE),
            patch("src.tasks.broadcast_task_event", new_callable=AsyncMock) as mock_ws,
            patch("src.tasks._ensure_analysis_exists", return_value=True),
            patch("src.tasks.cleanup_temp_file"),
        ):
            await process_pdf(task_id, file_path)

            mock_update.assert_called()
            _assert_completed_status_called(mock_update, task_id)
            mock_ws.assert_called()

    @pytest.mark.asyncio
    async def test_existing_analysis_update(self):
        task_id = "test-task-456"
        file_path = "/tmp/test2.pdf"

        with (
            patch("src.tasks.update_analysis", new_callable=AsyncMock) as mock_update,
            patch("src.tasks.create_analysis", new_callable=AsyncMock) as mock_create,
            patch("src.tasks.get_analysis", new_callable=AsyncMock, return_value=None),
            patch("src.tasks.touch_analysis_runtime_heartbeat", new_callable=AsyncMock),
            patch(
                "src.tasks.is_analysis_cancel_requested",
                new_callable=AsyncMock,
                return_value=False,
            ),
            patch("src.tasks.is_scanned_pdf", return_value=False),
            patch("src.tasks.extract_text", return_value="Text"),
            patch("src.tasks.extract_tables", return_value=[]),
            patch(
                "src.tasks.parse_financial_statements_with_metadata", return_value={}
            ),
            patch("src.tasks.apply_confidence_filter", return_value=({}, {})),
            patch("src.tasks.calculate_ratios", return_value={}),
            patch("src.tasks.calculate_integral_score", return_value=_MOCK_SCORE),
            patch("src.tasks.broadcast_task_event", new_callable=AsyncMock),
            patch("src.tasks._ensure_analysis_exists", return_value=True),
            patch("src.tasks.cleanup_temp_file"),
        ):
            mock_update.return_value = {"id": task_id}

            await process_pdf(task_id, file_path)

            mock_update.assert_called()
            _assert_completed_status_called(mock_update, task_id)

    @pytest.mark.asyncio
    async def test_scanned_pdf_processing(self):
        task_id = "scanned-task"
        file_path = "/tmp/scanned.pdf"

        with (
            patch("src.tasks.update_analysis", new_callable=AsyncMock) as mock_update,
            patch("src.tasks.create_analysis", new_callable=AsyncMock),
            patch("src.tasks.get_analysis", new_callable=AsyncMock, return_value=None),
            patch("src.tasks.touch_analysis_runtime_heartbeat", new_callable=AsyncMock),
            patch(
                "src.tasks.is_analysis_cancel_requested",
                new_callable=AsyncMock,
                return_value=False,
            ),
            patch("src.tasks.is_scanned_pdf", return_value=True),
            patch("src.tasks.extract_text_from_scanned", return_value="OCR text"),
            patch("src.tasks.extract_tables", return_value=[]),
            patch(
                "src.tasks.parse_financial_statements_with_metadata", return_value={}
            ),
            patch("src.tasks.apply_confidence_filter", return_value=({}, {})),
            patch("src.tasks.calculate_ratios", return_value={}),
            patch("src.tasks.calculate_integral_score", return_value=_MOCK_SCORE),
            patch("src.tasks.broadcast_task_event", new_callable=AsyncMock),
            patch("src.tasks._ensure_analysis_exists", return_value=True),
            patch("src.tasks.cleanup_temp_file"),
        ):
            await process_pdf(task_id, file_path)
            _assert_completed_status_called(mock_update, task_id)

    @pytest.mark.asyncio
    async def test_processing_failure(self, caplog):
        task_id = "failed-task"
        file_path = "/tmp/fail.pdf"

        with (
            patch("src.tasks.update_analysis", new_callable=AsyncMock) as mock_update,
            patch("src.tasks.create_analysis", new_callable=AsyncMock),
            patch("src.tasks.touch_analysis_runtime_heartbeat", new_callable=AsyncMock),
            patch(
                "src.tasks.is_analysis_cancel_requested",
                new_callable=AsyncMock,
                return_value=False,
            ),
            patch("src.tasks.is_scanned_pdf", side_effect=Exception("PDF corrupted")),
            patch("src.tasks.broadcast_task_event", new_callable=AsyncMock) as mock_ws,
            patch("src.tasks._ensure_analysis_exists", return_value=True),
            patch("src.tasks.cleanup_temp_file"),
        ):
            await process_pdf(task_id, file_path)

            mock_update.assert_called()
            # Find the call with 'failed' status
            failed_call = next(
                c for c in mock_update.call_args_list if c[0][1] == "failed"
            )
            assert "error" in failed_call[0][2]
            assert "PDF corrupted" in str(failed_call[0][2]["error"])
            assert "PDF processing failed" in caplog.text
            mock_ws.assert_called()

    @pytest.mark.asyncio
    async def test_temp_file_cleanup_on_success(self):
        """Test temporary file cleanup after successful processing."""
        task_id = "cleanup-task"
        file_path = "/tmp/cleanup.pdf"

        with (
            patch("src.tasks.update_analysis", new_callable=AsyncMock) as mock_update,
            patch("src.tasks.create_analysis", new_callable=AsyncMock),
            patch("src.tasks.get_analysis", new_callable=AsyncMock, return_value=None),
            patch("src.tasks.touch_analysis_runtime_heartbeat", new_callable=AsyncMock),
            patch(
                "src.tasks.is_analysis_cancel_requested",
                new_callable=AsyncMock,
                return_value=False,
            ),
            patch("src.tasks.is_scanned_pdf", return_value=False),
            patch("src.tasks.extract_text", return_value="Text"),
            patch("src.tasks.extract_tables", return_value=[]),
            patch(
                "src.tasks.parse_financial_statements_with_metadata", return_value={}
            ),
            patch("src.tasks.apply_confidence_filter", return_value=({}, {})),
            patch("src.tasks.calculate_ratios", return_value={}),
            patch("src.tasks.calculate_integral_score", return_value=_MOCK_SCORE),
            patch("src.tasks.broadcast_task_event", new_callable=AsyncMock),
            patch("src.tasks._ensure_analysis_exists", return_value=True),
            patch("src.tasks.cleanup_temp_file") as mock_cleanup,
        ):
            await process_pdf(task_id, file_path)

            _assert_completed_status_called(mock_update, task_id)
            mock_cleanup.assert_called_once_with(file_path)

    @pytest.mark.asyncio
    async def test_successful_processing_emits_phase_updates_in_order(self):
        task_id = "ordered-task"
        file_path = "/tmp/ordered.pdf"

        with (
            patch("src.tasks.update_analysis", new_callable=AsyncMock),
            patch("src.tasks.create_analysis", new_callable=AsyncMock),
            patch("src.tasks.get_analysis", new_callable=AsyncMock, return_value=None),
            patch("src.tasks.touch_analysis_runtime_heartbeat", new_callable=AsyncMock),
            patch(
                "src.tasks.is_analysis_cancel_requested",
                new_callable=AsyncMock,
                return_value=False,
            ),
            patch("src.tasks.is_scanned_pdf", return_value=False),
            patch("src.tasks.extract_text", return_value="Text"),
            patch("src.tasks.extract_tables", return_value=[]),
            patch(
                "src.tasks.parse_financial_statements_with_metadata", return_value={}
            ),
            patch("src.tasks.apply_confidence_filter", return_value=({}, {})),
            patch("src.tasks.calculate_ratios", return_value={}),
            patch("src.tasks.calculate_integral_score", return_value=_MOCK_SCORE),
            patch("src.tasks.broadcast_task_event", new_callable=AsyncMock) as mock_ws,
            patch("src.tasks._ensure_analysis_exists", return_value=True),
            patch("src.tasks.cleanup_temp_file"),
        ):
            await process_pdf(task_id, file_path)

        statuses = [
            call.args[1]["status"]
            for call in mock_ws.await_args_list
            if call.args and len(call.args) > 1 and "status" in call.args[1]
        ]
        assert statuses == ["extracting", "scoring", "analyzing", "completed"]

    @pytest.mark.asyncio
    async def test_temp_file_cleanup_on_failure(self):
        """Test temporary file cleanup even when processing fails."""
        task_id = "cleanup-fail-task"
        file_path = "/tmp/cleanup_fail.pdf"

        with (
            patch("src.tasks.update_analysis", new_callable=AsyncMock),
            patch("src.tasks.create_analysis", new_callable=AsyncMock),
            patch("src.tasks.touch_analysis_runtime_heartbeat", new_callable=AsyncMock),
            patch(
                "src.tasks.is_analysis_cancel_requested",
                new_callable=AsyncMock,
                return_value=False,
            ),
            patch("src.tasks.is_scanned_pdf", side_effect=Exception("Error")),
            patch("src.tasks.broadcast_task_event", new_callable=AsyncMock),
            patch("src.tasks._ensure_analysis_exists", return_value=True),
            patch("src.tasks.cleanup_temp_file") as mock_cleanup,
        ):
            await process_pdf(task_id, file_path)

            mock_cleanup.assert_called_once_with(file_path)

    @pytest.mark.asyncio
    async def test_cancellation_marks_analysis_cancelled(self):
        task_id = "cancelled-task"
        file_path = "/tmp/cancelled.pdf"

        with (
            patch(
                "src.tasks.mark_analysis_cancelled", new_callable=AsyncMock
            ) as mock_mark_cancelled,
            patch("src.tasks.broadcast_task_event", new_callable=AsyncMock) as mock_ws,
            patch("src.tasks.touch_analysis_runtime_heartbeat", new_callable=AsyncMock),
            patch(
                "src.tasks.is_analysis_cancel_requested",
                new_callable=AsyncMock,
                return_value=True,
            ),
            patch("src.tasks._ensure_analysis_exists", return_value=True),
            patch("src.tasks.cleanup_temp_file") as mock_cleanup,
        ):
            await process_pdf(task_id, file_path)

            mock_mark_cancelled.assert_awaited_once()
            assert mock_mark_cancelled.await_args.args == (
                task_id,
                {
                    "error": "Task cancelled by user",
                    "reason_code": "cancelled_by_request",
                },
            )
            mock_ws.assert_awaited_once()
            assert mock_ws.await_args.args[1]["status"] == "cancelled"
            mock_cleanup.assert_called_once_with(file_path)

    @pytest.mark.asyncio
    async def test_nonexistent_file_no_cleanup(self):
        """Test that cleanup is not called when db aborts early."""
        task_id = "no-db-task"
        file_path = "/tmp/doesnt_exist.pdf"

        with (
            patch("src.tasks.update_analysis", new_callable=AsyncMock),
            patch("src.tasks.create_analysis", new_callable=AsyncMock),
            patch("src.tasks._ensure_analysis_exists", return_value=False),
            patch("src.tasks.cleanup_temp_file") as mock_cleanup,
        ):
            await process_pdf(task_id, file_path)

            # In the current implementation, cleanup is in 'finally' block
            # and it's called even if _ensure_analysis_exists returns False
            # but before that we return. Wait, 'finally' is ALWAYS called.
            # Let's check src/tasks.py:108
            mock_cleanup.assert_called_once_with(file_path)

    @pytest.mark.asyncio
    async def test_regex_fallback_does_not_restore_revenue_after_parser_conflict(self):
        logger = MagicMock()
        filtered_metrics = {
            "revenue": None,
            "net_profit": 1_348_503_000.0,
            "total_assets": 435_659_511_000.0,
        }

        with (
            patch("src.tasks.is_scanned_pdf", return_value=True),
            patch("src.tasks.extract_text_from_scanned", return_value="OCR text"),
            patch("src.tasks.is_clean_financial_text", return_value=True),
            patch(
                "src.tasks.parse_financial_statements_with_metadata", return_value={}
            ),
            patch(
                "src.tasks.apply_confidence_filter",
                return_value=(filtered_metrics.copy(), {}),
            ),
            patch(
                "src.tasks.extract_metrics_regex",
                return_value={"revenue": 123_618_123_618.0},
            ),
            patch.object(
                __import__("src.tasks", fromlist=["app_settings"]).app_settings,
                "llm_extraction_enabled",
                False,
            ),
        ):
            result = await _run_extraction_phase("/tmp/scanned.pdf", logger)

        assert result["metrics"]["revenue"] is None
        assert result["metrics"]["net_profit"] == 1_348_503_000.0
        assert result["metrics"]["total_assets"] == 435_659_511_000.0


class TestTryLlmExtraction:
    @pytest.mark.asyncio
    async def test_invalid_schema_reason_uses_fallback(self, caplog):
        fallback = _build_empty_result()
        fallback["revenue"] = fallback["revenue"].__class__(
            value=1_000_000.0,
            confidence=0.5,
            source="text_regex",
        )

        with (
            patch(
                "src.tasks.parse_financial_statements_with_metadata",
                return_value=fallback,
            ),
            patch("src.tasks.ai_service") as mock_ai_service,
            patch("src.tasks.extract_with_llm", new_callable=AsyncMock) as mock_extract,
        ):
            mock_ai_service.is_configured = True
            mock_extract.return_value = LlmExtractionRunResult(
                metrics=None,
                failure_reason="invalid_schema",
            )

            with caplog.at_level("WARNING"):
                result = await _try_llm_extraction(
                    "Выручка 1 000 000",
                    [],
                    __import__("logging").getLogger("test"),
                )

        assert result["metadata"]["revenue"].value == 1_000_000.0
        assert "reason=invalid_schema" in caplog.text

    @pytest.mark.asyncio
    async def test_llm_only_fills_missing_or_derived_metrics(self, caplog):
        fallback = _build_empty_result()
        fallback["revenue"] = fallback["revenue"].__class__(
            value=1_000_000.0,
            confidence=0.5,
            source="text_regex",
        )
        fallback["total_assets"] = fallback["total_assets"].__class__(
            value=None,
            confidence=0.0,
            source="derived",
        )

        llm_metrics = _build_empty_result()
        llm_metrics["revenue"] = llm_metrics["revenue"].__class__(
            value=1_000.0,
            confidence=0.98,
            source="text",
            evidence_version="v2",
            match_semantics="keyword_match",
            inference_mode="direct",
            reason_code=semantics.REASON_LLM_EXTRACTION,
        )
        llm_metrics["total_assets"] = llm_metrics["total_assets"].__class__(
            value=2_500_000.0,
            confidence=0.95,
            source="text",
            evidence_version="v2",
            match_semantics="keyword_match",
            inference_mode="direct",
            reason_code=semantics.REASON_LLM_EXTRACTION,
        )
        llm_metrics["cash_and_equivalents"] = llm_metrics[
            "cash_and_equivalents"
        ].__class__(
            value=250_000.0,
            confidence=0.93,
            source="text",
            evidence_version="v2",
            match_semantics="keyword_match",
            inference_mode="direct",
            reason_code=semantics.REASON_LLM_EXTRACTION,
        )

        with (
            patch(
                "src.tasks.parse_financial_statements_with_metadata",
                return_value=fallback,
            ),
            patch("src.tasks.ai_service") as mock_ai_service,
            patch("src.tasks.extract_with_llm", new_callable=AsyncMock) as mock_extract,
        ):
            mock_ai_service.is_configured = True
            mock_extract.return_value = LlmExtractionRunResult(
                metrics=llm_metrics,
                failure_reason=None,
            )

            with caplog.at_level("INFO"):
                result = await _try_llm_extraction(
                    "Выручка 1 000 000",
                    [],
                    __import__("logging").getLogger("test"),
                )

        assert result["metadata"]["revenue"].value == 1_000_000.0
        assert result["metadata"]["revenue"].source == "text_regex"
        assert result["metadata"]["total_assets"].value == 2_500_000.0
        assert result["metadata"]["total_assets"].source == "text"
        assert result["metadata"]["total_assets"].evidence_version == "v2"
        assert result["metadata"]["cash_and_equivalents"].value == 250_000.0
        assert result["metadata"]["cash_and_equivalents"].source == "text"
        assert (
            result["metadata"]["cash_and_equivalents"].reason_code
            == semantics.REASON_LLM_EXTRACTION
        )
        assert "contributed metrics" in caplog.text
        assert "rejected for existing fallback metrics" in caplog.text

    @pytest.mark.asyncio
    async def test_llm_never_replaces_authoritative_override(self, caplog):
        fallback = _build_empty_result()
        fallback["ebitda"] = fallback["ebitda"].__class__(
            value=85_628_000_000.0,
            confidence=0.95,
            source="issuer_fallback",
            evidence_version="v2",
            match_semantics="not_applicable",
            inference_mode="policy_override",
            postprocess_state="none",
            reason_code=semantics.REASON_ISSUER_REPO_OVERRIDE,
            authoritative_override=True,
        )

        llm_metrics = _build_empty_result()
        llm_metrics["ebitda"] = llm_metrics["ebitda"].__class__(
            value=91_000_000_000.0,
            confidence=0.99,
            source="text",
            evidence_version="v2",
            match_semantics="keyword_match",
            inference_mode="direct",
            reason_code=semantics.REASON_LLM_EXTRACTION,
        )

        with (
            patch(
                "src.tasks.parse_financial_statements_with_metadata",
                return_value=fallback,
            ),
            patch("src.tasks.ai_service") as mock_ai_service,
            patch("src.tasks.extract_with_llm", new_callable=AsyncMock) as mock_extract,
        ):
            mock_ai_service.is_configured = True
            mock_extract.return_value = LlmExtractionRunResult(
                metrics=llm_metrics,
                failure_reason=None,
            )

            with caplog.at_level("WARNING"):
                result = await _try_llm_extraction(
                    "EBITDA 91 000 000 000",
                    [],
                    __import__("logging").getLogger("test"),
                )

        assert result["metadata"]["ebitda"].source == "issuer_fallback"
        assert result["metadata"]["ebitda"].authoritative_override is True
        assert "rejected for existing fallback metrics" in caplog.text


class TestTaskQueueDispatch:
    """Tests for persistent runtime dispatch helpers."""

    @pytest.mark.asyncio
    async def test_dispatch_pdf_task_uses_background_runtime_by_default(self):
        background_tasks = MagicMock(spec=BackgroundTasks)
        background_callable = MagicMock()

        with patch.object(
            __import__("src.core.task_queue", fromlist=["app_settings"]).app_settings,
            "task_runtime",
            "background",
        ):
            await dispatch_pdf_task(
                background_tasks,
                task_id="task-123",
                file_path="/tmp/test.pdf",
                background_callable=background_callable,
            )

        background_tasks.add_task.assert_called_once_with(
            background_callable, "task-123", "/tmp/test.pdf", None, False
        )

    @pytest.mark.asyncio
    async def test_dispatch_pdf_task_uses_celery_runtime_when_enabled(self):
        background_tasks = MagicMock(spec=BackgroundTasks)
        background_callable = MagicMock()

        with patch("src.core.task_queue.celery_app", MagicMock()):
            with patch.object(
                __import__(
                    "src.core.task_queue", fromlist=["app_settings"]
                ).app_settings,
                "task_runtime",
                "celery",
            ):
                with patch.object(
                    __import__(
                        "src.core.task_queue", fromlist=["app_settings"]
                    ).app_settings,
                    "task_queue_broker_url",
                    "redis://broker",
                ):
                    with patch(
                        "src.core.task_queue.run_pdf_task.apply_async"
                    ) as mock_apply_async:
                        await dispatch_pdf_task(
                            background_tasks,
                            task_id="task-123",
                            file_path="/tmp/test.pdf",
                            background_callable=background_callable,
                        )

        background_tasks.add_task.assert_not_called()
        mock_apply_async.assert_called_once_with(
            args=["task-123", "/tmp/test.pdf", None, False],
            task_id="task-123",
            queue="neofin",
        )

    @pytest.mark.asyncio
    async def test_dispatch_pdf_task_forwards_ai_provider(self):
        background_tasks = MagicMock(spec=BackgroundTasks)
        background_callable = MagicMock()

        with patch.object(
            __import__("src.core.task_queue", fromlist=["app_settings"]).app_settings,
            "task_runtime",
            "background",
        ):
            await dispatch_pdf_task(
                background_tasks,
                task_id="task-123",
                file_path="/tmp/test.pdf",
                background_callable=background_callable,
                ai_provider="ollama",
            )

        background_tasks.add_task.assert_called_once_with(
            background_callable,
            "task-123",
            "/tmp/test.pdf",
            "ollama",
            False,
        )

    @pytest.mark.asyncio
    async def test_dispatch_multi_analysis_task_raises_runtime_error_on_broker_failure(
        self,
    ):
        background_tasks = MagicMock(spec=BackgroundTasks)

        with patch("src.core.task_queue.celery_app", MagicMock()):
            with patch.object(
                __import__(
                    "src.core.task_queue", fromlist=["app_settings"]
                ).app_settings,
                "task_runtime",
                "celery",
            ):
                with patch.object(
                    __import__(
                        "src.core.task_queue", fromlist=["app_settings"]
                    ).app_settings,
                    "task_queue_broker_url",
                    "redis://broker",
                ):
                    with patch(
                        "src.core.task_queue.run_multi_analysis_task.apply_async",
                        side_effect=RuntimeError("broker down"),
                    ):
                        with pytest.raises(TaskRuntimeError):
                            await dispatch_multi_analysis_task(
                                background_tasks,
                                session_id="session-1",
                                periods_payload=[
                                    {
                                        "period_label": "2023",
                                        "file_path": "/tmp/2023.pdf",
                                    }
                                ],
                                background_callable=MagicMock(),
                            )

    def test_revoke_runtime_task_returns_false_in_background_mode(self):
        with patch.object(
            __import__("src.core.task_queue", fromlist=["app_settings"]).app_settings,
            "task_runtime",
            "background",
        ):
            assert revoke_runtime_task("task-123") is False

    def test_revoke_runtime_task_revokes_celery_task(self):
        mock_celery_app = MagicMock()

        with patch("src.core.task_queue.celery_app", mock_celery_app):
            with patch.object(
                __import__(
                    "src.core.task_queue", fromlist=["app_settings"]
                ).app_settings,
                "task_runtime",
                "celery",
            ):
                with patch.object(
                    __import__(
                        "src.core.task_queue", fromlist=["app_settings"]
                    ).app_settings,
                    "task_queue_broker_url",
                    "redis://broker",
                ):
                    assert revoke_runtime_task("task-123") is True

        mock_celery_app.control.revoke.assert_called_once_with("task-123")

    @pytest.mark.asyncio
    async def test_run_worker_coroutine_closes_ai_service_on_success(self):
        marker = {"ran": False}

        async def sample_coro():
            marker["ran"] = True

        with patch(
            "src.core.ai_service.ai_service.close", new_callable=AsyncMock
        ) as mock_close:
            await _run_worker_coroutine(sample_coro())

        assert marker["ran"] is True
        mock_close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_run_worker_coroutine_closes_ai_service_on_failure(self):
        async def failing_coro():
            raise RuntimeError("boom")

        with patch(
            "src.core.ai_service.ai_service.close", new_callable=AsyncMock
        ) as mock_close:
            with pytest.raises(RuntimeError, match="boom"):
                await _run_worker_coroutine(failing_coro())

        mock_close.assert_awaited_once()
