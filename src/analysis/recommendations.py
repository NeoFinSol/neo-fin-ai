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
        if value < 0.1:  # Likely a ratio or percentage decimal
            return f"{value:.2f}"
        elif value > 100:  # Likely a large number (currency, etc.)
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
    # Format metrics section
    metrics_section = "ФИНАНСОВЫЕ ПОКАЗАТЕЛИ КОМПАНИИ:\n"
    if metrics.get("revenue"):
        metrics_section += f"- Выручка (Revenue): {_format_metric_value(metrics['revenue'])} ₽\n"
    if metrics.get("net_profit") is not None:
        metrics_section += f"- Чистая прибыль (Net Profit): {_format_metric_value(metrics['net_profit'])} ₽\n"
    if metrics.get("total_assets"):
        metrics_section += f"- Активы (Total Assets): {_format_metric_value(metrics['total_assets'])} ₽\n"
    if metrics.get("equity"):
        metrics_section += f"- Собственный капитал (Equity): {_format_metric_value(metrics['equity'])} ₽\n"
    if metrics.get("liabilities"):
        metrics_section += f"- Обязательства (Liabilities): {_format_metric_value(metrics['liabilities'])} ₽\n"

    # Format ratios section
    ratios_section = "\nФИНАНСОВЫЕ КОЭФФИЦИЕНТЫ:\n"
    if ratios.get("current_ratio") is not None:
        ratios_section += f"- Коэффициент текущей ликвидности: {_format_metric_value(ratios['current_ratio'])}\n"
    if ratios.get("equity_ratio") is not None:
        ratios_section += f"- Коэффициент автономии: {_format_metric_value(ratios['equity_ratio'])}\n"
    if ratios.get("roe") is not None:
        ratios_section += f"- ROE (рентабельность собственного капитала): {_format_metric_value(ratios['roe'])}\n"
    if ratios.get("roa") is not None:
        ratios_section += f"- ROA (рентабельность активов): {_format_metric_value(ratios['roa'])}\n"
    if ratios.get("debt_to_revenue") is not None:
        ratios_section += f"- Долговая нагрузка (Долг/Выручка): {_format_metric_value(ratios['debt_to_revenue'])}\n"

    # Format NLP analysis section
    nlp_section = "\nРЕЗУЛЬТАТЫ NLP АНАЛИЗА ПОЯСНИТЕЛЬНОЙ ЗАПИСКИ:\n"
    risks = nlp_result.get("risks", [])
    if risks:
        nlp_section += f"- Выявленные риски: {', '.join(risks[:3])}\n"
    key_factors = nlp_result.get("key_factors", [])
    if key_factors:
        nlp_section += f"- Ключевые факторы: {', '.join(key_factors[:3])}\n"

    # Build the full prompt
    prompt = f"""{metrics_section}{ratios_section}{nlp_section}
ЗАДАЧА:
Сформируй 3-5 конкретных рекомендаций для финансового директора компании.
В каждой рекомендации обязательно ссылайся на конкретные цифры и показатели из выше приведённых данных.

Примеры формата ответа:
- "При текущем коэффициенте ликвидности 1.5 рекомендуется оптимизировать управление оборотным капиталом..."
- "Выручка компании составила 1000000 ₽, что при чистой прибыли 150000 ₽ указывает на маржу 15%. Рекомендуется..."
- "Коэффициент автономии на уровне 0.4 требует внимания к структуре капитала. Рекомендуется..."

Требования:
- Рекомендации должны быть практичными и действенными
- Обязательно ссылаться на конкретные цифры
- Ответ верни в формате JSON массива строк: {{"recommendations": ["рекомендация 1", "рекомендация 2", ...]}}
- Минимум 3 рекомендации, максимум 5
"""
    return prompt


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
        # Set timeout for AI service (60 seconds)
        response = await asyncio.wait_for(
            ai_service.invoke(
                input={
                    "tool_input": prompt,
                    "system": (
                        "Ты опытный финансовый аналитик и консультант. "
                        "Давай конкретные, действенные рекомендации с ссылками на цифры. "
                        "Отвечай только JSON без дополнительного текста."
                    ),
                },
                timeout=60,
            ),
            timeout=65.0  # Extra 5 seconds buffer
        )

        if not response:
            logger.warning("AI service returned empty response for recommendations")
            return FALLBACK_RECOMMENDATIONS

        # Parse the response
        recommendations = _parse_recommendations_response(response)
        
        if not recommendations:
            logger.warning("Failed to parse recommendations from AI response")
            return FALLBACK_RECOMMENDATIONS

        logger.info(f"Generated {len(recommendations)} recommendations with data references")
        return recommendations

    except asyncio.TimeoutError:
        logger.warning("Recommendations generation timed out (60s)")
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
        logger.warning(f"Failed to parse recommendations JSON: {e}")
        return []

    # Extract recommendations list
    recommendations = parsed.get("recommendations", [])

    if not isinstance(recommendations, list):
        logger.warning("Recommendations field is not a list")
        return []

    # Convert all items to strings and filter empty ones
    result = [str(r).strip() for r in recommendations if r]

    if len(result) < 3:
        logger.warning(f"Generated only {len(result)} recommendations, expected 3-5")

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
