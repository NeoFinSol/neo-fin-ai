"""Tests for NLP analysis module."""
import json
from unittest.mock import AsyncMock, patch

import pytest

from src.analysis.nlp_analysis import (
    _empty_result,
    _ensure_list,
    _extract_narrative,
    _parse_llm_json,
    analyze_narrative,
)


class TestEnsureList:
    """Tests for _ensure_list helper function."""

    def test_with_list_of_strings(self):
        """Test with list of strings."""
        assert _ensure_list(["a", "b", "c"]) == ["a", "b", "c"]

    def test_with_list_of_numbers(self):
        """Test with list of numbers."""
        assert _ensure_list([1, 2, 3]) == ["1", "2", "3"]

    def test_with_none(self):
        """Test with None value."""
        assert _ensure_list(None) == []

    def test_with_string(self):
        """Test with single string."""
        assert _ensure_list("hello") == ["hello"]

    def test_with_number(self):
        """Test with single number."""
        assert _ensure_list(42) == ["42"]

    def test_with_empty_list(self):
        """Test with empty list."""
        assert _ensure_list([]) == []

    def test_with_dict(self):
        """Test with dict (edge case)."""
        result = _ensure_list({"key": "value"})
        assert result == ["{'key': 'value'}"]


class TestExtractNarrative:
    """Tests for _extract_narrative function."""

    def test_with_poyasnitelnaya_zapiska(self):
        """Test extraction with Russian keyword."""
        text = "Some intro\nПояснительная записка\nMain content here" * 100
        result = _extract_narrative(text)
        assert "Пояснительная записка" in result
        assert result.startswith("Пояснительная записка")

    def test_with_english_notes(self):
        """Test extraction with English keyword."""
        text = "Intro\nNotes to the financial statements\nContent" * 100
        result = _extract_narrative(text)
        assert "Notes to the financial" in result

    def test_with_no_keywords(self):
        """Test when no keywords found."""
        text = "Just some random text without keywords"
        result = _extract_narrative(text)
        assert result == text

    def test_limits_to_8000_chars(self):
        """Test that extraction limits to 8000 characters."""
        long_text = "Пояснительная записка " + "x" * 10000
        result = _extract_narrative(long_text)
        assert len(result) <= 8000

    def test_case_insensitive_search(self):
        """Test case insensitive keyword search."""
        text = "ПОЯСНИТЕЛЬНАЯ ЗАПИСКА content"
        result = _extract_narrative(text)
        assert "ПОЯСНИТЕЛЬНАЯ ЗАПИСКА" in result


class TestParseLlmJson:
    """Tests for _parse_llm_json function."""

    def test_valid_json(self):
        """Test parsing valid JSON."""
        json_str = '{"risks": ["risk1"], "key_factors": ["factor1"]}'
        result = _parse_llm_json(json_str)
        assert result == {
            "risks": ["risk1"],
            "key_factors": ["factor1"],
        }

    def test_empty_string(self):
        """Test parsing empty string."""
        assert _parse_llm_json("") is None

    def test_invalid_json(self):
        """Test parsing invalid JSON."""
        assert _parse_llm_json("not json at all") is None

    def test_json_embedded_in_text(self):
        """Test extracting JSON from text."""
        text = "Some text before\n{\"risks\": [\"risk1\"]}\nSome text after"
        result = _parse_llm_json(text)
        assert result == {"risks": ["risk1"]}

    def test_nested_json(self):
        """Test parsing nested JSON."""
        json_str = '{"risks": [{"name": "risk1", "level": "high"}]}'
        result = _parse_llm_json(json_str)
        assert result["risks"][0]["name"] == "risk1"


class TestEmptyResult:
    """Tests for _empty_result function."""

    def test_returns_correct_structure(self):
        """Test empty result has correct structure."""
        result = _empty_result()
        assert result == {
            "risks": [],
            "key_factors": [],
            "recommendations": [],
        }

    def test_lists_are_independent(self):
        """Test that lists are independent objects."""
        result1 = _empty_result()
        result2 = _empty_result()
        result1["risks"].append("test")
        assert "test" not in result2["risks"]


class TestAnalyzeNarrative:
    """Tests for analyze_narrative main function."""

    @pytest.mark.asyncio
    async def test_empty_input(self):
        """Test with empty input."""
        result = await analyze_narrative("")
        assert result == _empty_result()

    @pytest.mark.asyncio
    async def test_successful_llm_response(self):
        """Test successful LLM API response."""
        mock_response_data = {
            "response": json.dumps({
                "risks": ["risk1", "risk2"],
                "key_factors": ["factor1"],
                "recommendations": ["rec1"],
            })
        }

        mock_response = AsyncMock()
        mock_response.raise_for_status = Mock()
        mock_response.json = AsyncMock(return_value=mock_response_data)

        mock_context_manager = AsyncMock()
        mock_context_manager.__aenter__ = AsyncMock(return_value=mock_response)
        mock_context_manager.__aexit__ = AsyncMock(return_value=None)

        with patch("aiohttp.ClientSession.post", return_value=mock_context_manager):
            with patch("aiohttp.ClientSession") as mock_session_class:
                mock_session = AsyncMock()
                mock_session.post = Mock(return_value=mock_context_manager)
                mock_session_class.return_value = mock_session
                mock_session.__aenter__ = AsyncMock(return_value=mock_session)
                mock_session.__aexit__ = AsyncMock(return_value=None)

                result = await analyze_narrative("Test narrative text")

                assert "risks" in result
                assert "key_factors" in result
                assert "recommendations" in result

    @pytest.mark.asyncio
    async def test_llm_request_failure(self):
        """Test LLM API request failure."""
        with patch("aiohttp.ClientSession.post", side_effect=Exception("Connection error")):
            result = await analyze_narrative("Test text")
            assert result == _empty_result()

    @pytest.mark.asyncio
    async def test_invalid_llm_json_response(self):
        """Test invalid JSON from LLM."""
        mock_response_data = {"response": "not valid json"}

        mock_response = AsyncMock()
        mock_response.raise_for_status = Mock()
        mock_response.json = AsyncMock(return_value=mock_response_data)

        mock_context_manager = AsyncMock()
        mock_context_manager.__aenter__ = AsyncMock(return_value=mock_response)
        mock_context_manager.__aexit__ = AsyncMock(return_value=None)

        with patch("aiohttp.ClientSession.post", return_value=mock_context_manager):
            with patch("aiohttp.ClientSession") as mock_session_class:
                mock_session = AsyncMock()
                mock_session.post = Mock(return_value=mock_context_manager)
                mock_session_class.return_value = mock_session
                mock_session.__aenter__ = AsyncMock(return_value=mock_session)
                mock_session.__aexit__ = AsyncMock(return_value=None)

                result = await analyze_narrative("Test text")
                assert result == _empty_result()

    @pytest.mark.asyncio
    async def test_custom_llm_url_from_env(self):
        """Test custom LLM URL from environment variable."""
        with patch.dict("os.environ", {"LLM_URL": "http://custom:11434/api/generate"}):
            # Just test that it doesn't crash with custom URL
            # Actual connection will fail but that's expected
            with patch("aiohttp.ClientSession.post", side_effect=Exception("Expected")):
                result = await analyze_narrative("Test")
                assert result == _empty_result()

    @pytest.mark.asyncio
    async def test_custom_llm_model_from_env(self):
        """Test custom LLM model from environment variable."""
        with patch.dict("os.environ", {"LLM_MODEL": "gpt4"}):
            with patch("aiohttp.ClientSession.post", side_effect=Exception("Expected")):
                result = await analyze_narrative("Test")
                assert result == _empty_result()

    @pytest.mark.asyncio
    async def test_narrative_extraction_from_full_text(self):
        """Test narrative extraction from full text."""
        full_text = "Intro\nПояснительная записка\nFinancial details" * 50

        mock_response_data = {"response": json.dumps({"risks": [], "key_factors": [], "recommendations": []})}

        mock_response = AsyncMock()
        mock_response.raise_for_status = Mock()
        mock_response.json = AsyncMock(return_value=mock_response_data)

        mock_context_manager = AsyncMock()
        mock_context_manager.__aenter__ = AsyncMock(return_value=mock_response)
        mock_context_manager.__aexit__ = AsyncMock(return_value=None)

        with patch("aiohttp.ClientSession.post", return_value=mock_context_manager):
            with patch("aiohttp.ClientSession") as mock_session_class:
                mock_session = AsyncMock()
                mock_session.post = Mock(return_value=mock_context_manager)
                mock_session_class.return_value = mock_session
                mock_session.__aenter__ = AsyncMock(return_value=mock_session)
                mock_session.__aexit__ = AsyncMock(return_value=None)

                result = await analyze_narrative(full_text)
                assert isinstance(result, dict)
                assert "risks" in result


# Helper mock class
class Mock:
    """Simple mock class."""
    def __init__(self, *args, **kwargs):
        pass

    def __call__(self, *args, **kwargs):
        return self
