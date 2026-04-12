import logging
from typing import Any

from src.analysis.math.engine import MathEngine
from src.analysis.math.projections import LEGACY_RATIO_NAME_MAP, project_legacy_ratios
from src.analysis.math.validators import normalize_inputs

logger = logging.getLogger(__name__)

# Маппинг русских ключей ratios → snake_case English для frontend
# Порядок соответствует группам: ликвидность, рентабельность, устойчивость, активность
RATIO_KEY_MAP = {
    # Liquidity
    "Коэффициент текущей ликвидности": "current_ratio",
    "Коэффициент быстрой ликвидности": "quick_ratio",
    "Коэффициент абсолютной ликвидности": "absolute_liquidity_ratio",
    # Profitability
    "Рентабельность активов (ROA)": "roa",
    "Рентабельность собственного капитала (ROE)": "roe",
    "Рентабельность продаж (ROS)": "ros",
    "EBITDA маржа": "ebitda_margin",
    # Financial stability
    "Коэффициент автономии": "equity_ratio",
    "Финансовый рычаг": "financial_leverage",
    "Финансовый рычаг (обязательства/капитал)": "financial_leverage_total",
    "Финансовый рычаг (долг/капитал)": "financial_leverage_debt_only",
    "Покрытие процентов": "interest_coverage",
    # Business activity
    "Оборачиваемость активов": "asset_turnover",
    "Оборачиваемость запасов": "inventory_turnover",
    "Оборачиваемость дебиторской задолженности": "receivables_turnover",
}


def translate_ratios(ratios: dict) -> dict:
    """
    Convert Russian ratio keys to snake_case English for frontend.

    Args:
        ratios: Dictionary with Russian keys from calculate_ratios

    Returns:
        dict: Dictionary with English keys
    """
    result = {}
    unknown_keys = []

    for k, v in ratios.items():
        en_key = RATIO_KEY_MAP.get(k)
        if en_key:
            result[en_key] = v
        else:
            # Drop unknown keys — do not forward Russian keys to the frontend
            unknown_keys.append(k)

    if unknown_keys:
        logger.warning("Unmapped ratio keys (frontend may break): %s", unknown_keys)

    return result


def calculate_ratios(financial_data: dict[str, Any]) -> dict[str, float | None]:
    """Project derived metrics from the Math Layer into the legacy ratio payload."""
    engine = MathEngine()
    typed_inputs = normalize_inputs(_build_raw_math_inputs(financial_data))
    derived_metrics = engine.compute(typed_inputs)
    legacy_values, _projection_trace = project_legacy_ratios(derived_metrics)
    return {key: legacy_values.get(key) for key in LEGACY_RATIO_NAME_MAP.values()}


def _build_raw_math_inputs(financial_data: dict[str, Any]) -> dict[str, object]:
    raw_inputs: dict[str, object] = {}
    for key, value in financial_data.items():
        if isinstance(value, dict):
            raw_inputs[key] = value
            continue
        raw_inputs[key] = {"value": _to_number(value)}
    return raw_inputs


def _to_number(value: Any) -> float | None:
    """
    Convert value to float, handling various types safely.

    Args:
        value: Any value that might be converted to float

    Returns:
        Float value or None if conversion fails
    """
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
