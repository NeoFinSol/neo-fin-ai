from __future__ import annotations

from copy import deepcopy
from typing import Any

from src.analysis.scoring import (
    BENCHMARKS_BY_PROFILE,
    WEIGHTS,
    calculate_score_with_context,
)
from tests.scoring_freeze.fixtures.case_registry import BLOCKER_CASES, CANONICAL_FREEZE_CASES
from tests.scoring_freeze.fixtures.classification_registry import BLOCKER_CASES as BLOCKER_CASE_IDS

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

_EXPECTED_NORMALIZED_KEYS = {
    "current_ratio",
    "quick_ratio",
    "absolute_liquidity_ratio",
    "roa",
    "roe",
    "ros",
    "ebitda_margin",
    "equity_ratio",
    "financial_leverage",
    "financial_leverage_total",
    "financial_leverage_debt_only",
    "interest_coverage",
    "asset_turnover",
    "inventory_turnover",
    "receivables_turnover",
}


def test_blocker_leakage_cases_are_not_in_canonical_baseline() -> None:
    canonical_case_ids = {case.case_id for case in CANONICAL_FREEZE_CASES}
    assert canonical_case_ids.isdisjoint(BLOCKER_CASE_IDS)
    assert {case.case_id for case in BLOCKER_CASES} == set(BLOCKER_CASE_IDS)


def test_label_coupling_regression_machine_fields_remain_primary_source() -> None:
    result = _run_case(text="Q1 plain text without labels section")
    assert result["methodology"]["period_basis"] == "annualized_q1"
    assert "period_marker:q1" in result["methodology"]["reasons"]
    assert isinstance(result["score_payload"]["factors"][0]["description"], str)


def test_omission_nullability_drift_normalized_scores_shape_is_stable() -> None:
    result = _run_case(metrics_overrides={"short_term_liabilities": 0.0})
    normalized_scores = result["score_payload"]["normalized_scores"]
    assert set(normalized_scores) == _EXPECTED_NORMALIZED_KEYS
    assert normalized_scores["current_ratio"] is None
    assert isinstance(normalized_scores["equity_ratio"], float)


def test_data_binding_rewiring_profile_tables_are_consistent() -> None:
    generic = _run_case(profile="generic")
    retail = _run_case(profile="retail_demo")
    assert generic["methodology"]["benchmark_profile"] == "generic"
    assert retail["methodology"]["benchmark_profile"] == "retail_demo"
    assert retail["methodology"]["peer_context"]
    assert retail["score_payload"]["score"] == 59.99


def test_numeric_tolerance_misuse_caps_are_exact_values() -> None:
    missing_core = _run_case(metrics_overrides={"revenue": None})
    missing_supporting = _run_case(metrics_overrides={"net_profit": None})
    low_confidence = _run_case()
    assert missing_core["score_payload"]["score"] == 39.99
    assert missing_supporting["score_payload"]["score"] == 54.99
    assert low_confidence["score_payload"]["score"] == 59.99


def test_hidden_guardrail_drift_priority_order_is_stable() -> None:
    result = _run_case(metrics_overrides={"revenue": None, "net_profit": None})
    assert result["score_payload"]["score"] == 39.99
    assert result["methodology"]["guardrails"] == ["missing_core:revenue"]


def test_annualization_flag_drift_detected_by_period_basis() -> None:
    annualized = _run_case(text="Q1 interim statements")
    reported = _run_case(text="FY annual statements")
    assert annualized["methodology"]["period_basis"] == "annualized_q1"
    assert reported["methodology"]["period_basis"] == "reported"


def test_factor_status_drift_impacts_are_from_expected_domain() -> None:
    result = _run_case()
    impacts = {factor["impact"] for factor in result["score_payload"]["factors"]}
    assert impacts.issubset({"positive", "neutral", "negative"})
    assert impacts


def test_machine_reason_and_prose_are_not_conflated() -> None:
    result = _run_case(metrics_overrides={"revenue": None})
    assert result["methodology"]["guardrails"] == ["missing_core:revenue"]
    descriptions = [factor["description"] for factor in result["score_payload"]["factors"]]
    assert all(isinstance(description, str) for description in descriptions)
    assert "missing_core:revenue" not in " ".join(descriptions)


def test_guardrail_data_binding_constants_are_wired() -> None:
    assert "retail_demo" in BENCHMARKS_BY_PROFILE
    assert "Коэффициент текущей ликвидности" in WEIGHTS


def _run_case(
    metrics_overrides: dict[str, Any] | None = None,
    text: str = "annual report",
    profile: str = "generic",
) -> dict[str, Any]:
    metrics = deepcopy(_BASE_METRICS)
    if metrics_overrides:
        metrics.update(metrics_overrides)
    result = calculate_score_with_context(
        metrics=metrics,
        filename="regression_case.pdf",
        text=text,
        extraction_metadata=None,
        profile=profile,
    )
    return {
        "score_payload": result["score_payload"],
        "methodology": result["score_payload"]["methodology"],
    }
