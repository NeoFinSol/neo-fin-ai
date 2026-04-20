from __future__ import annotations

from copy import deepcopy
from typing import Any

from src.analysis.scoring import calculate_score_with_context

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


def test_fy_entity_uses_reported_period_basis() -> None:
    result = _run_case("Годовой отчёт за 2025 год")
    assert result["methodology"]["period_basis"] == "reported"
    assert "period_marker:q1" not in result["methodology"]["reasons"]
    assert "period_marker:h1" not in result["methodology"]["reasons"]


def test_h1_entity_uses_h1_annualization_basis() -> None:
    result = _run_case("Консолидированная отчётность за 1 полугодие 2026")
    assert result["methodology"]["period_basis"] == "annualized_h1"
    assert "period_marker:h1" in result["methodology"]["reasons"]


def test_q1_entity_uses_q1_annualization_basis() -> None:
    result = _run_case("Промежуточная отчётность за 1 квартал 2026")
    assert result["methodology"]["period_basis"] == "annualized_q1"
    assert "period_marker:q1" in result["methodology"]["reasons"]


def test_q3_9m_like_entity_is_currently_non_annualized_observed_behavior() -> None:
    result = _run_case("Отчёт за 9M (Q3) период 2026")
    assert result["methodology"]["period_basis"] == "reported"
    assert "period_marker:q1" not in result["methodology"]["reasons"]
    assert "period_marker:h1" not in result["methodology"]["reasons"]


def test_annualizable_positive_case_requires_q_marker_and_revenue_presence() -> None:
    result = _run_case("Операционный отчёт Q1 2026")
    assert result["methodology"]["period_basis"] == "annualized_q1"
    assert "period_marker:q1" in result["methodology"]["reasons"]
    assert isinstance(result["score_payload"]["score"], (int, float))
    assert isinstance(result["score_payload"]["normalized_scores"], dict)


def test_non_annualizable_case_without_markers_stays_reported() -> None:
    result = _run_case("Консолидированная финансовая отчётность")
    assert result["methodology"]["period_basis"] == "reported"
    assert result["score_payload"]["methodology"]["period_basis"] == "reported"


def test_ambiguous_period_case_prefers_q1_marker_observed_ordering() -> None:
    result = _run_case("Отчётность Q1 и H1 одновременно")
    assert result["methodology"]["period_basis"] == "annualized_q1"
    assert "period_marker:q1" in result["methodology"]["reasons"]
    assert "period_marker:h1" not in result["methodology"]["reasons"]


def test_material_score_change_path_is_currently_uncovered_but_frozen() -> None:
    annualized = _run_case("Q1 financial statements")
    reported = _run_case("FY financial statements")
    assert annualized["methodology"]["period_basis"] == "annualized_q1"
    assert reported["methodology"]["period_basis"] == "reported"
    assert annualized["score_payload"]["score"] == reported["score_payload"]["score"]


def test_annualization_must_not_happen_when_revenue_is_missing() -> None:
    result = _run_case("Q1 management report", metrics_overrides={"revenue": None})
    assert result["methodology"]["period_basis"] == "reported"
    assert result["score_payload"]["methodology"]["period_basis"] == "reported"


def test_annualization_affects_only_selected_scoring_factors_observed_behavior() -> None:
    annualized = _run_case("Q1 issuer package")
    reported = _run_case("FY issuer package")
    assert annualized["methodology"]["period_basis"] == "annualized_q1"
    assert reported["methodology"]["period_basis"] == "reported"

    annualized_scores = annualized["score_payload"]["normalized_scores"]
    reported_scores = reported["score_payload"]["normalized_scores"]
    assert set(annualized_scores) == set(reported_scores)

    unaffected_factor_keys = ("current_ratio", "equity_ratio", "ros")
    for key in unaffected_factor_keys:
        assert annualized_scores[key] == reported_scores[key]

    assert annualized["score_payload"]["factors"] == reported["score_payload"]["factors"]


def _run_case(text: str, metrics_overrides: dict[str, Any] | None = None) -> dict[str, Any]:
    metrics = deepcopy(_BASE_METRICS)
    if metrics_overrides:
        metrics.update(metrics_overrides)
    result = calculate_score_with_context(
        metrics=metrics,
        filename="annualization_case.pdf",
        text=text,
        extraction_metadata=None,
        profile="generic",
    )
    return {
        "methodology": result["methodology"],
        "score_payload": result["score_payload"],
        "ratios_en": result["ratios_en"],
        "raw_score": result["raw_score"],
    }
