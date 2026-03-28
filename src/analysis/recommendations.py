"""Generate data-driven financial recommendations with references to extracted metrics."""
import asyncio
import json
import logging
import re
from typing import Any, Optional

from src.core.ai_service import ai_service

logger = logging.getLogger(__name__)


# Fallback recommendations when AI is unavailable
FALLBACK_RECOMMENDATIONS = [
    "Анализ данных компании завершён. Рекомендуется тщательно изучить предоставленные метрики и факторы риска.",
    "Следует пересмотреть стратегию управления ликвидностью на основе текущих показателей.",
    "Важно учитывать выявленные риски при планировании финансовой политики компании.",
]


def _format_metric_value(value: Optional[float | int | None]) -> str:
    """
    Format a metric value for display in recommendations.

    Args:
        value: Numeric value or None

    Returns:
        str: Formatted value or '—' if None
    """
    if value is None:
        return "—"
    if isinstance(value, float):
        # Show percentages and ratios nicely
        if abs(value) < 0.1:  # Likely a ratio or percentage decimal
            return f"{value:.2f}"
        elif abs(value) > 100:  # Likely a large number (currency, etc.)
            return f"{value:,.0f}"
        else:
            return f"{value:.2f}"
    # Format integers with thousands separator if large enough
    if isinstance(value, int) and value > 999:
        return f"{value:,}"
    return str(value)


def _build_recommendations_prompt(
    metrics: dict[str, Optional[float | int]],
    ratios: dict[str, Optional[float]],
    nlp_result: dict[str, Any],
) -> str:
    """
    Build a detailed prompt for LLM with specific metrics and context.
    
    Args:
        metrics: Extracted financial metrics (revenue, profit, etc.)
        ratios: Calculated financial ratios
        nlp_result: NLP analysis results (risks, factors)
        
    Returns:
        str: Formatted prompt for LLM
    """
    context = {
        "metrics": {
            key: _format_metric_value(value)
            for key, value in metrics.items()
            if value is not None
        },
        "ratios": {
            key: _format_metric_value(value)
            for key, value in ratios.items()
            if value is not None
        },
        "risks": [str(item) for item in nlp_result.get("risks", [])[:3]],
        "key_factors": [str(item) for item in nlp_result.get("key_factors", [])[:3]],
    }

    return (
        "Контекст финансового анализа JSON:\n"
        f"{json.dumps(context, ensure_ascii=False)}\n"
        "Сформируй 3-5 практичных рекомендаций для финансового директора.\n"
        "Каждая рекомендация должна ссылаться минимум на одно конкретное число "
        "из metrics или ratios.\n"
        "Не выдумывай отсутствующие значения.\n"
        "Верни только JSON: "
        "{\"recommendations\": [\"...\", \"...\"]}"
    )


async def generate_recommendations(
    metrics: dict[str, Optional[float | int]],
    ratios: dict[str, Optional[float]],
    nlp_result: dict[str, Any],
) -> list[str]:
    """
    Generate recommendations with references to extracted data.
    
    This function creates a detailed prompt with specific financial metrics
    and asks an LLM to generate actionable recommendations that directly
    reference the provided data.
    
    Args:
        metrics: Extracted financial metrics (revenue, profit, etc.)
        ratios: Calculated financial ratios (current_ratio, roe, etc.)
        nlp_result: NLP analysis results containing risks and factors
        
    Returns:
        list[str]: List of recommendation strings with data references
        
    Raises:
        None (graceful degradation with fallback recommendations)
    """
    if not metrics and not ratios:
        logger.warning("No metrics or ratios provided for recommendations generation")
        return FALLBACK_RECOMMENDATIONS

    # Build the detailed prompt
    prompt = _build_recommendations_prompt(metrics, ratios, nlp_result)

    # Try to invoke AI service
    try:
        # Timeout is controlled by tasks.py (single wait_for on the call stack)
        response = await ai_service.invoke(
            input={
                "tool_input": prompt,
                "system": (
                    "Ты опытный финансовый аналитик и консультант. "
                    "Давай конкретные, действенные рекомендации с ссылками на цифры. "
                    "Отвечай только JSON без дополнительного текста."
                ),
            },
            timeout=90,
        )

        if not response:
            logger.warning("AI service returned empty response for recommendations")
            return FALLBACK_RECOMMENDATIONS

        # Parse the response
        recommendations = _parse_recommendations_response(response)
        
        if not recommendations:
            logger.warning("Failed to parse recommendations from AI response")
            return FALLBACK_RECOMMENDATIONS

        logger.info("Generated %d recommendations with data references", len(recommendations))
        return recommendations

    except asyncio.TimeoutError:
        logger.warning("Recommendations generation timed out (90s)")
        return FALLBACK_RECOMMENDATIONS
    except ImportError:
        logger.debug("AI service not available for recommendations generation")
        return FALLBACK_RECOMMENDATIONS
    except Exception as exc:
        logger.exception("Failed to generate recommendations: %s", exc)
        return FALLBACK_RECOMMENDATIONS


def _parse_recommendations_response(response_text: str) -> list[str]:
    """
    Parse LLM response to extract recommendation strings.
    
    Handles both JSON and markdown-wrapped JSON responses.
    
    Args:
        response_text: Raw response from LLM
        
    Returns:
        list[str]: List of recommendations or empty list if parsing fails
    """
    if not response_text or not isinstance(response_text, str):
        return []

    response_text = response_text.strip()

    # Try to extract JSON object
    # Handle markdown code blocks: ```json {...}``` or ```{...}```
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", response_text, re.DOTALL)
    if match:
        json_str = match.group(1)
    else:
        # Try to find raw JSON object
        match = re.search(r"\{.*\}", response_text, re.DOTALL)
        if match:
            json_str = match.group(0)
        else:
            logger.warning("No JSON found in recommendations response")
            return []

    try:
        parsed = json.loads(json_str)
    except json.JSONDecodeError as e:
        logger.warning("Failed to parse recommendations JSON: %s", e)
        return []

    # Extract recommendations list
    recommendations = parsed.get("recommendations", [])

    if not isinstance(recommendations, list):
        logger.warning("Recommendations field is not a list")
        return []

    # Deduplicate while preserving first-occurrence order
    result = list(dict.fromkeys(str(r).strip() for r in recommendations if r))

    if len(result) < 3:
        logger.warning("Generated only %d recommendations, expected 3-5", len(result))

    return result


async def generate_recommendations_with_fallback(
    metrics: dict[str, Optional[float | int]],
    ratios: dict[str, Optional[float]],
    nlp_result: dict[str, Any],
    use_fallback: bool = True,
) -> list[str]:
    """
    Generate recommendations with optional fallback.
    
    This is a wrapper around generate_recommendations() that optionally
    uses fallback recommendations if generation fails.
    
    Args:
        metrics: Extracted financial metrics
        ratios: Calculated financial ratios
        nlp_result: NLP analysis results
        use_fallback: Whether to use fallback on failure (default: True)
        
    Returns:
        list[str]: List of recommendations
    """
    recommendations = await generate_recommendations(metrics, ratios, nlp_result)
    
    # If we got empty results but should use fallback
    if not recommendations and use_fallback:
        logger.info("Using fallback recommendations")
        return FALLBACK_RECOMMENDATIONS
    
    return recommendations
