"""Tests for analyze controller."""
import io
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from src.controllers.analyze import _read_pdf_file, analyze_pdf


class TestReadPdfFile:
    """Tests for PDF file reading."""

    def test_successful_table_extraction(self):
        """Test successful table extraction from PDF."""
        mock_tables = [{"flavor": "lattice", "rows": [["Header1", "Header2"], ["Value1", "Value2"]]}]

        with patch("src.analysis.pdf_extractor.extract_tables", return_value=mock_tables), \
             patch("pdfplumber.open") as mock_plumber:
            mock_pdf = MagicMock()
            mock_pdf.__enter__ = MagicMock(return_value=mock_pdf)
            mock_pdf.__exit__ = MagicMock(return_value=False)
            mock_pdf.pages = []
            mock_plumber.return_value = mock_pdf

            file = io.BytesIO(b"%PDF-1.4 fake content")
            result = _read_pdf_file(file)

            assert len(result) == 1
            assert "tables" in result[0]
            assert result[0]["tables"] == mock_tables

    def test_empty_tables_handling(self):
        """Test handling of empty tables."""
        with patch("src.analysis.pdf_extractor.extract_tables", return_value=[]), \
             patch("pdfplumber.open") as mock_plumber:
            mock_pdf = MagicMock()
            mock_pdf.__enter__ = MagicMock(return_value=mock_pdf)
            mock_pdf.__exit__ = MagicMock(return_value=False)
            mock_pdf.pages = []
            mock_plumber.return_value = mock_pdf

            file = io.BytesIO(b"%PDF-1.4 fake")
            result = _read_pdf_file(file)

            assert len(result) == 1
            assert result[0]["tables"] == []

    def test_cell_cleaning(self):
        """Test that text is extracted from pages."""
        mock_page = MagicMock()
        mock_page.extract_text.return_value = "  Some text  "

        with patch("src.analysis.pdf_extractor.extract_tables", return_value=[]), \
             patch("pdfplumber.open") as mock_plumber:
            mock_pdf = MagicMock()
            mock_pdf.__enter__ = MagicMock(return_value=mock_pdf)
            mock_pdf.__exit__ = MagicMock(return_value=False)
            mock_pdf.pages = [mock_page]
            mock_plumber.return_value = mock_pdf

            file = io.BytesIO(b"%PDF-1.4 fake")
            result = _read_pdf_file(file)

            assert "text" in result[0]

    def test_multiple_pages(self):
        """Test that text from multiple pages is combined."""
        page1 = MagicMock()
        page1.extract_text.return_value = "Page 1 text"
        page2 = MagicMock()
        page2.extract_text.return_value = "Page 2 text"

        with patch("src.analysis.pdf_extractor.extract_tables", return_value=[]), \
             patch("pdfplumber.open") as mock_plumber:
            mock_pdf = MagicMock()
            mock_pdf.__enter__ = MagicMock(return_value=mock_pdf)
            mock_pdf.__exit__ = MagicMock(return_value=False)
            mock_pdf.pages = [page1, page2]
            mock_plumber.return_value = mock_pdf

            file = io.BytesIO(b"%PDF-1.4 fake")
            result = _read_pdf_file(file)

            assert len(result) == 1  # _read_pdf_file returns one entry per call
            assert "Page 1 text" in result[0]["text"]

    def test_extraction_error(self):
        """Test handling of extraction errors."""
        with patch("src.analysis.pdf_extractor.extract_tables",
                   side_effect=Exception("PDF corrupted")):
            file = io.BytesIO(b"fake pdf")
            with pytest.raises(Exception):
                _read_pdf_file(file)


class TestAnalyzePdf:
    """Tests for async PDF analysis."""

    @pytest.mark.asyncio
    async def test_successful_analysis_with_bytesio(self):
        """Test successful analysis with BytesIO input."""
        mock_file = io.BytesIO(b"fake pdf content")

        with patch("src.controllers.analyze._read_pdf_file", return_value=[{"page": 1, "tables": []}]), \
             patch("src.controllers.analyze.ai_service") as mock_ai_service:

            mock_ai_service.invoke_with_retry = AsyncMock(return_value=json.dumps({"result": "success"}))

            result = await analyze_pdf(mock_file)

            assert result == {"result": "success"}
            mock_ai_service.invoke_with_retry.assert_called_once()

    @pytest.mark.asyncio
    async def test_binaryio_conversion(self):
        """Test conversion of BinaryIO to BytesIO."""
        mock_binary_file = MagicMock()
        mock_binary_file.read.return_value = b"pdf content"

        with patch("src.controllers.analyze._read_pdf_file", return_value=[{"page": 1, "tables": []}]), \
             patch("src.controllers.analyze.ai_service") as mock_ai_service:

            mock_ai_service.invoke_with_retry = AsyncMock(return_value=json.dumps({"result": "ok"}))

            result = await analyze_pdf(mock_binary_file)

            assert result == {"result": "ok"}
            mock_binary_file.read.assert_called_once()

    @pytest.mark.asyncio
    async def test_empty_binaryio_content(self):
        """Test handling of empty BinaryIO content."""
        mock_binary_file = MagicMock()
        mock_binary_file.read.return_value = b""
        
        with pytest.raises(HTTPException) as exc_info:
            await analyze_pdf(mock_binary_file)
        
        assert exc_info.value.status_code == 400
        assert "Invalid or corrupted PDF" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_invalid_pdf_raises_http_exception(self):
        """Test that invalid PDF raises HTTPException."""
        mock_file = io.BytesIO(b"invalid pdf")
        
        with patch("src.controllers.analyze._read_pdf_file", side_effect=ValueError("Invalid PDF")):
            with pytest.raises(HTTPException) as exc_info:
                await analyze_pdf(mock_file)
            
            assert exc_info.value.status_code == 400
            assert "Invalid or corrupted PDF" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_general_processing_error(self):
        """Test general processing error handling."""
        mock_file = io.BytesIO(b"pdf")
        
        with patch("src.controllers.analyze._read_pdf_file", side_effect=Exception("Unexpected error")):
            with pytest.raises(HTTPException) as exc_info:
                await analyze_pdf(mock_file)
            
            assert exc_info.value.status_code == 400
            assert "PDF processing failed" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_paged_processing_with_step(self):
        """Test processing in steps of 20 pages."""
        # Create mock data for 50 pages
        mock_data = [{"page": i, "tables": []} for i in range(1, 51)]

        with patch("src.controllers.analyze._read_pdf_file", return_value=mock_data), \
             patch("src.controllers.analyze.ai_service") as mock_ai_service:

            mock_ai_service.invoke_with_retry = AsyncMock(return_value=json.dumps({"page_result": "ok"}))

            result = await analyze_pdf(io.BytesIO(b"pdf"))

            # Should be called 3 times: pages 0-19, 20-39, 40-49
            assert mock_ai_service.invoke_with_retry.call_count == 3

            # Verify first call includes pages 1-20
            first_call_args = mock_ai_service.invoke_with_retry.call_args_list[0]
            prompt = first_call_args[1]["input"]["tool_input"]
            assert "PAGE 1" in prompt
            assert "PAGE 20" in prompt

    @pytest.mark.asyncio
    async def test_ai_timeout(self):
        """Test AI service timeout handling."""
        import asyncio

        mock_file = io.BytesIO(b"pdf")

        with patch("src.controllers.analyze._read_pdf_file", return_value=[{"page": 1, "tables": []}]), \
             patch("src.controllers.analyze.ai_service") as mock_ai_service:

            mock_ai_service.invoke_with_retry = AsyncMock(side_effect=asyncio.TimeoutError())

            with pytest.raises(HTTPException) as exc_info:
                await analyze_pdf(mock_file)

            assert exc_info.value.status_code == 504
            assert "timeout" in str(exc_info.value.detail).lower()

    @pytest.mark.asyncio
    async def test_ai_processing_error(self):
        """Test AI processing error handling."""
        mock_file = io.BytesIO(b"pdf")

        with patch("src.controllers.analyze._read_pdf_file", return_value=[{"page": 1, "tables": []}]), \
             patch("src.controllers.analyze.ai_service") as mock_ai_service:

            mock_ai_service.invoke_with_retry = AsyncMock(side_effect=Exception("AI service unavailable"))

            with pytest.raises(HTTPException) as exc_info:
                await analyze_pdf(mock_file)

            assert exc_info.value.status_code == 500
            assert "AI processing failed" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_null_ai_response(self):
        """Test handling of null AI response — returns AnalysisData fallback."""
        mock_file = io.BytesIO(b"pdf")

        with patch("src.controllers.analyze._read_pdf_file", return_value=[{"page": 1, "tables": [], "text": ""}]), \
             patch("src.controllers.analyze.ai_service") as mock_ai_service:

            mock_ai_service.invoke_with_retry = AsyncMock(return_value=None)

            result = await analyze_pdf(mock_file)

            # Should return AnalysisData structure (not empty dict)
            assert isinstance(result, dict)
            assert "ratios" in result
            assert "score" in result
            assert "metrics" in result

    @pytest.mark.asyncio
    async def test_invalid_json_ai_response(self):
        """Test handling of invalid JSON from AI — returns AnalysisData fallback."""
        mock_file = io.BytesIO(b"pdf")

        with patch("src.controllers.analyze._read_pdf_file", return_value=[{"page": 1, "tables": [], "text": ""}]), \
             patch("src.controllers.analyze.ai_service") as mock_ai_service:

            mock_ai_service.invoke_with_retry = AsyncMock(return_value="not valid json")

            result = await analyze_pdf(mock_file)

            # Should return AnalysisData structure (not empty dict)
            assert isinstance(result, dict)
            assert "ratios" in result
            assert "score" in result

    @pytest.mark.asyncio
    async def test_multiple_page_results_combined(self):
        """Test combining results from multiple page batches."""
        mock_data = [{"page": i, "tables": []} for i in range(1, 41)]  # 40 pages

        with patch("src.controllers.analyze._read_pdf_file", return_value=mock_data), \
             patch("src.controllers.analyze.ai_service") as mock_ai_service:

            # Return different results for each batch
            mock_ai_service.invoke_with_retry = AsyncMock(side_effect=[
                json.dumps({"batch": 1}),
                json.dumps({"batch": 2})
            ])

            result = await analyze_pdf(io.BytesIO(b"pdf"))

            # Multiple batches should be combined
            assert "pages" in result
            assert len(result["pages"]) == 2
            assert result["pages"][0] == {"batch": 1}
            assert result["pages"][1] == {"batch": 2}
