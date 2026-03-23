# Recommendations Generation Module

## Overview

The `recommendations.py` module provides functionality to generate data-driven financial recommendations with explicit references to extracted metrics and NLP analysis results.

**Key Feature**: Generated recommendations directly reference specific financial figures from the analysis, satisfying the competition requirement "Reference source data in text recommendations."

## Architecture

### Main Function: `generate_recommendations()`

```python
async def generate_recommendations(
    metrics: dict[str, Optional[float | int]],
    ratios: dict[str, Optional[float]],
    nlp_result: dict[str, Any],
) -> list[str]:
    """Generate recommendations with references to extracted data."""
```

**Parameters:**
- `metrics`: Financial metrics (revenue, net_profit, total_assets, equity, liabilities, etc.)
- `ratios`: Financial ratios (current_ratio, equity_ratio, roe, roa, debt_to_revenue)
- `nlp_result`: NLP analysis results (risks, key_factors from narrative analysis)

**Returns:**
- `list[str]`: 3-5 recommendations with explicit data references, or fallback recommendations if AI is unavailable

**Example Output:**
```json
[
  "При текущем коэффициенте ликвидности 1.5 рекомендуется оптимизировать управление оборотным капиталом...",
  "Выручка 1,000,000 ₽ при чистой прибыли 150,000 ₽ указывает на маржу 15%. Рекомендуется...",
  "Коэффициент автономии 0.4 требует внимания к структуре капитала. Рекомендуется..."
]
```

## Features

### 1. **Graceful Degradation**
- Falls back to predefined recommendations if AI is unavailable
- Handles timeouts (60 seconds)
- Logs all errors for monitoring

### 2. **Explicit Data References**
- Prompt construction includes all key metrics
- LLM is instructed to reference specific figures
- Generated recommendations quote actual values from analysis

### 3. **Flexible AI Provider Support**
- Works with any AI service compatible with `ai_service.invoke()`
- Supports GigaChat, Qwen, or local LLM via Ollama
- No dependency on specific provider

### 4. **JSON Response Parsing**
- Handles JSON in code blocks (```json {...}```)
- Handles plain JSON
- Robust error handling for malformed responses

## Integration with `process_pdf()`

The module is automatically integrated in `src/tasks.py`:

```python
# After NLP analysis
nlp_result = await analyze_narrative(text)

# Generate data-driven recommendations
recommendations = await asyncio.wait_for(
    generate_recommendations(metrics, ratios_en, nlp_result),
    timeout=65.0
)
nlp_result["recommendations"] = recommendations

# Update database with recommendations included
await update_analysis(task_id, "completed", {
    "data": {
        "metrics": metrics,
        "ratios": ratios_en,
        "score": score_payload,
        "nlp": nlp_result,  # Now includes recommendations
    }
})
```

## API Reference

### Primary Functions

#### `generate_recommendations(metrics, ratios, nlp_result)`
Main entry point for recommendation generation.

**Features:**
- 60-second timeout for AI requests
- Automatic fallback to predefined recommendations
- Full error logging

**Example:**
```python
recommendations = await generate_recommendations(
    metrics={
        "revenue": 1_000_000,
        "net_profit": 150_000,
        "total_assets": 2_000_000,
        "equity": 800_000,
    },
    ratios={
        "current_ratio": 1.5,
        "equity_ratio": 0.4,
        "roe": 0.2,
        "roa": 0.075,
        "debt_to_revenue": 0.5,
    },
    nlp_result={
        "risks": ["high debt", "market volatility"],
        "key_factors": ["supply chain optimization"],
        "recommendations": [],  # Will be populated
    }
)
print(recommendations)
# ["При ROE 0.2 рекомендуется...", "Выручка 1,000,000 ₽ показывает...", ...]
```

#### `generate_recommendations_with_fallback(metrics, ratios, nlp_result, use_fallback=True)`
Wrapper with optional fallback control.

**Parameters:**
- `use_fallback` (bool): If `False`, returns empty list on failure instead of fallback

```python
# Use fallback (default)
recommendations = await generate_recommendations_with_fallback(metrics, ratios, nlp_result)

# Strict mode - fail fast
recommendations = await generate_recommendations_with_fallback(
    metrics, ratios, nlp_result, use_fallback=False
)
```

### Helper Functions

#### `_format_metric_value(value)`
Formats numeric values for display:
- `None` → `"—"`
- Large numbers (>999) → comma-separated (e.g., "1,000,000")
- Floats < 0.1 → 2 decimals (e.g., "0.15")
- Floats > 100 → no decimals with commas (e.g., "1,500.00")

#### `_build_recommendations_prompt(metrics, ratios, nlp_result)`
Constructs the LLM prompt with:
- Formatted financial metrics
- Calculated ratios
- NLP analysis results (risks, key factors)
- Instructions for data referencing
- Response format requirements (JSON)

#### `_parse_recommendations_response(response_text)`
Parses LLM response to extract recommendations:
- Handles markdown code blocks (```json {...}```)
- Handles plain JSON
- Filters empty recommendations
- Returns list of strings

## Error Handling

The module handles all failure scenarios gracefully:

| Scenario | Behavior |
|----------|----------|
| AI service unavailable | Returns fallback recommendations, logs warning |
| AI request timeout (>60s) | Returns fallback recommendations, logs warning |
| Invalid JSON response | Returns fallback recommendations, logs warning |
| Empty metrics/ratios | Returns fallback recommendations, logs warning |
| Database error during update | Task continues, recommendations logged separately |
| Import error | Module gracefully skips, main process_pdf() continues |

## Fallback Recommendations

When AI is unavailable, returns 3 predefined recommendations:

```python
FALLBACK_RECOMMENDATIONS = [
    "Анализ данных компании завершён. Рекомендуется тщательно изучить предоставленные метрики и факторы риска.",
    "Следует пересмотреть стратегию управления ликвидностью на основе текущих показателей.",
    "Важно учитывать выявленные риски при планировании финансовой политики компании.",
]
```

## Testing

Comprehensive test suite in `tests/test_recommendations.py`:

```bash
# Run all tests
pytest tests/test_recommendations.py -v

# Run specific test class
pytest tests/test_recommendations.py::TestGenerateRecommendations -v

# Run with coverage
pytest tests/test_recommendations.py --cov=src.analysis.recommendations

# Quick test
pytest tests/test_recommendations.py -q
```

**Test Coverage:**
- 29 tests covering all functions
- Mock AI service for unit testing
- Integration tests with NLP results
- Edge cases: empty data, timeouts, parsing errors

## Prompt Structure

The generated prompt includes:

```
ФИНАНСОВЫЕ ПОКАЗАТЕЛИ КОМПАНИИ:
- Выручка (Revenue): 1,000,000 ₽
- Чистая прибыль (Net Profit): 150,000 ₽
- Активы (Total Assets): 2,000,000 ₽
...

ФИНАНСОВЫЕ КОЭФФИЦИЕНТЫ:
- Коэффициент текущей ликвидности: 1.50
- ROE (рентабельность собственного капитала): 0.20
...

РЕЗУЛЬТАТЫ NLP АНАЛИЗА ПОЯСНИТЕЛЬНОЙ ЗАПИСКИ:
- Выявленные риски: high debt, market volatility
- Ключевые факторы: supply chain optimization

ЗАДАЧА:
Сформируй 3-5 конкретных рекомендаций для финансового директора.
В каждой рекомендации ссылайся на конкретные цифры выше.
Требования: ...
Ответ верни в формате JSON массива строк.
```

## Performance Characteristics

| Operation | Timeout | Typical Time |
|-----------|---------|--------------|
| generate_recommendations() | 65s (60s AI + 5s buffer) | 20-30s |
| Prompt construction | N/A | <100ms |
| JSON parsing | N/A | <50ms |
| Fallback retrieval | N/A | <10ms |

## Logging

The module logs at various levels:

```python
logger.info(f"Generated {len(recommendations)} recommendations with data references")
logger.warning("AI service returned empty response for recommendations")
logger.exception("Failed to generate recommendations: %s", exc)
```

Monitor logs with:
```bash
grep "generate_recommendations\|recommendations" app.log
```

## Backward Compatibility

- ✅ Maintains existing `nlp_result` structure
- ✅ Adds `recommendations` field to existing dict
- ✅ Falls back gracefully if AI unavailable
- ✅ No changes required to existing code calling `process_pdf()`

## Configuration

No additional configuration required. Uses existing `ai_service` configuration:

- **AI Provider**: Automatically selected (GigaChat → Qwen → Ollama)
- **Timeout**: Fixed at 60 seconds for recommendation generation
- **Fallback**: Always enabled for production stability

## Future Enhancements

Potential improvements:
1. Caching of recommendations for identical metrics
2. Recommendation ranking/scoring by relevance
3. Multi-language support
4. A/B testing different prompt strategies
5. Domain-specific recommendation templates

## License

Same as parent project.
