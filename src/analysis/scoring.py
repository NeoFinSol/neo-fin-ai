import logging
from typing import Any

logger = logging.getLogger(__name__)

# Weights for integral scoring — sum must equal 1.0
# Based on standard financial analysis methodology (РСБУ/МСФО)
# Liquidity: 25%, Profitability: 35%, Stability: 25%, Activity: 15%
WEIGHTS = {
    # Liquidity (25%)
    "Коэффициент текущей ликвидности": 0.15,
    "Коэффициент быстрой ликвидности": 0.07,
    "Коэффициент абсолютной ликвидности": 0.03,
    # Profitability (35%)
    "Рентабельность активов (ROA)": 0.10,
    "Рентабельность собственного капитала (ROE)": 0.10,
    "Рентабельность продаж (ROS)": 0.08,
    "EBITDA маржа": 0.07,
    # Financial stability (25%)
    "Коэффициент автономии": 0.12,
    "Финансовый рычаг": 0.08,
    "Покрытие процентов": 0.05,
    # Business activity (15%)
    "Оборачиваемость активов": 0.05,
    "Оборачиваемость запасов": 0.05,
    "Оборачиваемость дебиторской задолженности": 0.05,
}

# Industry benchmarks for normalization (retail/general Russian market, РСБУ)
# Format: (target_value, is_higher_better)
_BENCHMARKS: dict[str, tuple[float, bool]] = {
    # Liquidity — нормативные значения по РСБУ
    "Коэффициент текущей ликвидности": (2.0, True),       # норма ≥ 2.0
    "Коэффициент быстрой ликвидности": (1.0, True),       # норма ≥ 1.0
    "Коэффициент абсолютной ликвидности": (0.2, True),    # норма ≥ 0.2
    # Profitability — средние по рынку РФ (ритейл/промышленность)
    "Рентабельность активов (ROA)": (0.08, True),         # 8% — хороший уровень
    "Рентабельность собственного капитала (ROE)": (0.15, True),  # 15% — норма
    "Рентабельность продаж (ROS)": (0.10, True),          # 10% — норма
    "EBITDA маржа": (0.15, True),                         # 15% — норма
    # Financial stability
    "Коэффициент автономии": (0.5, True),                 # норма ≥ 0.5
    "Финансовый рычаг": (1.0, False),                     # норма ≤ 1.0 (меньше — лучше)
    "Покрытие процентов": (3.0, True),                    # норма ≥ 3.0
    # Business activity — оборачиваемость (разы в год)
    "Оборачиваемость активов": (1.0, True),               # норма ≥ 1.0
    "Оборачиваемость запасов": (8.0, True),               # норма ≥ 8 раз/год (ритейл)
    "Оборачиваемость дебиторской задолженности": (8.0, True),  # норма ≥ 8 раз/год
}


def calculate_integral_score(ratios: dict[str, Any]) -> dict[str, Any]:
    """
    Calculate integral financial score (0–100) based on up to 12 ratios.

    Uses weighted normalization against industry benchmarks (РСБУ).
    Missing ratios are excluded from calculation (weight redistributed).

    Args:
        ratios: Dictionary with Russian ratio keys from calculate_ratios()

    Returns:
        dict with keys: score (float), risk_level (str), details (dict[str, float])
    """
    normalized: dict[str, float] = {}
    total_weight = 0.0
    weighted_sum = 0.0

    for ratio_name, weight in WEIGHTS.items():
        value = _to_number(ratios.get(ratio_name))
        score = _normalize_ratio(ratio_name, value)
        if score is None:
            continue
        normalized[ratio_name] = round(score, 4)
        weighted_sum += score * weight
        total_weight += weight

    if total_weight == 0:
        integral_score = 0.0
    else:
        # Rescale to account for missing ratios
        integral_score = (weighted_sum / total_weight) * 100

    risk_level = _risk_level(integral_score)

    return {
        "score": round(integral_score, 2),
        "risk_level": risk_level,
        "details": normalized,
    }


def _normalize_ratio(ratio_name: str, value: float | None) -> float | None:
    """
    Normalize a ratio value to [0, 1] range using benchmark targets.

    Args:
        ratio_name: Russian name of the ratio
        value: Numeric value of the ratio

    Returns:
        Normalized score in [0, 1] or None if value is None
    """
    if value is None:
        return None

    benchmark = _BENCHMARKS.get(ratio_name)
    if benchmark is None:
        return None

    target, higher_is_better = benchmark

    if higher_is_better:
        return _normalize_positive(value, target)
    else:
        return _normalize_inverse(value, max_acceptable=target * 2)


def _normalize_positive(value: float, target: float) -> float:
    """Normalize: higher is better. Returns 1.0 when value >= target."""
    if value <= 0:
        return 0.0
    return min(value / target, 1.0)


def _normalize_inverse(value: float, max_acceptable: float) -> float:
    """Normalize: lower is better. Returns 1.0 when value <= 0, 0.0 when value >= max."""
    if value <= 0:
        return 1.0
    if max_acceptable <= 0:
        return 0.0
    if value >= max_acceptable:
        return 0.0
    return 1.0 - (value / max_acceptable)


def _risk_level(score: float) -> str:
    """Map integral score to risk level."""
    if score >= 75:
        return "низкий"
    if score >= 50:
        return "средний"
    return "высокий"


def _to_number(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        logger.warning("Failed to convert ratio value to float: %r", value)
        return None
