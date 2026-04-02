import logging
from typing import Any

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
    """
    Calculate 12 financial ratios across 4 categories for "Молодой финансист 2026" competition.

    Categories:

    LIQUIDITY RATIOS (Коэффициенты ликвидности):
    - Текущая ликвидность = Current Assets / Short-term Liabilities
    - Быстрая ликвидность = (Current Assets - Inventory) / Short-term Liabilities
    - Абсолютная ликвидность = Cash & Equivalents / Short-term Liabilities

    PROFITABILITY RATIOS (Коэффициенты рентабельности):
    - ROA = Net Profit / Total Assets
    - ROE = Net Profit / Equity
    - ROS = Net Profit / Revenue
    - EBITDA Margin = EBITDA / Revenue

    FINANCIAL STABILITY RATIOS (Коэффициенты финансовой устойчивости):
    - Коэффициент автономии = Equity / Total Assets
    - Финансовый рычаг = Liabilities / Equity
    - Покрытие процентов = EBIT / Interest Expense

    BUSINESS ACTIVITY RATIOS (Коэффициенты деловой активности):
    - Оборачиваемость активов = Revenue / Total Assets
    - Оборачиваемость запасов = COGS / Average Inventory
    - Оборачиваемость дебиторской задолженности = Revenue / Accounts Receivable

    Args:
        financial_data: Dictionary with financial metrics extracted from PDF

    Returns:
        Dictionary with Russian keys and float/None values for 12 ratios
    """
    # Extract financial metrics with safety checks
    revenue = _to_number(financial_data.get("revenue"))
    net_profit = _to_number(financial_data.get("net_profit"))
    total_assets = _to_number(financial_data.get("total_assets"))
    equity = _to_number(financial_data.get("equity"))
    liabilities = _to_number(financial_data.get("liabilities"))
    current_assets = _to_number(financial_data.get("current_assets"))
    short_term_liabilities = _to_number(financial_data.get("short_term_liabilities"))
    short_term_borrowings = _to_number(financial_data.get("short_term_borrowings"))
    long_term_borrowings = _to_number(financial_data.get("long_term_borrowings"))

    # New fields for extended ratios
    inventory = _to_number(financial_data.get("inventory"))
    cash_and_equivalents = _to_number(financial_data.get("cash_and_equivalents"))
    ebitda = _to_number(financial_data.get("ebitda"))
    ebit = _to_number(financial_data.get("ebit"))
    interest_expense = _to_number(financial_data.get("interest_expense"))
    cost_of_goods_sold = _to_number(financial_data.get("cost_of_goods_sold"))
    accounts_receivable = _to_number(financial_data.get("accounts_receivable"))
    average_inventory = _to_number(financial_data.get("average_inventory"))
    interest_bearing_debt = _sum_required(short_term_borrowings, long_term_borrowings)
    normalized_interest_expense = _abs_value(interest_expense)

    # Log missing data for critical calculations
    _log_missing_data(financial_data)

    ratios: dict[str, float | None] = {
        # ===== LIQUIDITY RATIOS =====
        "Коэффициент текущей ликвидности": _safe_div(current_assets, short_term_liabilities),
        "Коэффициент быстрой ликвидности": _safe_div(
            _subtract(current_assets, inventory), 
            short_term_liabilities
        ),
        "Коэффициент абсолютной ликвидности": _safe_div(
            cash_and_equivalents, 
            short_term_liabilities
        ),

        # ===== PROFITABILITY RATIOS =====
        "Рентабельность активов (ROA)": _safe_div(net_profit, total_assets),
        "Рентабельность собственного капитала (ROE)": _safe_div(net_profit, equity),
        "Рентабельность продаж (ROS)": _safe_div(net_profit, revenue),
        "EBITDA маржа": _safe_div(ebitda, revenue),

        # ===== FINANCIAL STABILITY RATIOS =====
        "Коэффициент автономии": _safe_div(equity, total_assets),
        "Финансовый рычаг": _safe_div(liabilities, equity),
        "Финансовый рычаг (обязательства/капитал)": _safe_div(liabilities, equity),
        "Финансовый рычаг (долг/капитал)": _safe_div(interest_bearing_debt, equity),
        "Покрытие процентов": _safe_div(ebit, normalized_interest_expense),

        # ===== BUSINESS ACTIVITY RATIOS =====
        "Оборачиваемость активов": _safe_div(revenue, total_assets),
        "Оборачиваемость запасов": _safe_div(cost_of_goods_sold, average_inventory),
        "Оборачиваемость дебиторской задолженности": _safe_div(revenue, accounts_receivable),
    }

    return ratios


def _safe_div(numerator: float | None, denominator: float | None) -> float | None:
    """
    Safely divide two numbers, handling None and zero values.

    Args:
        numerator: Dividend (can be None)
        denominator: Divisor (can be None or zero)

    Returns:
        Result of division or None if calculation is not possible
    """
    if numerator is None or denominator in (None, 0):
        return None
    try:
        return numerator / denominator
    except Exception as exc:
        logger.warning("Failed to compute ratio: %s", exc)
        return None


def _subtract(minuend: float | None, subtrahend: float | None) -> float | None:
    """
    Safely subtract two numbers, handling None values.

    Args:
        minuend: Value to subtract from
        subtrahend: Value to subtract

    Returns:
        Result of subtraction or None if either value is None
    """
    if minuend is None or subtrahend is None:
        return None
    try:
        return minuend - subtrahend
    except Exception as exc:
        logger.warning("Failed to compute subtraction: %s", exc)
        return None


def _sum_required(left: float | None, right: float | None) -> float | None:
    """Return sum only when both components are available."""
    if left is None or right is None:
        return None
    return left + right


def _abs_value(value: float | None) -> float | None:
    if value is None:
        return None
    return abs(value)


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


def _log_missing_data(financial_data: dict[str, Any]) -> None:
    """
    Log warnings for missing critical financial data fields.

    Args:
        financial_data: Dictionary of financial metrics
    """
    critical_fields = [
        "revenue", "net_profit", "total_assets", "equity", 
        "liabilities", "current_assets", "short_term_liabilities"
    ]

    for field in critical_fields:
        if financial_data.get(field) is None:
            logger.warning("Missing critical financial field: %s", field)

    # Log warning for extended fields used in new ratios
    extended_fields = [
        "inventory", "cash_and_equivalents", "ebitda", "ebit",
        "interest_expense", "cost_of_goods_sold", "average_inventory", 
        "accounts_receivable"
    ]

    for field in extended_fields:
        if financial_data.get(field) is None:
            logger.debug("Optional field not available: %s", field)
