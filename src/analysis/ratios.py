import logging
from typing import Any

logger = logging.getLogger(__name__)


def calculate_ratios(financial_data: dict[str, Any]) -> dict[str, float | None]:
    revenue = _to_number(financial_data.get("revenue"))
    net_profit = _to_number(financial_data.get("net_profit"))
    total_assets = _to_number(financial_data.get("total_assets"))
    equity = _to_number(financial_data.get("equity"))
    liabilities = _to_number(financial_data.get("liabilities"))
    current_assets = _to_number(financial_data.get("current_assets"))
    short_term_liabilities = _to_number(financial_data.get("short_term_liabilities"))

    ratios: dict[str, float | None] = {
        "Коэффициент текущей ликвидности": _safe_div(current_assets, short_term_liabilities),
        "Коэффициент автономии": _safe_div(equity, total_assets),
        "Рентабельность активов (ROA)": _safe_div(net_profit, total_assets),
        "Рентабельность собственного капитала (ROE)": _safe_div(net_profit, equity),
        "Долговая нагрузка": _safe_div(liabilities, revenue),
    }

    return ratios


def _safe_div(numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or denominator in (None, 0):
        return None
    try:
        return numerator / denominator
    except Exception as exc:
        logger.warning("Failed to compute ratio: %s", exc)
        return None


def _to_number(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
