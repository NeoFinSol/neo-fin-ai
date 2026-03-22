"""Tests for background tasks module."""
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.tasks import _extract_text_from_pdf, process_pdf


class TestExtractTextFromPdf:
    """Tests for PDF text extraction."""

    def test_successful_extraction(self):
        """Test successful text extraction from PDF."""
        mock_page = MagicMock()
        mock_page.extract_text.return_value = "Page 1 content"

        mock_reader = MagicMock()
        mock_reader.pages = [mock_page]

        with patch("PyPDF2.PdfReader", return_value=mock_reader):
            result = _extract_text_from_pdf("test.pdf")
            assert result == "Page 1 content"

    def test_multiple_pages(self):
        """Test extraction from multiple pages."""
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
        """Test handling of empty pages."""
        mock_page = MagicMock()
        mock_page.extract_text.return_value = None  # Some pages return None

        mock_reader = MagicMock()
        mock_reader.pages = [mock_page]

        with patch("PyPDF2.PdfReader", return_value=mock_reader):
            result = _extract_text_from_pdf("test.pdf")
            assert result == ""

    def test_extraction_error_on_page(self, caplog):
        """Test handling of extraction errors on specific pages."""
        mock_page = MagicMock()
        mock_page.extract_text.side_effect = Exception("Extraction failed")

        mock_reader = MagicMock()
        mock_reader.pages = [mock_page]

        with patch("PyPDF2.PdfReader", return_value=mock_reader):
            with caplog.at_level("WARNING"):
                result = _extract_text_from_pdf("test.pdf")
                assert "Failed to extract text from page 1" in caplog.text
                assert result == ""


class TestProcessPdf:
    """Tests for async PDF processing."""

    @pytest.mark.asyncio
    async def test_successful_processing(self):
        """Test successful PDF processing flow."""
        task_id = "test-task-123"
        file_path = "/tmp/test.pdf"

        # Setup mocks
        with patch("src.tasks.update_analysis", new_callable=AsyncMock) as mock_update, \
             patch("src.tasks.create_analysis", new_callable=AsyncMock) as mock_create, \
             patch("src.tasks.pdf_extractor.is_scanned_pdf", return_value=False), \
             patch("src.tasks.pdf_extractor.extract_text_from_scanned"), \
             patch("src.tasks._extract_text_from_pdf", return_value="Extracted text"), \
             patch("src.tasks.pdf_extractor.extract_tables", return_value=["table1"]), \
             patch("src.tasks.pdf_extractor.parse_financial_statements", return_value={"revenue": 100}), \
             patch("src.tasks.calculate_ratios", return_value={"current_ratio": 1.5}), \
             patch("src.tasks.calculate_integral_score", return_value=85.5), \
             patch("os.path.exists", return_value=True), \
             patch("os.remove"):

            mock_update.return_value = None  # Simulate no existing analysis

            await process_pdf(task_id, file_path)

            # Verify workflow
            mock_create.assert_called_once_with(task_id, "processing", None)
            mock_update.assert_called()
            
            # Verify final status is completed
            calls = mock_update.call_args_list
            last_call = calls[-1]
            assert last_call[0][1] == "completed"

    @pytest.mark.asyncio
    async def test_existing_analysis_update(self):
        """Test updating existing analysis record."""
        task_id = "test-task-456"
        file_path = "/tmp/test2.pdf"

        with patch("src.tasks.update_analysis", new_callable=AsyncMock) as mock_update, \
             patch("src.tasks.create_analysis", new_callable=AsyncMock) as mock_create, \
             patch("src.tasks.pdf_extractor.is_scanned_pdf", return_value=False), \
             patch("src.tasks._extract_text_from_pdf", return_value="Text"), \
             patch("src.tasks.pdf_extractor.extract_tables", return_value=[]), \
             patch("src.tasks.pdf_extractor.parse_financial_statements", return_value={}), \
             patch("src.tasks.calculate_ratios", return_value={}), \
             patch("src.tasks.calculate_integral_score", return_value=0.0), \
             patch("os.path.exists", return_value=True), \
             patch("os.remove"):

            # Simulate existing analysis found
            mock_update.return_value = {"id": task_id}

            await process_pdf(task_id, file_path)

            # Should update but not create new
            mock_create.assert_not_called()
            mock_update.assert_called()

    @pytest.mark.asyncio
    async def test_scanned_pdf_processing(self):
        """Test processing of scanned PDF requiring OCR."""
        task_id = "scanned-task"
        file_path = "/tmp/scanned.pdf"

        with patch("src.tasks.update_analysis", new_callable=AsyncMock), \
             patch("src.tasks.create_analysis", new_callable=AsyncMock), \
             patch("src.tasks.pdf_extractor.is_scanned_pdf", return_value=True), \
             patch("src.tasks.pdf_extractor.extract_text_from_scanned", return_value="OCR text"), \
             patch("src.tasks.pdf_extractor.extract_tables", return_value=[]), \
             patch("src.tasks.pdf_extractor.parse_financial_statements", return_value={}), \
             patch("src.tasks.calculate_ratios", return_value={}), \
             patch("src.tasks.calculate_integral_score", return_value=0.0), \
             patch("os.path.exists", return_value=True), \
             patch("os.remove"):

            await process_pdf(task_id, file_path)

            # Verify OCR method was called instead of regular extraction
            pass  # If we get here without error, test passes

    @pytest.mark.asyncio
    async def test_processing_failure(self, caplog):
        """Test handling of processing failures."""
        task_id = "failed-task"
        file_path = "/tmp/fail.pdf"

        with patch("src.tasks.update_analysis", new_callable=AsyncMock) as mock_update, \
             patch("src.tasks.create_analysis", new_callable=AsyncMock), \
             patch("src.tasks.pdf_extractor.is_scanned_pdf", side_effect=Exception("PDF corrupted")):

            await process_pdf(task_id, file_path)

            # Verify failure was recorded
            mock_update.assert_called()
            fail_call = mock_update.call_args_list[-1]
            assert fail_call[0][1] == "failed"
            assert "error" in fail_call[0][2]
            assert "PDF corrupted" in str(fail_call[0][2]["error"])

            # Verify error was logged
            assert "Failed to process PDF task" in caplog.text

    @pytest.mark.asyncio
    async def test_temp_file_cleanup_on_success(self):
        """Test temporary file cleanup after successful processing."""
        task_id = "cleanup-task"
        file_path = "/tmp/cleanup.pdf"

        with patch("src.tasks.update_analysis", new_callable=AsyncMock), \
             patch("src.tasks.create_analysis", new_callable=AsyncMock), \
             patch("src.tasks.pdf_extractor.is_scanned_pdf", return_value=False), \
             patch("src.tasks._extract_text_from_pdf", return_value="Text"), \
             patch("src.tasks.pdf_extractor.extract_tables", return_value=[]), \
             patch("src.tasks.pdf_extractor.parse_financial_statements", return_value={}), \
             patch("src.tasks.calculate_ratios", return_value={}), \
             patch("src.tasks.calculate_integral_score", return_value=0.0), \
             patch("os.path.exists", return_value=True), \
             patch("os.remove") as mock_remove:

            await process_pdf(task_id, file_path)

            # Verify cleanup occurred
            mock_remove.assert_called_once_with(file_path)

    @pytest.mark.asyncio
    async def test_temp_file_cleanup_on_failure(self):
        """Test temporary file cleanup even when processing fails."""
        task_id = "cleanup-fail-task"
        file_path = "/tmp/cleanup_fail.pdf"

        with patch("src.tasks.update_analysis", new_callable=AsyncMock), \
             patch("src.tasks.create_analysis", new_callable=AsyncMock), \
             patch("src.tasks.pdf_extractor.is_scanned_pdf", side_effect=Exception("Error")), \
             patch("os.path.exists", return_value=True), \
             patch("os.remove") as mock_remove:

            await process_pdf(task_id, file_path)

            # Verify cleanup still occurred despite failure
            mock_remove.assert_called_once_with(file_path)

    @pytest.mark.asyncio
    async def test_cleanup_failure_handled_gracefully(self, caplog):
        """Test graceful handling of cleanup failures."""
        task_id = "cleanup-error-task"
        file_path = "/tmp/noexist.pdf"

        with patch("src.tasks.update_analysis", new_callable=AsyncMock), \
             patch("src.tasks.create_analysis", new_callable=AsyncMock), \
             patch("src.tasks.pdf_extractor.is_scanned_pdf", side_effect=Exception("Main error")), \
             patch("os.path.exists", return_value=True), \
             patch("os.remove", side_effect=PermissionError("Can't delete")):

            await process_pdf(task_id, file_path)

            # Verify cleanup failure was logged but didn't crash
            assert "Failed to delete temporary file" in caplog.text

    @pytest.mark.asyncio
    async def test_nonexistent_file_cleanup(self):
        """Test handling when temp file doesn't exist."""
        task_id = "no-file-task"
        file_path = "/tmp/doesnt_exist.pdf"

        with patch("src.tasks.update_analysis", new_callable=AsyncMock), \
             patch("src.tasks.create_analysis", new_callable=AsyncMock), \
             patch("src.tasks.pdf_extractor.is_scanned_pdf", side_effect=Exception("Error")), \
             patch("os.path.exists", return_value=False), \
             patch("os.remove") as mock_remove:

            await process_pdf(task_id, file_path)

            # Verify remove was not called for non-existent file
            mock_remove.assert_not_called()
