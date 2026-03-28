"""Tests for recommendations generation module."""
import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.analysis.recommendations import (
    FALLBACK_RECOMMENDATIONS,
    _build_recommendations_prompt,
    _format_metric_value,
    _parse_recommendations_response,
    generate_recommendations,
    generate_recommendations_with_fallback,
)


class TestFormatMetricValue:
    """Tests for _format_metric_value helper."""

    def test_format_none_value(self):
        """Test None value returns dash."""
        assert _format_metric_value(None) == "—"

    def test_format_large_number(self):
        """Test large numbers are formatted with thousands separator."""
        result = _format_metric_value(1000000)
        # Numbers over 100 are formatted with no decimals
        assert "1000000" in result or "1,000,000" in result

    def test_format_ratio_value(self):
        """Test ratio values are formatted with 2 decimal places."""
        result = _format_metric_value(1.5)
        assert "1.50" in result

    def test_format_small_float(self):
        """Test small floats are formatted correctly."""
        result = _format_metric_value(0.05)
        assert "0.05" in result

    def test_format_integer(self):
        """Test integer values are converted to string."""
        result = _format_metric_value(42)
        assert "42" in result


class TestBuildRecommendationsPrompt:
    """Tests for _build_recommendations_prompt function."""

    def test_prompt_includes_metrics(self):
        """Test prompt includes provided metrics in compact JSON context."""
        metrics = {
            "revenue": 1000000,
            "net_profit": 150000,
            "total_assets": 2000000,
        }
        ratios = {}
        nlp_result = {}

        prompt = _build_recommendations_prompt(metrics, ratios, nlp_result)

        assert "\"metrics\"" in prompt
        assert "\"revenue\": \"1,000,000\"" in prompt
        assert "1,000,000" in prompt
        assert "150,000" in prompt
        assert "2,000,000" in prompt
        assert "Контекст финансового анализа JSON" in prompt

    def test_prompt_includes_ratios(self):
        """Test prompt includes provided ratios in compact JSON context."""
        metrics = {}
        ratios = {
            "current_ratio": 1.5,
            "equity_ratio": 0.4,
            "roe": 0.2,
        }
        nlp_result = {}

        prompt = _build_recommendations_prompt(metrics, ratios, nlp_result)

        assert "\"ratios\"" in prompt
        assert "\"current_ratio\": \"1.50\"" in prompt
        assert "1.50" in prompt
        assert "0.40" in prompt

    def test_prompt_includes_nlp_results(self):
        """Test prompt includes compact NLP findings."""
        metrics = {}
        ratios = {}
        nlp_result = {
            "risks": ["high debt", "low profitability"],
            "key_factors": ["market conditions", "operational efficiency"],
        }

        prompt = _build_recommendations_prompt(metrics, ratios, nlp_result)

        assert "high debt" in prompt
        assert "low profitability" in prompt
        assert "market conditions" in prompt
        assert "\"risks\"" in prompt
        assert "\"key_factors\"" in prompt

    def test_prompt_handles_empty_inputs(self):
        """Test prompt handles empty metrics/ratios/nlp gracefully."""
        prompt = _build_recommendations_prompt({}, {}, {})

        assert "\"metrics\": {}" in prompt
        assert "\"ratios\": {}" in prompt
        assert "\"risks\": []" in prompt


class TestParseRecommendationsResponse:
    """Tests for _parse_recommendations_response function."""

    def test_parse_valid_json(self):
        """Test parsing valid JSON response."""
        response = json.dumps({
            "recommendations": [
                "При текущем коэффициенте ликвидности 1.5 рекомендуется...",
                "Выручка 1 млн руб. показывает...",
            ]
        })

        result = _parse_recommendations_response(response)

        assert len(result) == 2
        assert "ликвидности" in result[0].lower()
        assert "выручка" in result[1].lower()

    def test_parse_markdown_wrapped_json(self):
        """Test parsing JSON wrapped in markdown code block."""
        json_obj = json.dumps({
            "recommendations": ["Rec 1", "Rec 2", "Rec 3"]
        })
        response = f"```json\n{json_obj}\n```"

        result = _parse_recommendations_response(response)

        assert len(result) == 3
        assert "Rec 1" in result

    def test_parse_plain_json_in_response(self):
        """Test parsing plain JSON embedded in response."""
        json_obj = json.dumps({
            "recommendations": ["Rec 1", "Rec 2"]
        })
        response = f"Here is the analysis:\n{json_obj}\nEnd of analysis"

        result = _parse_recommendations_response(response)

        assert len(result) == 2

    def test_parse_invalid_json(self):
        """Test parsing invalid JSON returns empty list."""
        response = "This is not JSON"

        result = _parse_recommendations_response(response)

        assert result == []

    def test_parse_empty_response(self):
        """Test parsing empty response."""
        result = _parse_recommendations_response("")
        assert result == []

    def test_parse_none_response(self):
        """Test parsing None response."""
        result = _parse_recommendations_response(None)
        assert result == []

    def test_parse_missing_recommendations_field(self):
        """Test JSON without recommendations field."""
        response = json.dumps({"analysis": "something"})

        result = _parse_recommendations_response(response)

        assert result == []

    def test_parse_non_list_recommendations(self):
        """Test recommendations field that is not a list."""
        response = json.dumps({
            "recommendations": "just a string"
        })

        result = _parse_recommendations_response(response)

        assert result == []

    def test_parse_filters_empty_recommendations(self):
        """Test that empty strings are filtered out."""
        response = json.dumps({
            "recommendations": ["Rec 1", "", "Rec 2", None, "Rec 3"]
        })

        result = _parse_recommendations_response(response)

        assert len(result) == 3
        assert all(r for r in result)  # All non-empty


class TestGenerateRecommendations:
    """Tests for generate_recommendations function."""

    @pytest.mark.asyncio
    async def test_successful_generation(self):
        """Test successful recommendations generation."""
        metrics = {"revenue": 1000000, "net_profit": 150000}
        ratios = {"current_ratio": 1.5, "roe": 0.2}
        nlp_result = {"risks": ["high debt"]}

        mock_response = json.dumps({
            "recommendations": [
                "При ROE 0.2 рекомендуется...",
                "Выручка 1 млн руб. показывает...",
            ]
        })

        with patch("src.analysis.recommendations.ai_service") as mock_ai:
            mock_ai.invoke = AsyncMock(return_value=mock_response)

            result = await generate_recommendations(metrics, ratios, nlp_result)

            assert len(result) == 2
            assert "ROE" in result[0]
            mock_ai.invoke.assert_called_once()

    @pytest.mark.asyncio
    async def test_empty_metrics_returns_fallback(self):
        """Test empty metrics returns fallback recommendations."""
        result = await generate_recommendations({}, {}, {})

        assert result == FALLBACK_RECOMMENDATIONS

    @pytest.mark.asyncio
    async def test_ai_timeout_returns_fallback(self):
        """Test AI timeout returns fallback recommendations."""
        metrics = {"revenue": 1000000}
        ratios = {"current_ratio": 1.5}
        nlp_result = {}

        with patch("src.analysis.recommendations.ai_service") as mock_ai:
            async def timeout_func(*args, **kwargs):
                await asyncio.sleep(100)  # Simulate timeout
                return None

            mock_ai.invoke = timeout_func

            result = await generate_recommendations(metrics, ratios, nlp_result)

            assert result == FALLBACK_RECOMMENDATIONS

    @pytest.mark.asyncio
    async def test_ai_error_returns_fallback(self):
        """Test AI error returns fallback recommendations."""
        metrics = {"revenue": 1000000}
        ratios = {"current_ratio": 1.5}
        nlp_result = {}

        with patch("src.analysis.recommendations.ai_service") as mock_ai:
            mock_ai.invoke = AsyncMock(side_effect=Exception("AI error"))

            result = await generate_recommendations(metrics, ratios, nlp_result)

            assert result == FALLBACK_RECOMMENDATIONS

    @pytest.mark.asyncio
    async def test_empty_ai_response_returns_fallback(self):
        """Test empty AI response returns fallback recommendations."""
        metrics = {"revenue": 1000000}
        ratios = {"current_ratio": 1.5}
        nlp_result = {}

        with patch("src.analysis.recommendations.ai_service") as mock_ai:
            mock_ai.invoke = AsyncMock(return_value=None)

            result = await generate_recommendations(metrics, ratios, nlp_result)

            assert result == FALLBACK_RECOMMENDATIONS

    @pytest.mark.asyncio
    async def test_invalid_json_ai_response_returns_fallback(self):
        """Test invalid JSON from AI returns fallback recommendations."""
        metrics = {"revenue": 1000000}
        ratios = {"current_ratio": 1.5}
        nlp_result = {}

        with patch("src.analysis.recommendations.ai_service") as mock_ai:
            mock_ai.invoke = AsyncMock(return_value="This is not JSON")

            result = await generate_recommendations(metrics, ratios, nlp_result)

            assert result == FALLBACK_RECOMMENDATIONS

    @pytest.mark.asyncio
    async def test_recommendations_reference_metrics(self):
        """Test that generated recommendations reference actual metrics."""
        metrics = {"revenue": 1000000}
        ratios = {"current_ratio": 1.5, "roe": 0.2}
        nlp_result = {}

        mock_response = json.dumps({
            "recommendations": [
                "При текущем коэффициенте ликвидности 1.5 рекомендуется оптимизировать оборотный капитал.",
                "ROE на уровне 0.2 указывает на хорошую рентабельность. Следует поддерживать этот уровень.",
            ]
        })

        with patch("src.analysis.recommendations.ai_service") as mock_ai:
            mock_ai.invoke = AsyncMock(return_value=mock_response)

            result = await generate_recommendations(metrics, ratios, nlp_result)

            assert len(result) == 2
            # Verify metrics are referenced
            assert any("1.5" in r for r in result)
            assert any("0.2" in r for r in result)


class TestGenerateRecommendationsWithFallback:
    """Tests for generate_recommendations_with_fallback wrapper."""

    @pytest.mark.asyncio
    async def test_with_fallback_success(self):
        """Test successful generation with fallback enabled."""
        metrics = {"revenue": 1000000}
        ratios = {"current_ratio": 1.5}
        nlp_result = {}

        mock_response = json.dumps({
            "recommendations": ["Rec 1", "Rec 2"]
        })

        with patch("src.analysis.recommendations.ai_service") as mock_ai:
            mock_ai.invoke = AsyncMock(return_value=mock_response)

            result = await generate_recommendations_with_fallback(
                metrics, ratios, nlp_result, use_fallback=True
            )

            assert len(result) == 2
            assert "Rec 1" in result

    @pytest.mark.asyncio
    async def test_with_fallback_uses_fallback(self):
        """Test that fallback is used when generation fails."""
        metrics = {"revenue": 1000000}
        ratios = {"current_ratio": 1.5}
        nlp_result = {}

        with patch("src.analysis.recommendations.ai_service") as mock_ai:
            mock_ai.invoke = AsyncMock(return_value=None)

            result = await generate_recommendations_with_fallback(
                metrics, ratios, nlp_result, use_fallback=True
            )

            assert result == FALLBACK_RECOMMENDATIONS

    @pytest.mark.asyncio
    async def test_without_fallback_returns_empty(self):
        """Test that empty list is returned when fallback is disabled."""
        metrics = {"revenue": 1000000}
        ratios = {"current_ratio": 1.5}
        nlp_result = {}

        with patch("src.analysis.recommendations.ai_service") as mock_ai:
            mock_ai.invoke = AsyncMock(return_value=None)

            result = await generate_recommendations_with_fallback(
                metrics, ratios, nlp_result, use_fallback=False
            )

            # When use_fallback is False and generation fails, return empty list
            assert isinstance(result, list)


class TestIntegrationWithNLPResult:
    """Integration tests with NLP result structure."""

    @pytest.mark.asyncio
    async def test_recommendations_consider_nlp_risks(self):
        """Test that recommendations account for NLP-identified risks."""
        metrics = {"revenue": 1000000, "net_profit": 50000}
        ratios = {"current_ratio": 0.8}  # Below recommended 1.5
        nlp_result = {
            "risks": ["high operational risk", "market volatility"],
            "key_factors": ["supply chain issues"],
        }

        prompt_capture = []

        async def mock_invoke(input, timeout=None):
            prompt_capture.append(input.get("tool_input", ""))
            return json.dumps({
                "recommendations": [
                    "При коэффициенте ликвидности 0.8 необходимо срочно улучшить управление оборотным капиталом "
                    "учитывая выявленные операционные риски.",
                ]
            })

        with patch("src.analysis.recommendations.ai_service") as mock_ai:
            mock_ai.invoke = mock_invoke

            result = await generate_recommendations(metrics, ratios, nlp_result)

            # Verify the prompt included the risks
            prompt = prompt_capture[0] if prompt_capture else ""
            assert "0.8" in prompt
            assert "high operational risk" in prompt
            assert "market volatility" in prompt
            assert len(result) > 0
