import logging
from typing import Any

from src.analysis.ratios import RATIO_KEY_MAP, calculate_ratios, translate_ratios
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
_SCORING_DETECTION_MODE = "auto"
_PERIOD_REPORTED = "reported"
_PERIOD_ANNUALIZED_Q1 = "annualized_q1"
_PERIOD_ANNUALIZED_H1 = "annualized_h1"
_LEVERAGE_BASIS_TOTAL = "total_liabilities"
_LEVERAGE_BASIS_DEBT_ONLY = "debt_only"
_LEVERAGE_TOTAL_RU = "Финансовый рычаг (обязательства/капитал)"
_LEVERAGE_DEBT_ONLY_RU = "Финансовый рычаг (долг/капитал)"
_RETAIL_PEER_CONTEXT = [
    "Large food retail may operate with current ratio below 1; Walmart current ratio ~0.79 (Jan 2026 reference).",
]
_RETAIL_KEYWORDS = (
    "магнит",
    "x5",
    "лента",
    "fix price",
    "окей",
    "детский мир",
    "retail",
    "рознич",
    "торговая сеть",
    "магазин",
)
_Q1_MARKERS = ("1 квартал", "q1", "three months", "январь - март", "январь-март")
_H1_MARKERS = ("1 полугодие", "h1", "half-year", "six months", "январь - июнь", "январь-июнь")
_ANNUALIZATION_FACTORS = {
    _PERIOD_ANNUALIZED_Q1: 4.0,
    _PERIOD_ANNUALIZED_H1: 2.0,
}
_ANNUALIZED_METRIC_KEYS = (
    "revenue",
    "net_profit",
    "ebitda",
    "ebit",
    "interest_expense",
    "cost_of_goods_sold",
)

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
        "Коэффициент текущей ликвидности": (2.0, True),
        "Коэффициент быстрой ликвидности": (1.0, True),
        "Коэффициент абсолютной ликвидности": (0.2, True),
        "Рентабельность активов (ROA)": (0.08, True),
        "Рентабельность собственного капитала (ROE)": (0.15, True),
        "Рентабельность продаж (ROS)": (0.10, True),
        "EBITDA маржа": (0.15, True),
        "Коэффициент автономии": (0.5, True),
        "Финансовый рычаг": (1.0, False),
        "Покрытие процентов": (3.0, True),
        "Оборачиваемость активов": (1.0, True),
        "Оборачиваемость запасов": (8.0, True),
        "Оборачиваемость дебиторской задолженности": (8.0, True),
    },
    "retail_demo": {
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

# Anomaly limits per ratio — values outside these bounds are almost certainly
# extraction errors (e.g. scale factor not applied) and must not be normalised.
# Format: (min_valid, max_valid)
_ANOMALY_LIMITS: dict[str, tuple[float, float]] = {
    "Рентабельность активов (ROA)": (-1.0, 2.0),
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


def _resolve_scoring_profile(profile: str | None = None) -> str:
    resolved_profile = (profile or app_settings.scoring_profile or "auto").strip().lower()
    if resolved_profile == "auto":
        return "generic"
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
    Calculate integral financial score (0–100) based on available ratios.

    Missing ratios are excluded from calculation with weight redistribution.
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
        integral_score = (weighted_sum / total_weight) * 100
        confidence_score = round(total_weight, 2)

    risk_level = _risk_level(integral_score)
    return {
        "score": round(integral_score, 2),
        "risk_level": risk_level,
        "details": normalized,
        "confidence_score": confidence_score,
        "profile": active_profile,
    }


def resolve_scoring_methodology(
    metrics: dict[str, Any],
    ratios_en: dict[str, Any] | None = None,
    filename: str | None = None,
    text: str | None = None,
) -> dict[str, Any]:
    """Resolve benchmark profile and period basis from document context."""
    context = _normalize_scoring_context(filename, text)
    resolved_ratios = ratios_en or {}
    benchmark_profile, benchmark_reasons = _detect_benchmark_profile(
        metrics,
        resolved_ratios,
        context,
    )
    period_basis, period_reasons = _detect_period_basis(metrics, context)
    return {
        "benchmark_profile": benchmark_profile,
        "period_basis": period_basis,
        "detection_mode": _SCORING_DETECTION_MODE,
        "reasons": benchmark_reasons + period_reasons,
        "guardrails": [],
        "leverage_basis": _LEVERAGE_BASIS_TOTAL,
        "ifrs16_adjusted": False,
        "adjustments": [],
        "peer_context": list(_RETAIL_PEER_CONTEXT) if benchmark_profile == "retail_demo" else [],
    }


def annualize_metrics_for_period(
    metrics: dict[str, Any],
    period_basis: str,
) -> dict[str, Any]:
    """Annualize only interim P&L/activity metrics; keep balance metrics untouched."""
    factor = _ANNUALIZATION_FACTORS.get(period_basis)
    if factor is None:
        return dict(metrics)

    annualized = dict(metrics)
    for key in _ANNUALIZED_METRIC_KEYS:
        value = _to_number(metrics.get(key))
        annualized[key] = None if value is None else value * factor
    return annualized


def calculate_score_with_context(
    metrics: dict[str, Any],
    filename: str | None = None,
    text: str | None = None,
    extraction_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Run document-aware scoring with retail/interim auto-detection."""
    base_ratios_ru = calculate_ratios(metrics)
    base_ratios_en = translate_ratios(base_ratios_ru)
    methodology = resolve_scoring_methodology(
        metrics,
        ratios_en=base_ratios_en,
        filename=filename,
        text=text,
    )
    scoring_metrics = annualize_metrics_for_period(metrics, methodology["period_basis"])
    ratios_ru = calculate_ratios(scoring_metrics)
    ratios_en = translate_ratios(ratios_ru)
    ratios_ru, ratios_en, methodology = _apply_scoring_methodology_adjustments(
        ratios_ru,
        ratios_en,
        methodology,
        scoring_metrics,
        extraction_metadata=extraction_metadata,
    )
    raw_score = calculate_integral_score(
        ratios_ru,
        profile=methodology["benchmark_profile"],
    )
    raw_score["methodology"] = methodology
    score_payload = build_score_payload(raw_score, ratios_en, methodology=methodology)
    score_payload = apply_data_quality_guardrails(score_payload, metrics)
    return {
        "ratios_ru": ratios_ru,
        "ratios_en": ratios_en,
        "raw_score": raw_score,
        "score_payload": score_payload,
        "methodology": score_payload["methodology"],
    }


def build_score_payload(
    raw_score: dict[str, Any],
    ratios_en: dict[str, Any],
    methodology: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Transform backend score structure to match frontend ScoreData interface.
    """
    details = raw_score.get("details", {})
    normalized_methodology = _normalize_methodology(
        methodology or raw_score.get("methodology") or {"benchmark_profile": raw_score.get("profile")}
    )
    active_profile = _resolve_scoring_profile(normalized_methodology.get("benchmark_profile"))
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
        "score": raw_score.get("score", 0.0),
        "risk_level": translate_risk_level(raw_score.get("risk_level", "высокий")),
        "confidence_score": raw_score.get("confidence_score", 0.0),
        "factors": factors,
        "normalized_scores": normalized_scores,
        "methodology": {
            **normalized_methodology,
            "benchmark_profile": active_profile,
        },
    }


def apply_data_quality_guardrails(
    score_payload: dict[str, Any],
    metrics: dict[str, Any],
) -> dict[str, Any]:
    """Downgrade overconfident scores when critical extraction coverage is weak."""
    adjusted = dict(score_payload)
    methodology = _normalize_methodology(adjusted.get("methodology"))
    current_score = float(adjusted.get("score", 0.0) or 0.0)
    confidence_score = float(adjusted.get("confidence_score", 0.0) or 0.0)

    missing_core = [key for key in _CORE_SCORE_KEYS if metrics.get(key) is None]
    missing_supporting = [key for key in _SUPPORTING_SCORE_KEYS if metrics.get(key) is None]

    capped_score = current_score
    applied_guardrails: list[str] = []
    if missing_core:
        capped_score = min(capped_score, 39.99)
        applied_guardrails = [f"missing_core:{key}" for key in missing_core]
    elif missing_supporting:
        capped_score = min(capped_score, 54.99)
        applied_guardrails = [f"missing_supporting:{key}" for key in missing_supporting]
    elif confidence_score < 0.4:
        capped_score = min(capped_score, 59.99)
        applied_guardrails = ["low_confidence"]

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
        methodology["guardrails"] = _merge_unique_strings(
            methodology["guardrails"],
            applied_guardrails,
        )

    adjusted["methodology"] = methodology
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

    numeric_actual = _to_number(actual_val)
    if numeric_actual is not None:
        val_str = "%.2f" % numeric_actual
    else:
        val_str = str(actual_val)

    if benchmark is None:
        return "Значение: %s" % val_str

    if numeric_actual is None:
        return "Значение: %s" % val_str

    target, higher_is_better = benchmark
    target_str = "%.2f" % target

    if higher_is_better:
        norm = "норма ≥ %s" % target_str
        if numeric_actual >= target:
            return "Значение %s — в норме (%s)" % (val_str, norm)
        return "Значение %s — ниже нормы (%s)" % (val_str, norm)

    norm = "норма ≤ %s" % target_str
    if numeric_actual <= target:
        return "Значение %s — в норме (%s)" % (val_str, norm)
    return "Значение %s — выше нормы (%s)" % (val_str, norm)


def _normalize_scoring_context(filename: str | None, text: str | None) -> str:
    return " ".join(part for part in (filename or "", text or "") if part).casefold()


def _detect_benchmark_profile(
    metrics: dict[str, Any],
    ratios_en: dict[str, Any],
    context: str,
) -> tuple[str, list[str]]:
    for keyword in _RETAIL_KEYWORDS:
        if keyword in context:
            return "retail_demo", ["retail_keyword"]

    inventory = _to_number(metrics.get("inventory"))
    asset_turnover = _to_number(ratios_en.get("asset_turnover"))
    receivables_turnover = _to_number(ratios_en.get("receivables_turnover"))
    if inventory is not None and (
        (asset_turnover is not None and asset_turnover >= 1.2)
        or (receivables_turnover is not None and receivables_turnover >= 20.0)
    ):
        return "retail_demo", ["retail_structure"]

    return "generic", []


def _detect_period_basis(
    metrics: dict[str, Any],
    context: str,
) -> tuple[str, list[str]]:
    revenue = _to_number(metrics.get("revenue"))
    has_q1_marker = any(marker in context for marker in _Q1_MARKERS)
    has_h1_marker = any(marker in context for marker in _H1_MARKERS)

    if revenue is None and (has_q1_marker or has_h1_marker):
        return _PERIOD_REPORTED, []
    if has_q1_marker:
        return _PERIOD_ANNUALIZED_Q1, ["period_marker:q1"]
    if has_h1_marker:
        return _PERIOD_ANNUALIZED_H1, ["period_marker:h1"]
    return _PERIOD_REPORTED, []


def _normalize_methodology(methodology: dict[str, Any] | None) -> dict[str, Any]:
    normalized = {
        "benchmark_profile": "generic",
        "period_basis": _PERIOD_REPORTED,
        "detection_mode": _SCORING_DETECTION_MODE,
        "reasons": [],
        "guardrails": [],
        "leverage_basis": _LEVERAGE_BASIS_TOTAL,
        "ifrs16_adjusted": False,
        "adjustments": [],
        "peer_context": [],
    }
    if not isinstance(methodology, dict):
        return normalized

    benchmark_profile = _resolve_scoring_profile(methodology.get("benchmark_profile"))
    normalized["benchmark_profile"] = benchmark_profile
    period_basis = str(methodology.get("period_basis") or _PERIOD_REPORTED).strip().lower()
    if period_basis not in {_PERIOD_REPORTED, _PERIOD_ANNUALIZED_Q1, _PERIOD_ANNUALIZED_H1}:
        period_basis = _PERIOD_REPORTED
    normalized["period_basis"] = period_basis
    normalized["detection_mode"] = _SCORING_DETECTION_MODE
    normalized["reasons"] = _merge_unique_strings([], methodology.get("reasons", []))
    normalized["guardrails"] = _merge_unique_strings([], methodology.get("guardrails", []))
    leverage_basis = str(methodology.get("leverage_basis") or _LEVERAGE_BASIS_TOTAL).strip().lower()
    if leverage_basis not in {_LEVERAGE_BASIS_TOTAL, _LEVERAGE_BASIS_DEBT_ONLY}:
        leverage_basis = _LEVERAGE_BASIS_TOTAL
    normalized["leverage_basis"] = leverage_basis
    normalized["ifrs16_adjusted"] = bool(methodology.get("ifrs16_adjusted", False))
    normalized["adjustments"] = _merge_unique_strings([], methodology.get("adjustments", []))
    normalized["peer_context"] = _merge_unique_strings([], methodology.get("peer_context", []))
    return normalized


def _apply_scoring_methodology_adjustments(
    ratios_ru: dict[str, Any],
    ratios_en: dict[str, Any],
    methodology: dict[str, Any],
    metrics: dict[str, Any],
    extraction_metadata: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    adjusted_ratios_ru = dict(ratios_ru)
    adjusted_ratios_en = dict(ratios_en)
    adjusted_methodology = _normalize_methodology(methodology)

    total_leverage = _to_number(adjusted_ratios_ru.get(_LEVERAGE_TOTAL_RU))
    debt_only_leverage = _to_number(adjusted_ratios_ru.get(_LEVERAGE_DEBT_ONLY_RU))

    leverage_basis = _LEVERAGE_BASIS_TOTAL
    active_leverage = total_leverage
    if (
        adjusted_methodology["benchmark_profile"] == "retail_demo"
        and debt_only_leverage is not None
    ):
        leverage_basis = _LEVERAGE_BASIS_DEBT_ONLY
        active_leverage = debt_only_leverage
        adjusted_methodology["adjustments"] = _merge_unique_strings(
            adjusted_methodology["adjustments"],
            ["leverage_debt_only"],
        )

    adjusted_methodology["leverage_basis"] = leverage_basis
    adjusted_ratios_ru["Финансовый рычаг"] = active_leverage
    adjusted_ratios_en["financial_leverage_total"] = total_leverage
    adjusted_ratios_en["financial_leverage_debt_only"] = debt_only_leverage
    adjusted_ratios_en["financial_leverage"] = active_leverage

    interest_expense = _to_number(metrics.get("interest_expense"))
    if interest_expense is not None and interest_expense < 0:
        adjusted_methodology["adjustments"] = _merge_unique_strings(
            adjusted_methodology["adjustments"],
            ["interest_coverage_sign_corrected"],
        )

    issuer_adjustments = _extract_issuer_adjustment_codes(extraction_metadata)
    adjusted_methodology["adjustments"] = _merge_unique_strings(
        adjusted_methodology["adjustments"],
        issuer_adjustments,
    )

    has_lease_metrics = any(
        metrics.get(key) is not None
        for key in ("short_term_lease_liabilities", "long_term_lease_liabilities")
    )
    adjusted_methodology["ifrs16_adjusted"] = bool(
        leverage_basis == _LEVERAGE_BASIS_DEBT_ONLY or has_lease_metrics or issuer_adjustments
    )
    if adjusted_methodology["benchmark_profile"] == "retail_demo":
        adjusted_methodology["peer_context"] = _merge_unique_strings(
            [],
            _RETAIL_PEER_CONTEXT,
        )

    return adjusted_ratios_ru, adjusted_ratios_en, adjusted_methodology


def _extract_issuer_adjustment_codes(
    extraction_metadata: dict[str, Any] | None,
) -> list[str]:
    if not isinstance(extraction_metadata, dict):
        return []

    adjustments: list[str] = []
    for metric_key, item in extraction_metadata.items():
        source = None
        if isinstance(item, dict):
            source = item.get("source")
        else:
            source = getattr(item, "source", None)
        if source == "issuer_fallback":
            adjustments = _merge_unique_strings(
                adjustments,
                [f"issuer_override:{metric_key}"],
            )
    return adjustments


def _merge_unique_strings(existing: list[str], extra: Any) -> list[str]:
    merged = list(existing)
    if not isinstance(extra, list):
        return merged
    for item in extra:
        if not isinstance(item, str):
            continue
        if item not in merged:
            merged.append(item)
    return merged


def _normalize_ratio(
    ratio_name: str,
    value: float | None,
    benchmarks: dict[str, tuple[float, bool]] | None = None,
) -> float | None:
    if value is None:
        return None

    limits = _ANOMALY_LIMITS.get(ratio_name)
    if limits is not None:
        min_val, max_val = limits
        if not (min_val <= value <= max_val):
            logger.warning(
                "Anomalous ratio blocked from scoring: %s = %s (expected [%s, %s])",
                ratio_name,
                value,
                min_val,
                max_val,
            )
            return None

    active_benchmarks = benchmarks or BENCHMARKS_BY_PROFILE["generic"]
    benchmark = active_benchmarks.get(ratio_name)
    if benchmark is None:
        return None

    target, higher_is_better = benchmark
    if higher_is_better:
        return _normalize_positive(value, target)
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
