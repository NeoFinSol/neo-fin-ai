"""Tests for src/analysis/nlp_analysis.py."""
import json
from unittest.mock import AsyncMock, patch

import pytest

from src.analysis.nlp_analysis import (
    _empty_result,
    _ensure_list,
    _extract_narrative,
    _parse_llm_json,
    _prepare_narrative_for_llm,
    analyze_narrative,
)


class TestEnsureList:
    def test_with_list_of_strings(self):
        assert _ensure_list(["a", "b", "c"]) == ["a", "b", "c"]

    def test_with_list_of_numbers(self):
        assert _ensure_list([1, 2, 3]) == ["1", "2", "3"]

    def test_with_none(self):
        assert _ensure_list(None) == []

    def test_with_string(self):
        assert _ensure_list("hello") == ["hello"]

    def test_with_number(self):
        assert _ensure_list(42) == ["42"]

    def test_with_dict(self):
        assert _ensure_list({"key": "value"}) == ["{'key': 'value'}"]


class TestExtractNarrative:
    def test_with_poyasnitelnaya_zapiska(self):
        text = "Some intro\nПояснительная записка\nMain content here" * 100
        result = _extract_narrative(text)
        assert "Пояснительная записка" in result
        assert result.startswith("Пояснительная записка")

    def test_with_english_notes(self):
        text = "Intro\nNotes to the financial statements\nContent" * 100
        result = _extract_narrative(text)
        assert "Notes to the financial" in result

    def test_with_no_keywords(self):
        text = "Just some random text without keywords"
        assert _extract_narrative(text) == text

    def test_limits_to_8000_chars(self):
        long_text = "Пояснительная записка " + "x" * 10000
        result = _extract_narrative(long_text)
        assert len(result) <= 8000


class TestPrepareNarrativeForLlm:
    def test_compacts_and_limits_prompt(self):
        text = "\n".join(
            [
                "Страница 1",
                "Пояснительная записка",
                "Выручка компании составила 1 000 000 рублей",
                "Выручка компании составила 1 000 000 рублей",
                "Кредиторская задолженность выросла до 500 000 рублей",
                "2023",
            ]
        )

        prepared = _prepare_narrative_for_llm(text)

        assert "Выручка компании составила 1 000 000 рублей" in prepared
        assert "Кредиторская задолженность выросла до 500 000 рублей" in prepared
        assert prepared.count("Выручка компании составила 1 000 000 рублей") == 1
        assert "Страница 1" not in prepared
        assert "2023" not in prepared
        assert len(prepared) <= 4000


class TestParseLlmJson:
    def test_valid_json(self):
        result = _parse_llm_json('{"risks": ["risk1"], "key_factors": ["factor1"]}')
        assert result == {"risks": ["risk1"], "key_factors": ["factor1"]}

    def test_empty_string(self):
        assert _parse_llm_json("") is None

    def test_invalid_json(self):
        assert _parse_llm_json("not json at all") is None

    def test_json_embedded_in_text(self):
        text = 'Some text before\n{"risks": ["risk1"]}\nSome text after'
        assert _parse_llm_json(text) == {"risks": ["risk1"]}


class TestAnalyzeNarrative:
    @pytest.mark.asyncio
    async def test_empty_input(self):
        assert await analyze_narrative("") == _empty_result()

    @pytest.mark.asyncio
    async def test_low_quality_text_skips_llm(self):
        with patch("src.analysis.nlp_analysis.ai_service") as mock_ai:
            result = await analyze_narrative("lorem ipsum " * 20)
        assert result == _empty_result()
        mock_ai.invoke.assert_not_called()

    @pytest.mark.asyncio
    async def test_successful_llm_response(self):
        payload = json.dumps(
            {
                "risks": ["risk1", "risk2"],
                "key_factors": ["factor1"],
                "recommendations": ["rec1"],
            }
        )

        with patch("src.analysis.nlp_analysis.ai_service") as mock_ai:
            mock_ai.invoke = AsyncMock(return_value=payload)

            result = await analyze_narrative(
                "Пояснительная записка\nВыручка 1000000\nРиск ликвидности 500000\n" * 10
            )

        assert result["risks"] == ["risk1", "risk2"]
        assert result["key_factors"] == ["factor1"]
        assert result["recommendations"] == ["rec1"]
        mock_ai.invoke.assert_called_once()
        kwargs = mock_ai.invoke.await_args.kwargs
        assert kwargs["timeout"] == 120
        tool_input = kwargs["input"]["tool_input"]
        assert len(tool_input) <= 4000
        assert "Выручка 1000000" in tool_input

    @pytest.mark.asyncio
    async def test_invalid_llm_json_response(self):
        with patch("src.analysis.nlp_analysis.ai_service") as mock_ai:
            mock_ai.invoke = AsyncMock(return_value="not valid json")
            result = await analyze_narrative("Выручка 1000000\nАктивы 2000000\n" * 10)
        assert result == _empty_result()

    @pytest.mark.asyncio
    async def test_ai_exception_returns_empty(self):
        with patch("src.analysis.nlp_analysis.ai_service") as mock_ai:
            mock_ai.invoke = AsyncMock(side_effect=Exception("Connection error"))
            result = await analyze_narrative("Выручка 1000000\nАктивы 2000000\n" * 10)
        assert result == _empty_result()
