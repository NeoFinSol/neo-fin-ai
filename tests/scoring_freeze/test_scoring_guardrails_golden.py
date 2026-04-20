from __future__ import annotations

from copy import deepcopy
from typing import Any

from src.analysis.scoring import (
    calculate_score_from_precomputed_ratios,
    calculate_score_with_context,
)

_BASE_METRICS: dict[str, Any] = {
    "revenue": 120_000_000.0,
    "net_profit": 5_000_000.0,
    "total_assets": 80_000_000.0,
    "liabilities": 30_000_000.0,
    "current_assets": 40_000_000.0,
    "short_term_liabilities": 20_000_000.0,
    "equity": 50_000_000.0,
    "cash_and_equivalents": 10_000_000.0,
    "inventory": 15_000_000.0,
    "cost_of_goods_sold": 90_000_000.0,
    "accounts_receivable": 10_000_000.0,
    "ebitda": 12_000_000.0,
    "ebit": 9_000_000.0,
    "interest_expense": 1_000_000.0,
}

_BASE_PRECOMPUTED_RATIOS_RU: dict[str, float] = {
    "Коэффициент текущей ликвидности": 2.0,
    "Коэффициент быстрой ликвидности": 1.0,
    "Коэффициент абсолютной ликвидности": 0.5,
    "Рентабельность активов (ROA)": 0.1,
    "Рентабельность собственного капитала (ROE)": 0.2,
    "Рентабельность продаж (ROS)": 0.2,
    "EBITDA маржа": 0.3,
    "Коэффициент автономии": 0.4,
    "Финансовый рычаг": 1.2,
    "Покрытие процентов": 5.0,
    "Оборачиваемость активов": 2.0,
    "Оборачиваемость запасов": 11.0,
    "Оборачиваемость дебиторской задолженности": 12.0,
}

_BASE_PRECOMPUTED_METHOD: dict[str, Any] = {
    "benchmark_profile": "generic",
    "period_basis": "reported",
    "reasons": [],
    "guardrails": [],
    "adjustments": [],
    "peer_context": [],
}


def test_cap_applied_for_missing_core_data() -> None:
    result = _run_document_case(metrics_overrides={"revenue": None})
    assert result["score_payload"]["score"] == 39.99
    assert result["methodology"]["guardrails"] == ["missing_core:revenue"]


def test_cap_not_applied_when_score_below_cap_threshold() -> None:
    result = _run_precomputed_case(
        ratios_ru_overrides={
            "Коэффициент текущей ликвидности": 0.05,
            "Коэффициент быстрой ликвидности": 0.01,
            "Коэффициент абсолютной ликвидности": 0.0,
            "Рентабельность продаж (ROS)": -1.5,
            "Рентабельность собственного капитала (ROE)": -3.0,
            "Коэффициент автономии": -0.8,
        }
    )
    assert result["score_payload"]["score"] < 59.99
    assert result["methodology"]["guardrails"] == []


def test_exclusion_applied_when_anomaly_limit_triggered() -> None:
    result = _run_precomputed_case(
        ratios_ru_overrides={"Рентабельность продаж (ROS)": 2.01}
    )
    assert result["score_payload"]["normalized_scores"]["ros"] is None


def test_exclusion_not_applied_with_normal_ratio_values() -> None:
    result = _run_precomputed_case(
        ratios_ru_overrides={"Рентабельность продаж (ROS)": 0.25}
    )
    assert result["score_payload"]["normalized_scores"]["ros"] == 1.0


def test_anomaly_limit_triggered_blocks_out_of_range_metric() -> None:
    result = _run_precomputed_case(
        ratios_ru_overrides={"Рентабельность продаж (ROS)": -2.01}
    )
    assert result["score_payload"]["normalized_scores"]["ros"] is None


def test_anomaly_limit_near_boundary_not_triggered() -> None:
    result = _run_precomputed_case(
        ratios_ru_overrides={"Рентабельность продаж (ROS)": 2.0}
    )
    assert result["score_payload"]["normalized_scores"]["ros"] == 1.0


def test_invalid_factor_is_excluded_from_final_score() -> None:
    excluded = _run_precomputed_case(
        ratios_ru_overrides={"Рентабельность продаж (ROS)": 2.01}
    )
    valid = _run_precomputed_case(
        ratios_ru_overrides={"Рентабельность продаж (ROS)": 0.2}
    )
    assert excluded["score_payload"]["normalized_scores"]["ros"] is None
    assert excluded["score_payload"]["score"] != valid["score_payload"]["score"]


def test_invalid_factor_causing_score_refusal_is_currently_not_emitted() -> None:
    result = _run_precomputed_case(
        ratios_ru_overrides={
            "Рентабельность продаж (ROS)": 2.01,
            "Рентабельность собственного капитала (ROE)": 5.01,
            "EBITDA маржа": 2.5,
        }
    )
    assert isinstance(result["score_payload"]["score"], (int, float))
    assert result["score_payload"]["risk_level"] in {"low", "medium", "high", "critical"}


def test_suppressed_metric_path_yields_none_normalized_value() -> None:
    result = _run_precomputed_case(
        ratios_ru_overrides={"Финансовый рычаг": -5.0}
    )
    assert result["score_payload"]["normalized_scores"]["financial_leverage"] is None


def test_unavailable_metric_path_keeps_payload_stable() -> None:
    result = _run_document_case(metrics_overrides={"short_term_liabilities": 0.0})
    assert result["score_payload"]["normalized_scores"]["current_ratio"] is None
    assert result["score_payload"]["score"] == 59.99
    assert result["methodology"]["guardrails"] == ["low_confidence"]


def test_comparative_mismatch_path_affects_scoring_outcome() -> None:
    ratios = {
        "Коэффициент текущей ликвидности": 1.0,
        "Коэффициент быстрой ликвидности": 0.7,
        "Коэффициент абсолютной ликвидности": 0.1,
        "Рентабельность активов (ROA)": 0.05,
        "Рентабельность собственного капитала (ROE)": 0.12,
        "Рентабельность продаж (ROS)": 0.04,
        "EBITDA маржа": 0.08,
        "Коэффициент автономии": 0.35,
        "Финансовый рычаг (обязательства/капитал)": 4.0,
        "Финансовый рычаг (долг/капитал)": 1.0,
        "Покрытие процентов": 2.0,
        "Оборачиваемость активов": 1.5,
        "Оборачиваемость запасов": 10.0,
        "Оборачиваемость дебиторской задолженности": 10.0,
    }
    generic = _run_precomputed_case(
        ratios_ru_overrides=ratios,
        method_overrides={"benchmark_profile": "generic"},
    )
    retail = _run_precomputed_case(
        ratios_ru_overrides=ratios,
        method_overrides={"benchmark_profile": "retail_demo"},
    )
    assert generic["score_payload"]["score"] == 61.82
    assert retail["score_payload"]["score"] == 98.0
    assert retail["methodology"]["leverage_basis"] == "debt_only"


def test_pathological_input_path_must_not_crash_scoring() -> None:
    result = _run_document_case(
        metrics_overrides={
            "revenue": 0.0,
            "total_assets": 0.0,
            "equity": 0.0,
            "short_term_liabilities": 0.0,
        },
        text="Q1 pathological guardrail input",
    )
    assert isinstance(result["score_payload"], dict)
    assert "score" in result["score_payload"]
    assert result["methodology"]["period_basis"] == "annualized_q1"


def _run_document_case(
    metrics_overrides: dict[str, Any] | None = None,
    text: str = "annual report",
) -> dict[str, Any]:
    metrics = deepcopy(_BASE_METRICS)
    if metrics_overrides:
        metrics.update(metrics_overrides)
    result = calculate_score_with_context(
        metrics=metrics,
        filename="guardrails_case.pdf",
        text=text,
        extraction_metadata=None,
        profile="generic",
    )
    return {
        "score_payload": result["score_payload"],
        "methodology": result["score_payload"]["methodology"],
    }


def _run_precomputed_case(
    ratios_ru_overrides: dict[str, Any] | None = None,
    method_overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    ratios_ru = deepcopy(_BASE_PRECOMPUTED_RATIOS_RU)
    if ratios_ru_overrides:
        ratios_ru.update(ratios_ru_overrides)
    methodology = deepcopy(_BASE_PRECOMPUTED_METHOD)
    if method_overrides:
        methodology.update(method_overrides)
    result = calculate_score_from_precomputed_ratios(
        metrics=deepcopy(_BASE_METRICS),
        ratios_ru=ratios_ru,
        ratios_en={},
        methodology=methodology,
        extraction_metadata=None,
    )
    return {
        "score_payload": result["score_payload"],
        "methodology": result["score_payload"]["methodology"],
    }
