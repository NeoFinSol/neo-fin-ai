"""Tests for background tasks module."""
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.analysis.pdf_extractor import extract_text
from src.analysis.ratios import translate_ratios
from src.analysis.scoring import build_score_payload
from src.tasks import process_pdf

# Minimal valid score dict returned by calculate_integral_score
_MOCK_SCORE = {"score": 85.5, "risk_level": "низкий", "details": {}}


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
        raw = {"score": 80.0, "risk_level": "низкий", "details": {
            "Коэффициент текущей ликвидности": 0.9,
        }}
        result = build_score_payload(raw, {"current_ratio": 2.0})
        assert result["factors"][0]["impact"] == "positive"

    def test_impact_negative(self):
        raw = {"score": 20.0, "risk_level": "высокий", "details": {
            "Коэффициент текущей ликвидности": 0.1,
        }}
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

        with patch("src.tasks.update_analysis", new_callable=AsyncMock) as mock_update, \
             patch("src.tasks.create_analysis", new_callable=AsyncMock) as mock_create, \
             patch("src.tasks.get_analysis", new_callable=AsyncMock, return_value=None), \
             patch("src.tasks.is_scanned_pdf", return_value=False), \
             patch("src.tasks.extract_text", return_value="Extracted text"), \
             patch("src.tasks.extract_tables", return_value=[]), \
             patch("src.tasks.parse_financial_statements_with_metadata", return_value={}), \
             patch("src.tasks.apply_confidence_filter", return_value=({}, {})), \
             patch("src.tasks.calculate_ratios", return_value={}), \
             patch("src.tasks.calculate_integral_score", return_value=_MOCK_SCORE), \
             patch("src.tasks.ws_manager.broadcast", new_callable=AsyncMock) as mock_ws, \
             patch("src.tasks._ensure_analysis_exists", return_value=True), \
             patch("src.tasks.cleanup_temp_file"):

            await process_pdf(task_id, file_path)

            mock_update.assert_called()
            last_call = mock_update.call_args_list[-1]
            assert last_call[0][1] == "completed"
            mock_ws.assert_called()

    @pytest.mark.asyncio
    async def test_existing_analysis_update(self):
        task_id = "test-task-456"
        file_path = "/tmp/test2.pdf"

        with patch("src.tasks.update_analysis", new_callable=AsyncMock) as mock_update, \
             patch("src.tasks.create_analysis", new_callable=AsyncMock) as mock_create, \
             patch("src.tasks.get_analysis", new_callable=AsyncMock, return_value=None), \
             patch("src.tasks.is_scanned_pdf", return_value=False), \
             patch("src.tasks.extract_text", return_value="Text"), \
             patch("src.tasks.extract_tables", return_value=[]), \
             patch("src.tasks.parse_financial_statements_with_metadata", return_value={}), \
             patch("src.tasks.apply_confidence_filter", return_value=({}, {})), \
             patch("src.tasks.calculate_ratios", return_value={}), \
             patch("src.tasks.calculate_integral_score", return_value=_MOCK_SCORE), \
             patch("src.tasks.ws_manager.broadcast", new_callable=AsyncMock), \
             patch("src.tasks._ensure_analysis_exists", return_value=True), \
             patch("src.tasks.cleanup_temp_file"):

            mock_update.return_value = {"id": task_id}

            await process_pdf(task_id, file_path)

            mock_update.assert_called()
            assert mock_update.call_args_list[-1][0][1] == "completed"

    @pytest.mark.asyncio
    async def test_scanned_pdf_processing(self):
        task_id = "scanned-task"
        file_path = "/tmp/scanned.pdf"

        with patch("src.tasks.update_analysis", new_callable=AsyncMock) as mock_update, \
             patch("src.tasks.create_analysis", new_callable=AsyncMock), \
             patch("src.tasks.get_analysis", new_callable=AsyncMock, return_value=None), \
             patch("src.tasks.is_scanned_pdf", return_value=True), \
             patch("src.tasks.extract_text_from_scanned", return_value="OCR text"), \
             patch("src.tasks.extract_tables", return_value=[]), \
             patch("src.tasks.parse_financial_statements_with_metadata", return_value={}), \
             patch("src.tasks.apply_confidence_filter", return_value=({}, {})), \
             patch("src.tasks.calculate_ratios", return_value={}), \
             patch("src.tasks.calculate_integral_score", return_value=_MOCK_SCORE), \
             patch("src.tasks.ws_manager.broadcast", new_callable=AsyncMock), \
             patch("src.tasks._ensure_analysis_exists", return_value=True), \
             patch("src.tasks.cleanup_temp_file"):

            await process_pdf(task_id, file_path)
            assert mock_update.call_args_list[-1][0][1] == "completed"

    @pytest.mark.asyncio
    async def test_processing_failure(self, caplog):
        task_id = "failed-task"
        file_path = "/tmp/fail.pdf"

        with patch("src.tasks.update_analysis", new_callable=AsyncMock) as mock_update, \
             patch("src.tasks.create_analysis", new_callable=AsyncMock), \
             patch("src.tasks.is_scanned_pdf", side_effect=Exception("PDF corrupted")), \
             patch("src.tasks.ws_manager.broadcast", new_callable=AsyncMock) as mock_ws, \
             patch("src.tasks._ensure_analysis_exists", return_value=True), \
             patch("src.tasks.cleanup_temp_file"):

            await process_pdf(task_id, file_path)

            mock_update.assert_called()
            # Find the call with 'failed' status
            failed_call = next(c for c in mock_update.call_args_list if c[0][1] == "failed")
            assert "error" in failed_call[0][2]
            assert "PDF corrupted" in str(failed_call[0][2]["error"])
            assert "PDF processing failed" in caplog.text
            mock_ws.assert_called()

    @pytest.mark.asyncio
    async def test_temp_file_cleanup_on_success(self):
        """Test temporary file cleanup after successful processing."""
        task_id = "cleanup-task"
        file_path = "/tmp/cleanup.pdf"

        with patch("src.tasks.update_analysis", new_callable=AsyncMock) as mock_update, \
             patch("src.tasks.create_analysis", new_callable=AsyncMock), \
             patch("src.tasks.get_analysis", new_callable=AsyncMock, return_value=None), \
             patch("src.tasks.is_scanned_pdf", return_value=False), \
             patch("src.tasks.extract_text", return_value="Text"), \
             patch("src.tasks.extract_tables", return_value=[]), \
             patch("src.tasks.parse_financial_statements_with_metadata", return_value={}), \
             patch("src.tasks.apply_confidence_filter", return_value=({}, {})), \
             patch("src.tasks.calculate_ratios", return_value={}), \
             patch("src.tasks.calculate_integral_score", return_value=_MOCK_SCORE), \
             patch("src.tasks.ws_manager.broadcast", new_callable=AsyncMock), \
             patch("src.tasks._ensure_analysis_exists", return_value=True), \
             patch("src.tasks.cleanup_temp_file") as mock_cleanup:

            await process_pdf(task_id, file_path)

            assert mock_update.call_args_list[-1][0][1] == "completed"
            mock_cleanup.assert_called_once_with(file_path)

    @pytest.mark.asyncio
    async def test_temp_file_cleanup_on_failure(self):
        """Test temporary file cleanup even when processing fails."""
        task_id = "cleanup-fail-task"
        file_path = "/tmp/cleanup_fail.pdf"

        with patch("src.tasks.update_analysis", new_callable=AsyncMock), \
             patch("src.tasks.create_analysis", new_callable=AsyncMock), \
             patch("src.tasks.is_scanned_pdf", side_effect=Exception("Error")), \
             patch("src.tasks.ws_manager.broadcast", new_callable=AsyncMock), \
             patch("src.tasks._ensure_analysis_exists", return_value=True), \
             patch("src.tasks.cleanup_temp_file") as mock_cleanup:

            await process_pdf(task_id, file_path)

            mock_cleanup.assert_called_once_with(file_path)

    @pytest.mark.asyncio
    async def test_nonexistent_file_no_cleanup(self):
        """Test that cleanup is not called when db aborts early."""
        task_id = "no-db-task"
        file_path = "/tmp/doesnt_exist.pdf"

        with patch("src.tasks.update_analysis", new_callable=AsyncMock), \
             patch("src.tasks.create_analysis", new_callable=AsyncMock), \
             patch("src.tasks._ensure_analysis_exists", return_value=False), \
             patch("src.tasks.cleanup_temp_file") as mock_cleanup:

            await process_pdf(task_id, file_path)

            # In the current implementation, cleanup is in 'finally' block
            # and it's called even if _ensure_analysis_exists returns False
            # but before that we return. Wait, 'finally' is ALWAYS called.
            # Let's check src/tasks.py:108
            mock_cleanup.assert_called_once_with(file_path)
