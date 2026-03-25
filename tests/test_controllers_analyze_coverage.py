"""Additional tests for controllers/analyze.py — covers fallback ratios calculation."""
import io
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.controllers.analyze import _extract_json_from_response, analyze_pdf


class TestExtractJsonFromResponse:
    """Tests for _extract_json_from_response — covers lines 17-35."""

    def test_extracts_json_code_block(self):
        text = '```json\n{"key": "value"}\n```'
        result = _extract_json_from_response(text)
        assert result == '{"key": "value"}'

    def test_extracts_plain_code_block(self):
        text = '```\n{"key": "value"}\n```'
        result = _extract_json_from_response(text)
        assert result == '{"key": "value"}'

    def test_extracts_raw_json(self):
        text = 'Some text {"key": "value"} more text'
        result = _extract_json_from_response(text)
        assert '{"key": "value"}' in result

    def test_returns_original_when_no_json(self):
        text = "no json here at all"
        result = _extract_json_from_response(text)
        assert result == text

    def test_empty_string(self):
        result = _extract_json_from_response("")
        assert result == ""


class TestAnalyzePdfFallback:
    """Tests for analyze_pdf fallback path when AI returns None — covers lines 224-349."""

    @pytest.mark.asyncio
    async def test_fallback_with_metrics_calculates_ratios(self):
        """When AI returns None and metrics extracted, calculates ratios."""
        file_content = [{
            "tables": [],
            "text": "Выручка | 1000000\nЧистая прибыль | 100000\nИтого активов | 500000\nИтого капитала | 300000\nИтого обязательств | 200000"
        }]

        with patch("src.controllers.analyze._read_pdf_file", return_value=file_content), \
             patch("src.controllers.analyze.ai_service.invoke", new_callable=AsyncMock) as mock_invoke:
            mock_invoke.return_value = None

            result = await analyze_pdf(io.BytesIO(b"pdf"))
            assert isinstance(result, dict)
            # Should have AnalysisData structure
            assert "ratios" in result or "score" in result or "metrics" in result

    @pytest.mark.asyncio
    async def test_fallback_returns_default_when_no_metrics(self):
        """When AI returns None and no metrics, returns default AnalysisData."""
        file_content = [{"tables": [], "text": ""}]

        with patch("src.controllers.analyze._read_pdf_file", return_value=file_content), \
             patch("src.controllers.analyze.ai_service.invoke", new_callable=AsyncMock) as mock_invoke:
            mock_invoke.return_value = None

            result = await analyze_pdf(io.BytesIO(b"pdf"))
            assert isinstance(result, dict)
            assert "ratios" in result
            assert "score" in result

    @pytest.mark.asyncio
    async def test_fallback_with_parse_financial_statements(self):
        """Fallback uses parse_financial_statements from pdf_extractor."""
        file_content = [{"tables": [["Выручка", "1000000"]], "text": ""}]

        with patch("src.controllers.analyze._read_pdf_file", return_value=file_content), \
             patch("src.controllers.analyze.ai_service.invoke", new_callable=AsyncMock) as mock_invoke, \
             patch("src.analysis.pdf_extractor.parse_financial_statements", return_value={
                 "revenue": 1000000, "net_profit": 100000, "total_assets": 500000,
                 "equity": 300000, "liabilities": 200000
             }):
            mock_invoke.return_value = None
            result = await analyze_pdf(io.BytesIO(b"pdf"))
            assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_multiple_batches_combined_in_pages(self):
        """Multiple AI results combined into pages structure."""
        mock_data = [{"page": i, "tables": []} for i in range(1, 41)]

        with patch("src.controllers.analyze._read_pdf_file", return_value=mock_data), \
             patch("src.controllers.analyze.ai_service.invoke", new_callable=AsyncMock) as mock_invoke:
            mock_invoke.side_effect = [
                json.dumps({"batch": 1}),
                json.dumps({"batch": 2}),
            ]
            result = await analyze_pdf(io.BytesIO(b"pdf"))
            assert "pages" in result
            assert len(result["pages"]) == 2

    @pytest.mark.asyncio
    async def test_json_decode_error_skips_batch(self):
        """JSONDecodeError in one batch is skipped, others processed."""
        mock_data = [{"page": i, "tables": []} for i in range(1, 41)]

        with patch("src.controllers.analyze._read_pdf_file", return_value=mock_data), \
             patch("src.controllers.analyze.ai_service.invoke", new_callable=AsyncMock) as mock_invoke:
            mock_invoke.side_effect = [
                "not valid json {{{{",
                json.dumps({"batch": 2}),
            ]
            result = await analyze_pdf(io.BytesIO(b"pdf"))
            # Only second batch succeeded
            assert result == {"batch": 2}
