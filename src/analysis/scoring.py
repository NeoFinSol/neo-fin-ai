import logging
from typing import Any

from src.analysis.ratios import RATIO_KEY_MAP
from src.models.settings import app_settings

logger = logging.getLogger(__name__)

_CORE_SCORE_KEYS = (
    "revenue",
    "total_assets",
    "liabilities",
    "current_assets",
    "short_term_liabilities",
)
_SUPPORTING_SCORE_KEYS = ("net_profit", "equity")

# Human-readable names for frontend display
FRIENDLY_NAMES: dict[str, str] = {
    "Коэффициент текущей ликвидности": "Текущая ликвидность",
    "Коэффициент быстрой ликвидности": "Быстрая ликвидность",
    "Коэффициент абсолютной ликвидности": "Абсолютная ликвидность",
    "Рентабельность активов (ROA)": "Рентабельность активов",
    "Рентабельность собственного капитала (ROE)": "Рентабельность капитала",
    "Рентабельность продаж (ROS)": "Рентабельность продаж",
    "EBITDA маржа": "EBITDA маржа",
    "Коэффициент автономии": "Финансовая независимость",
    "Финансовый рычаг": "Финансовый рычаг",
    "Покрытие процентов": "Покрытие процентов",
    "Оборачиваемость активов": "Оборачиваемость активов",
    "Оборачиваемость запасов": "Оборачиваемость запасов",
    "Оборачиваемость дебиторской задолженности": "Оборачиваемость ДЗ",
}

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

# Industry benchmarks for normalization by profile.
# Format: (target_value, is_higher_better)
BENCHMARKS_BY_PROFILE: dict[str, dict[str, tuple[float, bool]]] = {
    "generic": {
        # Liquidity — нормативные значения по РСБУ
        "Коэффициент текущей ликвидности": (2.0, True),       # норма ≥ 2.0
        "Коэффициент быстрой ликвидности": (1.0, True),       # норма ≥ 1.0
        "Коэффициент абсолютной ликвидности": (0.2, True),    # норма ≥ 0.2
        # Profitability — средние по рынку РФ
        "Рентабельность активов (ROA)": (0.08, True),
        "Рентабельность собственного капитала (ROE)": (0.15, True),
        "Рентабельность продаж (ROS)": (0.10, True),
        "EBITDA маржа": (0.15, True),
        # Financial stability
        "Коэффициент автономии": (0.5, True),
        "Финансовый рычаг": (1.0, False),
        "Покрытие процентов": (3.0, True),
        # Business activity
        "Оборачиваемость активов": (1.0, True),
        "Оборачиваемость запасов": (8.0, True),
        "Оборачиваемость дебиторской задолженности": (8.0, True),
    },
    "retail_demo": {
        # Retail-friendly thresholds for demo-readiness (without weakening anomaly blocking)
        "Коэффициент текущей ликвидности": (1.0, True),
        "Коэффициент быстрой ликвидности": (0.7, True),
        "Коэффициент абсолютной ликвидности": (0.1, True),
        "Рентабельность активов (ROA)": (0.05, True),
        "Рентабельность собственного капитала (ROE)": (0.12, True),
        "Рентабельность продаж (ROS)": (0.04, True),
        "EBITDA маржа": (0.08, True),
        "Коэффициент автономии": (0.35, True),
        "Финансовый рычаг": (2.0, False),
        "Покрытие процентов": (2.0, True),
        "Оборачиваемость активов": (1.5, True),
        "Оборачиваемость запасов": (10.0, True),
        "Оборачиваемость дебиторской задолженности": (10.0, True),
    },
}


def _resolve_scoring_profile(profile: str | None = None) -> str:
    resolved_profile = (profile or app_settings.scoring_profile or "generic").strip().lower()
    if resolved_profile not in BENCHMARKS_BY_PROFILE:
        logger.warning(
            "Unknown scoring profile %r, using generic profile",
            resolved_profile,
        )
        return "generic"
    return resolved_profile


def calculate_integral_score(
    ratios: dict[str, Any],
    profile: str | None = None,
) -> dict[str, Any]:
    """
    Calculate integral financial score (0–100) based on up to 12 ratios.

    Uses weighted normalization against industry benchmarks (РСБУ).
    Missing ratios are excluded from calculation (weight redistributed).

    Args:
        ratios: Dictionary with Russian ratio keys from calculate_ratios()

    Returns:
        dict with keys: score (float), risk_level (str), details (dict[str, float])
    """
    active_profile = _resolve_scoring_profile(profile)
    benchmarks = BENCHMARKS_BY_PROFILE[active_profile]
    normalized: dict[str, float] = {}
    total_weight = 0.0
    weighted_sum = 0.0

    for ratio_name, weight in WEIGHTS.items():
        value = _to_number(ratios.get(ratio_name))
        score = _normalize_ratio(ratio_name, value, benchmarks=benchmarks)
        if score is None:
            continue
        normalized[ratio_name] = round(score, 4)
        weighted_sum += score * weight
        total_weight += weight

    if total_weight == 0:
        integral_score = 0.0
        confidence_score = 0.0
    else:
        # Rescale to account for missing ratios
        integral_score = (weighted_sum / total_weight) * 100
        # Confidence depends on how much weight we actually have
        confidence_score = round(total_weight, 2)

    risk_level = _risk_level(integral_score)

    return {
        "score": round(integral_score, 2),
        "risk_level": risk_level,
        "details": normalized,
        "confidence_score": confidence_score,
        "profile": active_profile,
    }


def build_score_payload(raw_score: dict, ratios_en: dict) -> dict:
    """
    Transform backend score structure to match frontend ScoreData interface.

    Frontend expects:
      { score, risk_level, factors: [{name, description, impact}],
        normalized_scores: {en_key: float | null, ...} }
    """
    details = raw_score.get("details", {})  # normalized 0-1 values per ratio (RU keys)
    active_profile = _resolve_scoring_profile(raw_score.get("profile"))
    benchmarks = BENCHMARKS_BY_PROFILE[active_profile]

    factors = []
    normalized_scores: dict[str, float | None] = {
        en_key: None for en_key in RATIO_KEY_MAP.values()
    }

    for ru_name, norm_val in details.items():
        en_key = RATIO_KEY_MAP.get(ru_name)
        if not en_key:
            continue

        normalized_scores[en_key] = norm_val
        actual_val = ratios_en.get(en_key)

        # Determine impact based on normalized score
        if norm_val is None:
            impact = "neutral"
        elif norm_val >= 0.65:
            impact = "positive"
        elif norm_val >= 0.35:
            impact = "neutral"
        else:
            impact = "negative"

        friendly_name = FRIENDLY_NAMES.get(ru_name, ru_name)
        benchmark = benchmarks.get(ru_name)
        description = _build_factor_description(ru_name, actual_val, benchmark)

        factors.append({
            "name": friendly_name,
            "description": description,
            "impact": impact,
        })

    return {
        "score": raw_score.get("score", 0),
        "risk_level": translate_risk_level(raw_score.get("risk_level", "высокий")),
        "confidence_score": raw_score.get("confidence_score", 0.0),
        "factors": factors,
        "normalized_scores": normalized_scores,
    }


def apply_data_quality_guardrails(
    score_payload: dict[str, Any],
    metrics: dict[str, Any],
) -> dict[str, Any]:
    """Downgrade overconfident scores when critical extraction coverage is weak."""
    adjusted = dict(score_payload)
    current_score = float(adjusted.get("score", 0.0) or 0.0)
    confidence_score = float(adjusted.get("confidence_score", 0.0) or 0.0)

    missing_core = [key for key in _CORE_SCORE_KEYS if metrics.get(key) is None]
    missing_supporting = [key for key in _SUPPORTING_SCORE_KEYS if metrics.get(key) is None]

    capped_score = current_score
    if missing_core:
        capped_score = min(capped_score, 39.99)
    elif missing_supporting:
        capped_score = min(capped_score, 54.99)
    elif confidence_score < 0.4:
        capped_score = min(capped_score, 59.99)

    if capped_score != current_score:
        logger.warning(
            "Score downgraded by data-quality guardrail: score=%s -> %s, "
            "missing_core=%s, missing_supporting=%s, confidence=%s",
            current_score,
            capped_score,
            missing_core,
            missing_supporting,
            confidence_score,
        )
        adjusted["score"] = round(capped_score, 2)
        adjusted["risk_level"] = translate_risk_level(_risk_level(capped_score))

    return adjusted


def translate_risk_level(ru: str) -> str:
    """Translate Russian risk level to English."""
    return {
        "низкий": "low",
        "средний": "medium",
        "высокий": "high",
        "критический": "critical",
    }.get(ru, "high")


def _build_factor_description(
    ratio_name: str,
    actual_val: float | None,
    benchmark: tuple[float, bool] | None,
) -> str:
    """Build a human-readable description for a scoring factor."""
    if actual_val is None:
        return "Данные недоступны"

    if isinstance(actual_val, (int, float)):
        val_str = "%.2f" % actual_val
    else:
        try:
            val_str = "%.2f" % float(actual_val)
        except (TypeError, ValueError):
            val_str = str(actual_val)

    if benchmark is None:
        return "Значение: %s" % val_str

    target, higher_is_better = benchmark
    target_str = "%.2f" % target

    if higher_is_better:
        norm = "норма ≥ %s" % target_str
        if actual_val >= target:
            return "Значение %s — в норме (%s)" % (val_str, norm)
        return "Значение %s — ниже нормы (%s)" % (val_str, norm)
    else:
        norm = "норма ≤ %s" % target_str
        if actual_val <= target:
            return "Значение %s — в норме (%s)" % (val_str, norm)
        return "Значение %s — выше нормы (%s)" % (val_str, norm)


# Anomaly limits per ratio — values outside these bounds are almost certainly
# extraction errors (e.g. scale factor not applied) and must not be normalised.
# Format: (min_valid, max_valid)
_ANOMALY_LIMITS: dict[str, tuple[float, float]] = {
    "Рентабельность активов (ROA)": (-1.0, 2.0),           # -100% to +200%
    "Рентабельность собственного капитала (ROE)": (-5.0, 5.0),
    "Рентабельность продаж (ROS)": (-2.0, 2.0),
    "EBITDA маржа": (-2.0, 2.0),
    "Коэффициент автономии": (-1.0, 1.5),
    "Финансовый рычаг": (0.0, 100.0),
    "Покрытие процентов": (-50.0, 500.0),
    "Оборачиваемость активов": (0.0, 50.0),
    "Оборачиваемость запасов": (0.0, 500.0),
    "Оборачиваемость дебиторской задолженности": (0.0, 500.0),
}


def _normalize_ratio(
    ratio_name: str,
    value: float | None,
    benchmarks: dict[str, tuple[float, bool]] | None = None,
) -> float | None:
    """
    Normalize a ratio value to [0, 1] range using benchmark targets.

    Args:
        ratio_name: Russian name of the ratio
        value: Numeric value of the ratio

    Returns:
        Normalized score in [0, 1] or None if value is None or anomalous
    """
    if value is None:
        return None

    # Block anomalous values — almost certainly extraction errors (wrong scale factor etc.)
    limits = _ANOMALY_LIMITS.get(ratio_name)
    if limits is not None:
        min_val, max_val = limits
        if not (min_val <= value <= max_val):
            logger.warning(
                "Anomalous ratio blocked from scoring: %s = %s (expected [%s, %s])",
                ratio_name, value, min_val, max_val,
            )
            return None

    active_benchmarks = benchmarks or BENCHMARKS_BY_PROFILE["generic"]
    benchmark = active_benchmarks.get(ratio_name)
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
    if score >= 55:
        return "средний"
    if score >= 35:
        return "высокий"
    return "критический"


def _to_number(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        logger.warning("Failed to convert ratio value to float: %r", value)
        return None
