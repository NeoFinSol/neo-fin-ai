"""Tests for analysis/nlp_analysis.py — covers missing branches."""
import pytest
from unittest.mock import AsyncMock, patch

from src.analysis.nlp_analysis import (
    analyze_narrative,
    _extract_narrative,
    _parse_llm_json,
    _ensure_list,
    _empty_result,
)


class TestAnalyzeNarrative:
    @pytest.mark.asyncio
    async def test_empty_text_returns_empty(self):
        result = await analyze_narrative("")
        assert result == {"risks": [], "key_factors": [], "recommendations": []}

    @pytest.mark.asyncio
    async def test_ai_returns_valid_json(self):
        import json
        payload = {"risks": ["risk1"], "key_factors": ["factor1"], "recommendations": ["rec1"]}
        with patch("src.analysis.nlp_analysis.ai_service") as mock_ai:
            mock_ai.invoke = AsyncMock(return_value=json.dumps(payload))
            result = await analyze_narrative("Some financial text here")
            assert result["risks"] == ["risk1"]
            assert result["key_factors"] == ["factor1"]
            assert result["recommendations"] == ["rec1"]

    @pytest.mark.asyncio
    async def test_ai_returns_none_gives_empty(self):
        with patch("src.analysis.nlp_analysis.ai_service") as mock_ai:
            mock_ai.invoke = AsyncMock(return_value=None)
            result = await analyze_narrative("Some text")
            assert result == {"risks": [], "key_factors": [], "recommendations": []}

    @pytest.mark.asyncio
    async def test_ai_returns_invalid_json_gives_empty(self):
        with patch("src.analysis.nlp_analysis.ai_service") as mock_ai:
            mock_ai.invoke = AsyncMock(return_value="not json at all !!!")
            result = await analyze_narrative("Some text")
            assert result == {"risks": [], "key_factors": [], "recommendations": []}

    @pytest.mark.asyncio
    async def test_ai_exception_gives_empty(self):
        with patch("src.analysis.nlp_analysis.ai_service") as mock_ai:
            mock_ai.invoke = AsyncMock(side_effect=Exception("AI down"))
            result = await analyze_narrative("Some text")
            assert result == {"risks": [], "key_factors": [], "recommendations": []}

    @pytest.mark.asyncio
    async def test_ai_returns_json_in_text(self):
        """AI response with JSON embedded in text."""
        with patch("src.analysis.nlp_analysis.ai_service") as mock_ai:
            mock_ai.invoke = AsyncMock(
                return_value='Here is the analysis: {"risks": ["r1"], "key_factors": [], "recommendations": []}'
            )
            result = await analyze_narrative("Some text")
            assert result["risks"] == ["r1"]


class TestExtractNarrative:
    def test_finds_keyword_and_extracts(self):
        text = "Intro text. Пояснительная записка к бухгалтерской отчётности. Details here."
        result = _extract_narrative(text)
        assert "Пояснительная записка" in result

    def test_no_keyword_returns_full_text(self):
        text = "Just some random financial text without keywords."
        result = _extract_narrative(text)
        assert result == text

    def test_limits_to_8000_chars(self):
        keyword = "пояснительная записка"
        text = keyword + " " + "x" * 10000
        result = _extract_narrative(text)
        assert len(result) <= 8001  # keyword + 8000

    def test_notes_to_financial_keyword(self):
        text = "Some text. Notes to the financial statements. More text."
        result = _extract_narrative(text)
        assert "Notes to the financial" in result


class TestParseLlmJson:
    def test_valid_json_parsed(self):
        result = _parse_llm_json('{"risks": ["r1"]}')
        assert result == {"risks": ["r1"]}

    def test_json_in_text_extracted(self):
        result = _parse_llm_json('Some text {"risks": []} more text')
        assert result == {"risks": []}

    def test_invalid_json_returns_none(self):
        result = _parse_llm_json("not json at all")
        assert result is None

    def test_empty_string_returns_none(self):
        result = _parse_llm_json("")
        assert result is None

    def test_none_returns_none(self):
        result = _parse_llm_json(None)
        assert result is None


class TestEnsureList:
    def test_list_returned_as_is(self):
        assert _ensure_list(["a", "b"]) == ["a", "b"]

    def test_none_returns_empty(self):
        assert _ensure_list(None) == []

    def test_string_wrapped_in_list(self):
        assert _ensure_list("single") == ["single"]

    def test_int_wrapped_in_list(self):
        assert _ensure_list(42) == ["42"]

    def test_list_items_converted_to_str(self):
        assert _ensure_list([1, 2, 3]) == ["1", "2", "3"]
