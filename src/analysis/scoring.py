import logging
from typing import Any

logger = logging.getLogger(__name__)


def calculate_integral_score(ratios: dict[str, Any]) -> dict[str, Any]:
    weights = {
        "Коэффициент текущей ликвидности": 0.3,
        "Коэффициент автономии": 0.2,
        "Рентабельность активов (ROA)": 0.2,
        "Рентабельность собственного капитала (ROE)": 0.2,
        "Финансовый рычаг": 0.1,
    }

    normalized: dict[str, float] = {}
    total_weight = 0.0
    weighted_sum = 0.0

    for ratio_name, weight in weights.items():
        value = _to_number(ratios.get(ratio_name))
        score = _normalize_ratio(ratio_name, value)
        if score is None:
            continue
        normalized[ratio_name] = score
        weighted_sum += score * weight
        total_weight += weight

    if total_weight == 0:
        integral_score = 0.0
    else:
        integral_score = (weighted_sum / total_weight) * 100

    risk_level = _risk_level(integral_score)

    return {
        "score": round(integral_score, 2),
        "risk_level": risk_level,
        "details": normalized,
    }


def _normalize_ratio(ratio_name: str, value: float | None) -> float | None:
    if value is None:
        return None

    if ratio_name == "Коэффициент текущей ликвидности":
        return _normalize_positive(value, target=2.0)
    if ratio_name == "Коэффициент автономии":
        return _normalize_positive(value, target=0.5)
    if ratio_name == "Рентабельность активов (ROA)":
        return _normalize_positive(value, target=0.1)
    if ratio_name == "Рентабельность собственного капитала (ROE)":
        return _normalize_positive(value, target=0.2)
    if ratio_name == "Финансовый рычаг":
        return _normalize_inverse(value, max_acceptable=2.0)

    return None


def _normalize_positive(value: float, target: float) -> float:
    if value <= 0:
        return 0.0
    return min(value / target, 1.0)


def _normalize_inverse(value: float, max_acceptable: float) -> float:
    if value <= 0:
        return 1.0
    if value >= max_acceptable:
        return 0.0
    return 1.0 - (value / max_acceptable)


def _risk_level(score: float) -> str:
    if score >= 80:
        return "низкий"
    if score >= 60:
        return "средний"
    return "высокий"


def _to_number(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        logger.warning("Failed to convert ratio value: %s", value)
        return None
