"""Tests for background tasks module."""
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.tasks import _build_score_payload, _extract_text_from_pdf, _translate_ratios, process_pdf

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
            result = _extract_text_from_pdf("test.pdf")
            assert result == "Page 1 content"

    def test_multiple_pages(self):
        page1 = MagicMock()
        page1.extract_text.return_value = "Page 1"
        page2 = MagicMock()
        page2.extract_text.return_value = "Page 2"
        mock_reader = MagicMock()
        mock_reader.pages = [page1, page2]

        with patch("PyPDF2.PdfReader", return_value=mock_reader):
            result = _extract_text_from_pdf("test.pdf")
            assert result == "Page 1\nPage 2"

    def test_empty_page_handling(self):
        mock_page = MagicMock()
        mock_page.extract_text.return_value = None
        mock_reader = MagicMock()
        mock_reader.pages = [mock_page]

        with patch("PyPDF2.PdfReader", return_value=mock_reader):
            result = _extract_text_from_pdf("test.pdf")
            assert result == ""

    def test_extraction_error_on_page(self, caplog):
        mock_page = MagicMock()
        mock_page.extract_text.side_effect = Exception("Extraction failed")
        mock_reader = MagicMock()
        mock_reader.pages = [mock_page]

        with patch("PyPDF2.PdfReader", return_value=mock_reader):
            with caplog.at_level("WARNING"):
                result = _extract_text_from_pdf("test.pdf")
                assert "Failed to extract text from page 1" in caplog.text
                assert result == ""


class TestTranslateRatios:
    """Tests for _translate_ratios helper."""

    def test_known_keys_translated(self):
        ratios = {
            "Коэффициент текущей ликвидности": 1.5,
            "Рентабельность активов (ROA)": 0.08,
        }
        result = _translate_ratios(ratios)
        assert result["current_ratio"] == 1.5
        assert result["roa"] == 0.08

    def test_unknown_keys_kept(self, caplog):
        ratios = {"Unknown Key": 42.0}
        with caplog.at_level("WARNING"):
            result = _translate_ratios(ratios)
        assert "Unknown Key" in result
        assert "Unmapped ratio keys" in caplog.text

    def test_empty_dict(self):
        assert _translate_ratios({}) == {}


class TestBuildScorePayload:
    """Tests for _build_score_payload helper."""

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
        result = _build_score_payload(raw_score, ratios_en)

        assert result["score"] == 75.0
        assert result["risk_level"] == "medium"
        assert isinstance(result["factors"], list)
        assert len(result["factors"]) == 2
        assert isinstance(result["normalized_scores"], dict)

    def test_risk_level_translation(self):
        for ru, en in [("низкий", "low"), ("средний", "medium"), ("высокий", "high")]:
            raw = {"score": 50.0, "risk_level": ru, "details": {}}
            result = _build_score_payload(raw, {})
            assert result["risk_level"] == en

    def test_impact_positive(self):
        raw = {"score": 80.0, "risk_level": "низкий", "details": {
            "Коэффициент текущей ликвидности": 0.9,
        }}
        result = _build_score_payload(raw, {"current_ratio": 2.0})
        assert result["factors"][0]["impact"] == "positive"

    def test_impact_negative(self):
        raw = {"score": 20.0, "risk_level": "высокий", "details": {
            "Коэффициент текущей ликвидности": 0.1,
        }}
        result = _build_score_payload(raw, {"current_ratio": 0.3})
        assert result["factors"][0]["impact"] == "negative"

    def test_empty_details(self):
        raw = {"score": 0.0, "risk_level": "высокий", "details": {}}
        result = _build_score_payload(raw, {})
        assert result["factors"] == []


class TestProcessPdf:
    """Tests for async PDF processing."""

    @pytest.mark.asyncio
    async def test_successful_processing(self):
        task_id = "test-task-123"
        file_path = "/tmp/test.pdf"

        with patch("src.tasks.update_analysis", new_callable=AsyncMock) as mock_update, \
             patch("src.tasks.create_analysis", new_callable=AsyncMock) as mock_create, \
             patch("src.tasks.pdf_extractor.is_scanned_pdf", return_value=False), \
             patch("src.tasks._extract_text_from_pdf", return_value="Extracted text"), \
             patch("src.tasks.pdf_extractor.extract_tables", return_value=[]), \
             patch("src.tasks.pdf_extractor.parse_financial_statements", return_value={"revenue": 100}), \
             patch("src.tasks.calculate_ratios", return_value={}), \
             patch("src.tasks.calculate_integral_score", return_value=_MOCK_SCORE), \
             patch("pathlib.Path.is_file", return_value=False):

            mock_update.return_value = None

            await process_pdf(task_id, file_path)

            mock_create.assert_called_once_with(task_id, "processing", None)
            mock_update.assert_called()
            last_call = mock_update.call_args_list[-1]
            assert last_call[0][1] == "completed"

    @pytest.mark.asyncio
    async def test_existing_analysis_update(self):
        task_id = "test-task-456"
        file_path = "/tmp/test2.pdf"

        with patch("src.tasks.update_analysis", new_callable=AsyncMock) as mock_update, \
             patch("src.tasks.create_analysis", new_callable=AsyncMock) as mock_create, \
             patch("src.tasks.pdf_extractor.is_scanned_pdf", return_value=False), \
             patch("src.tasks._extract_text_from_pdf", return_value="Text"), \
             patch("src.tasks.pdf_extractor.extract_tables", return_value=[]), \
             patch("src.tasks.pdf_extractor.parse_financial_statements", return_value={}), \
             patch("src.tasks.calculate_ratios", return_value={}), \
             patch("src.tasks.calculate_integral_score", return_value=_MOCK_SCORE), \
             patch("pathlib.Path.is_file", return_value=False):

            mock_update.return_value = {"id": task_id}

            await process_pdf(task_id, file_path)

            mock_create.assert_not_called()
            mock_update.assert_called()

    @pytest.mark.asyncio
    async def test_scanned_pdf_processing(self):
        task_id = "scanned-task"
        file_path = "/tmp/scanned.pdf"

        with patch("src.tasks.update_analysis", new_callable=AsyncMock), \
             patch("src.tasks.create_analysis", new_callable=AsyncMock), \
             patch("src.tasks.pdf_extractor.is_scanned_pdf", return_value=True), \
             patch("src.tasks.pdf_extractor.extract_text_from_scanned", return_value="OCR text"), \
             patch("src.tasks.pdf_extractor.extract_tables", return_value=[]), \
             patch("src.tasks.pdf_extractor.parse_financial_statements", return_value={}), \
             patch("src.tasks.calculate_ratios", return_value={}), \
             patch("src.tasks.calculate_integral_score", return_value=_MOCK_SCORE), \
             patch("pathlib.Path.is_file", return_value=False):

            await process_pdf(task_id, file_path)

    @pytest.mark.asyncio
    async def test_processing_failure(self, caplog):
        task_id = "failed-task"
        file_path = "/tmp/fail.pdf"

        with patch("src.tasks.update_analysis", new_callable=AsyncMock) as mock_update, \
             patch("src.tasks.create_analysis", new_callable=AsyncMock), \
             patch("src.tasks.pdf_extractor.is_scanned_pdf", side_effect=Exception("PDF corrupted")), \
             patch("pathlib.Path.is_file", return_value=False):

            await process_pdf(task_id, file_path)

            mock_update.assert_called()
            fail_call = mock_update.call_args_list[-1]
            assert fail_call[0][1] == "failed"
            assert "error" in fail_call[0][2]
            assert "PDF corrupted" in str(fail_call[0][2]["error"])
            assert "PDF processing failed" in caplog.text

    @pytest.mark.asyncio
    async def test_temp_file_cleanup_on_success(self):
        """Test temporary file cleanup after successful processing (uses Path.unlink)."""
        task_id = "cleanup-task"
        file_path = "/tmp/cleanup.pdf"

        with patch("src.tasks.update_analysis", new_callable=AsyncMock), \
             patch("src.tasks.create_analysis", new_callable=AsyncMock), \
             patch("src.tasks.pdf_extractor.is_scanned_pdf", return_value=False), \
             patch("src.tasks._extract_text_from_pdf", return_value="Text"), \
             patch("src.tasks.pdf_extractor.extract_tables", return_value=[]), \
             patch("src.tasks.pdf_extractor.parse_financial_statements", return_value={}), \
             patch("src.tasks.calculate_ratios", return_value={}), \
             patch("src.tasks.calculate_integral_score", return_value=_MOCK_SCORE), \
             patch("pathlib.Path.is_file", return_value=True), \
             patch("pathlib.Path.unlink") as mock_unlink:

            await process_pdf(task_id, file_path)

            mock_unlink.assert_called_once()

    @pytest.mark.asyncio
    async def test_temp_file_cleanup_on_failure(self):
        """Test temporary file cleanup even when processing fails."""
        task_id = "cleanup-fail-task"
        file_path = "/tmp/cleanup_fail.pdf"

        with patch("src.tasks.update_analysis", new_callable=AsyncMock), \
             patch("src.tasks.create_analysis", new_callable=AsyncMock), \
             patch("src.tasks.pdf_extractor.is_scanned_pdf", side_effect=Exception("Error")), \
             patch("pathlib.Path.is_file", return_value=True), \
             patch("pathlib.Path.unlink") as mock_unlink:

            await process_pdf(task_id, file_path)

            mock_unlink.assert_called_once()

    @pytest.mark.asyncio
    async def test_nonexistent_file_no_cleanup(self):
        """Test that unlink is not called when file doesn't exist."""
        task_id = "no-file-task"
        file_path = "/tmp/doesnt_exist.pdf"

        with patch("src.tasks.update_analysis", new_callable=AsyncMock), \
             patch("src.tasks.create_analysis", new_callable=AsyncMock), \
             patch("src.tasks.pdf_extractor.is_scanned_pdf", side_effect=Exception("Error")), \
             patch("pathlib.Path.is_file", return_value=False), \
             patch("pathlib.Path.unlink") as mock_unlink:

            await process_pdf(task_id, file_path)

            mock_unlink.assert_not_called()
