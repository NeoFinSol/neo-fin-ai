import json
import logging
import re
from typing import Any

from src.core.ai_service import ai_service
from src.core.prompts import LLM_ANALYSIS_PROMPT
from src.analysis.llm_extractor import clean_for_llm, is_clean_financial_text

logger = logging.getLogger(__name__)


async def analyze_narrative(full_text: str) -> dict[str, list[str]]:
    if not full_text:
        return _empty_result()

    # Gate: if text is OCR garbage, skip LLM entirely — saves 80-90% tokens
    if not is_clean_financial_text(full_text):
        logger.warning("NLP analysis skipped: text quality too low (%d chars)", len(full_text))
        return _empty_result()

    # Filter to financially relevant lines before extracting narrative
    cleaned_text = clean_for_llm(full_text)
    if not cleaned_text:
        return _empty_result()
    narrative_text = _extract_narrative(cleaned_text)
    if not narrative_text:
        narrative_text = cleaned_text

    try:
        response = await ai_service.invoke(
            input={
                "tool_input": narrative_text,
                "system": LLM_ANALYSIS_PROMPT,
            },
            timeout=120
        )
        
        if not response:
            logger.warning("AI service returned empty response")
            return _empty_result()
            
        parsed = _parse_llm_json(response)
        if parsed is None:
            logger.warning("Failed to parse AI response, returning fallback")
            return _empty_result()

        return {
            "risks": _ensure_list(parsed.get("risks")),
            "key_factors": _ensure_list(parsed.get("key_factors")),
            "recommendations": _ensure_list(parsed.get("recommendations")),
        }
        
    except Exception as exc:
        logger.warning("AI analysis failed: %s", exc)
        return _empty_result()


def _extract_narrative(text: str) -> str:
    lowered = text.lower()
    keywords = [
        "пояснительная записка",
        "пояснительная записка к бухгалтерской",
        "пояснения к бухгалтерской",
        "notes to the financial",
    ]

    start_index = -1
    for keyword in keywords:
        idx = lowered.find(keyword)
        if idx != -1:
            start_index = idx
            break

    if start_index == -1:
        # No narrative section found — use beginning of text, truncated
        return text[:6000].strip()

    extracted = text[start_index: start_index + 6000]
    return extracted.strip()


def _parse_llm_json(response_text: str) -> dict[str, Any] | None:
    if not response_text:
        return None

    try:
        return json.loads(response_text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", response_text, re.DOTALL)
        if not match:
            return None
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            return None


def _ensure_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value]
    if value is None:
        return []
    return [str(value)]


def _empty_result() -> dict[str, list[str]]:
    return {
        "risks": [],
        "key_factors": [],
        "recommendations": [],
    }
