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
        mock_page = MagicMock()
        mock_page.extract_tables.return_value = [
            [["Header1", "Header2"], ["Value1", "Value2"]],
            [["Data1", "Data2"]]
        ]
        
        mock_pdf = MagicMock()
        mock_pdf.pages = [mock_page]
        mock_pdf.__enter__ = MagicMock(return_value=mock_pdf)
        mock_pdf.__exit__ = MagicMock(return_value=False)

        with patch("pdfplumber.open", return_value=mock_pdf):
            file = io.BytesIO(b"fake pdf content")
            result = _read_pdf_file(file)
            
            assert len(result) == 1
            assert result[0]["page"] == 1
            assert len(result[0]["tables"]) == 2
            assert result[0]["tables"][0]["table_index"] == 0

    def test_empty_tables_handling(self):
        """Test handling of empty tables."""
        mock_page = MagicMock()
        mock_page.extract_tables.return_value = [None, []]
        
        mock_pdf = MagicMock()
        mock_pdf.pages = [mock_page]
        mock_pdf.__enter__ = MagicMock(return_value=mock_pdf)
        mock_pdf.__exit__ = MagicMock(return_value=False)

        with patch("pdfplumber.open", return_value=mock_pdf):
            file = io.BytesIO(b"fake pdf")
            result = _read_pdf_file(file)
            
            assert len(result) == 1
            assert len(result[0]["tables"]) == 0  # Empty tables filtered out

    def test_cell_cleaning(self):
        """Test that cells are properly cleaned (stripped)."""
        mock_page = MagicMock()
        mock_page.extract_tables.return_value = [
            [[" Header1 ", "  "], [None, "Value2"]]
        ]
        
        mock_pdf = MagicMock()
        mock_pdf.pages = [mock_page]
        mock_pdf.__enter__ = MagicMock(return_value=mock_pdf)
        mock_pdf.__exit__ = MagicMock(return_value=False)

        with patch("pdfplumber.open", return_value=mock_pdf):
            file = io.BytesIO(b"fake pdf")
            result = _read_pdf_file(file)
            
            # Check that cells are stripped and None becomes ""
            rows = result[0]["tables"][0]["rows"]
            assert rows[0][0] == "Header1"  # Stripped
            assert rows[0][1] == ""  # Empty string from whitespace
            assert rows[1][0] == ""  # None converted to ""

    def test_multiple_pages(self):
        """Test processing multiple pages."""
        page1 = MagicMock()
        page1.extract_tables.return_value = [[["Page1Table"]]]
        
        page2 = MagicMock()
        page2.extract_tables.return_value = [[["Page2Table"]]]
        
        mock_pdf = MagicMock()
        mock_pdf.pages = [page1, page2]
        mock_pdf.__enter__ = MagicMock(return_value=mock_pdf)
        mock_pdf.__exit__ = MagicMock(return_value=False)

        with patch("pdfplumber.open", return_value=mock_pdf):
            file = io.BytesIO(b"fake pdf")
            result = _read_pdf_file(file)
            
            assert len(result) == 2
            assert result[0]["page"] == 1
            assert result[1]["page"] == 2

    def test_extraction_error(self):
        """Test handling of extraction errors."""
        with patch("pdfplumber.open", side_effect=Exception("PDF corrupted")):
            file = io.BytesIO(b"fake pdf")
            with pytest.raises(ValueError, match="PDF table extraction failed"):
                _read_pdf_file(file)


class TestAnalyzePdf:
    """Tests for async PDF analysis."""

    @pytest.mark.asyncio
    async def test_successful_analysis_with_bytesio(self):
        """Test successful analysis with BytesIO input."""
        mock_file = io.BytesIO(b"fake pdf content")
        
        with patch("src.controllers.analyze._read_pdf_file", return_value=[{"page": 1, "tables": []}]), \
             patch("src.controllers.analyze.agent") as mock_agent:
            
            mock_agent.invoke = AsyncMock(return_value=json.dumps({"result": "success"}))
            
            result = await analyze_pdf(mock_file)
            
            assert result == {"result": "success"}
            mock_agent.invoke.assert_called_once()

    @pytest.mark.asyncio
    async def test_binaryio_conversion(self):
        """Test conversion of BinaryIO to BytesIO."""
        mock_binary_file = MagicMock()
        mock_binary_file.read.return_value = b"pdf content"
        
        with patch("src.controllers.analyze._read_pdf_file", return_value=[{"page": 1, "tables": []}]), \
             patch("src.controllers.analyze.agent") as mock_agent:
            
            mock_agent.invoke = AsyncMock(return_value=json.dumps({"result": "ok"}))
            
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
             patch("src.controllers.analyze.agent") as mock_agent:
            
            mock_agent.invoke = AsyncMock(return_value=json.dumps({"page_result": "ok"}))
            
            result = await analyze_pdf(io.BytesIO(b"pdf"))
            
            # Should be called 3 times: pages 0-19, 20-39, 40-49
            assert mock_agent.invoke.call_count == 3
            
            # Verify first call includes pages 1-20
            first_call_args = mock_agent.invoke.call_args_list[0]
            prompt = first_call_args[1]["input"]["tool_input"]
            assert "PAGE 1" in prompt
            assert "PAGE 20" in prompt

    @pytest.mark.asyncio
    async def test_ai_timeout(self):
        """Test AI service timeout handling."""
        import asyncio
        
        mock_file = io.BytesIO(b"pdf")
        
        with patch("src.controllers.analyze._read_pdf_file", return_value=[{"page": 1, "tables": []}]), \
             patch("src.controllers.analyze.agent") as mock_agent:
            
            mock_agent.invoke = AsyncMock(side_effect=asyncio.TimeoutError())
            
            with pytest.raises(HTTPException) as exc_info:
                await analyze_pdf(mock_file)
            
            assert exc_info.value.status_code == 504
            assert "timeout" in str(exc_info.value.detail).lower()

    @pytest.mark.asyncio
    async def test_ai_processing_error(self):
        """Test AI processing error handling."""
        mock_file = io.BytesIO(b"pdf")
        
        with patch("src.controllers.analyze._read_pdf_file", return_value=[{"page": 1, "tables": []}]), \
             patch("src.controllers.analyze.agent") as mock_agent:
            
            mock_agent.invoke = AsyncMock(side_effect=Exception("AI service unavailable"))
            
            with pytest.raises(HTTPException) as exc_info:
                await analyze_pdf(mock_file)
            
            assert exc_info.value.status_code == 500
            assert "AI processing failed" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_null_ai_response(self):
        """Test handling of null AI response."""
        mock_file = io.BytesIO(b"pdf")
        
        with patch("src.controllers.analyze._read_pdf_file", return_value=[{"page": 1, "tables": []}]), \
             patch("src.controllers.analyze.agent") as mock_agent:
            
            mock_agent.invoke = AsyncMock(return_value=None)
            
            result = await analyze_pdf(mock_file)
            
            assert result == {}  # Empty result when AI returns None

    @pytest.mark.asyncio
    async def test_invalid_json_ai_response(self):
        """Test handling of invalid JSON from AI."""
        mock_file = io.BytesIO(b"pdf")
        
        with patch("src.controllers.analyze._read_pdf_file", return_value=[{"page": 1, "tables": []}]), \
             patch("src.controllers.analyze.agent") as mock_agent:
            
            mock_agent.invoke = AsyncMock(return_value="not valid json")
            
            with pytest.raises(HTTPException) as exc_info:
                await analyze_pdf(mock_file)
            
            assert exc_info.value.status_code == 500

    @pytest.mark.asyncio
    async def test_multiple_page_results_combined(self):
        """Test combining results from multiple page batches."""
        mock_data = [{"page": i, "tables": []} for i in range(1, 41)]  # 40 pages
        
        with patch("src.controllers.analyze._read_pdf_file", return_value=mock_data), \
             patch("src.controllers.analyze.agent") as mock_agent:
            
            # Return different results for each batch
            mock_agent.invoke = AsyncMock(side_effect=[
                json.dumps({"batch": 1}),
                json.dumps({"batch": 2})
            ])
            
            result = await analyze_pdf(io.BytesIO(b"pdf"))
            
            # Multiple batches should be combined
            assert "pages" in result
            assert len(result["pages"]) == 2
            assert result["pages"][0] == {"batch": 1}
            assert result["pages"][1] == {"batch": 2}
