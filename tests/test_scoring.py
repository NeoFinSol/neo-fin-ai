"""Basic smoke tests for calculate_integral_score (legacy compatibility)."""

from __future__ import annotations

import pytest

from src.analysis import pdf_extractor
from src.analysis.scoring import (
    WEIGHTS,
    annualize_metrics_for_period,
    calculate_integral_score,
    calculate_score_from_precomputed_ratios,
    calculate_score_with_context,
    resolve_scoring_methodology,
)


def test_calculate_integral_score_happy_path():
    """All available ratios at benchmark should still yield the top score."""
    ratios = {
        "Коэффициент текущей ликвидности": 2.0,  # target 2.0 → norm 1.0
        "Коэффициент быстрой ликвидности": 1.0,  # target 1.0 → norm 1.0
        "Коэффициент абсолютной ликвидности": 0.2,  # target 0.2 → norm 1.0
        "Рентабельность активов (ROA)": 0.08,  # target 0.08 → norm 1.0
        "Рентабельность собственного капитала (ROE)": 0.15,  # target 0.15 → norm 1.0
        "Рентабельность продаж (ROS)": 0.10,  # target 0.10 → norm 1.0
        "EBITDA маржа": 0.15,  # target 0.15 → norm 1.0
        "Коэффициент автономии": 0.5,  # target 0.5 → norm 1.0
        "Финансовый рычаг": None,  # unavailable, not treated as ideal
        "Покрытие процентов": 3.0,  # target 3.0 → norm 1.0
        "Оборачиваемость активов": 1.0,  # target 1.0 → norm 1.0
        "Оборачиваемость запасов": 8.0,  # target 8.0 → norm 1.0
        "Оборачиваемость дебиторской задолженности": 8.0,  # target 8.0 → norm 1.0
    }

    score = calculate_integral_score(ratios)

    assert score["score"] == pytest.approx(100.0)
    assert score["risk_level"] == "низкий"
    assert len(score["details"]) == 12


def test_calculate_integral_score_empty():
    score = calculate_integral_score({})

    assert score["score"] == 0.0
    assert score["risk_level"] == "критический"
    assert score["details"] == {}


def test_weights_sum_to_one():
    """Weights must sum to exactly 1.0."""
    total = sum(WEIGHTS.values())
    assert total == pytest.approx(1.0, abs=1e-9)


def test_retail_demo_profile_is_less_punitive_for_retail_like_structure():
    ratios = {
        "Коэффициент текущей ликвидности": 1.1,
        "Коэффициент быстрой ликвидности": 0.75,
        "Коэффициент абсолютной ликвидности": 0.12,
        "Рентабельность активов (ROA)": 0.05,
        "Рентабельность собственного капитала (ROE)": 0.12,
        "Рентабельность продаж (ROS)": 0.04,
        "EBITDA маржа": 0.08,
        "Коэффициент автономии": 0.38,
        "Финансовый рычаг": 2.1,
        "Покрытие процентов": 2.1,
        "Оборачиваемость активов": 1.7,
        "Оборачиваемость запасов": 11.0,
        "Оборачиваемость дебиторской задолженности": 10.0,
    }

    generic = calculate_integral_score(ratios, profile="generic")
    retail_demo = calculate_integral_score(ratios, profile="retail_demo")

    assert retail_demo["score"] > generic["score"]
    assert retail_demo["profile"] == "retail_demo"


def test_unknown_scoring_profile_falls_back_to_generic():
    ratios = {"Коэффициент текущей ликвидности": 2.0}

    default_generic = calculate_integral_score(ratios, profile="generic")
    unknown_profile = calculate_integral_score(ratios, profile="unknown-profile")

    assert unknown_profile["score"] == default_generic["score"]
    assert unknown_profile["profile"] == "generic"


def test_resolve_scoring_methodology_detects_retail_keyword_and_h1_period():
    metrics = {
        "revenue": 1_673_223_617_000.0,
        "net_profit": 154_479_000.0,
        "total_assets": 1_670_048_135_000.0,
        "liabilities": 1_486_023_626_000.0,
        "equity": 175_381_814_000.0,
        "current_assets": 533_367_626_000.0,
        "short_term_liabilities": 670_066_479_000.0,
        "inventory": 252_793_359_000.0,
        "accounts_receivable": 20_036_564_000.0,
    }
    ratios_en = {
        "asset_turnover": 1.0,
        "receivables_turnover": 83.41,
    }

    methodology = resolve_scoring_methodology(
        metrics,
        ratios_en=ratios_en,
        filename="Консолидированная финансовая отчетность ПАО «Магнит» по МСФО за 1 полугодие 2025 год.pdf",
        text="ПАО Магнит. Консолидированная финансовая отчетность за 1 полугодие 2025 год.",
    )

    assert methodology["benchmark_profile"] == "retail_demo"
    assert methodology["period_basis"] == "annualized_h1"
    assert methodology["detection_mode"] == "auto"
    assert "retail_keyword" in methodology["reasons"]
    assert "period_marker:h1" in methodology["reasons"]


def test_resolve_scoring_methodology_detects_retail_by_structure():
    methodology = resolve_scoring_methodology(
        {
            "inventory": 120_000_000.0,
            "revenue": 900_000_000.0,
            "accounts_receivable": 30_000_000.0,
        },
        ratios_en={
            "asset_turnover": 1.6,
            "receivables_turnover": 30.0,
        },
        filename="issuer-report.pdf",
        text="Consolidated financial statements",
    )

    assert methodology["benchmark_profile"] == "retail_demo"
    assert "retail_structure" in methodology["reasons"]


def test_resolve_scoring_methodology_keeps_reported_when_revenue_missing_for_interim():
    methodology = resolve_scoring_methodology(
        {
            "revenue": None,
            "inventory": 2_142_153_000.0,
            "net_profit": 1_348_503_000.0,
            "total_assets": 435_659_511_000.0,
        },
        ratios_en={"asset_turnover": None, "receivables_turnover": None},
        filename="Бухгалтерская отчетность ПАО «Магнит» за 1 квартал 2025 года.pdf",
        text="Отчетность за 1 квартал 2025 года",
    )

    assert methodology["benchmark_profile"] == "retail_demo"
    assert methodology["period_basis"] == "reported"


def test_annualize_metrics_for_period_updates_only_pnl_inputs():
    metrics = {
        "revenue": 100.0,
        "net_profit": 10.0,
        "ebitda": 14.0,
        "ebit": 12.0,
        "interest_expense": 2.0,
        "cost_of_goods_sold": 70.0,
        "total_assets": 500.0,
        "liabilities": 300.0,
        "equity": 200.0,
        "current_assets": 150.0,
        "short_term_liabilities": 90.0,
        "cash_and_equivalents": 40.0,
        "inventory": 30.0,
        "accounts_receivable": 25.0,
        "average_inventory": 33.0,
    }

    annualized = annualize_metrics_for_period(metrics, period_basis="annualized_h1")

    assert annualized["revenue"] == 200.0
    assert annualized["net_profit"] == 20.0
    assert annualized["ebitda"] == 28.0
    assert annualized["ebit"] == 24.0
    assert annualized["interest_expense"] == 4.0
    assert annualized["cost_of_goods_sold"] == 140.0
    assert annualized["total_assets"] == 500.0
    assert annualized["liabilities"] == 300.0
    assert annualized["current_assets"] == 150.0
    assert annualized["accounts_receivable"] == 25.0


def test_calculate_score_with_context_includes_methodology_and_guardrails():
    metrics = {
        "revenue": None,
        "net_profit": 1_348_503_000.0,
        "total_assets": 435_659_511_000.0,
        "equity": 209_475_516_000.0,
        "liabilities": 226_183_995_000.0,
        "current_assets": 174_989_150_000.0,
        "short_term_liabilities": 192_460_146_000.0,
        "inventory": 2_142_153_000.0,
        "accounts_receivable": 26_998_240_000.0,
        "cash_and_equivalents": 1_448_897_000.0,
    }

    result = calculate_score_with_context(
        metrics,
        filename="Бухгалтерская отчетность ПАО «Магнит» за 1 квартал 2025 года.pdf",
        text="ПАО Магнит. Отчетность за 1 квартал 2025 года.",
    )

    methodology = result["score_payload"]["methodology"]
    assert methodology["benchmark_profile"] == "retail_demo"
    assert methodology["period_basis"] == "reported"
    assert "missing_core:revenue" in methodology["guardrails"]


def test_calculate_score_with_context_uses_canonical_2400_for_ros_characterization():
    tables = [
        {
            "rows": [
                ["2300", "9 000", ""],
                ["2400", "1 000", ""],
                ["2110", "100 000", ""],
            ],
            "flavor": "stream",
        }
    ]
    metadata = pdf_extractor.parse_financial_statements_with_metadata(tables, "")
    metrics = {key: entry.value for key, entry in metadata.items()}

    result = calculate_score_with_context(
        metrics,
        filename="issuer-report.pdf",
        text="Annual report",
    )

    assert metrics["net_profit"] == 1000.0
    assert result["ratios_en"]["ros"] == pytest.approx(0.01)
    assert result["score_payload"]["normalized_scores"]["ros"] == pytest.approx(0.1)


def test_calculate_score_with_context_uses_debt_only_leverage_for_retail():
    metrics = {
        "revenue": 1_200_000_000.0,
        "net_profit": 48_000_000.0,
        "total_assets": 900_000_000.0,
        "equity": 180_000_000.0,
        "liabilities": 720_000_000.0,
        "current_assets": 310_000_000.0,
        "short_term_liabilities": 250_000_000.0,
        "inventory": 140_000_000.0,
        "accounts_receivable": 12_000_000.0,
        "cash_and_equivalents": 35_000_000.0,
        "short_term_borrowings": 70_000_000.0,
        "long_term_borrowings": 110_000_000.0,
        "ebit": 110_000_000.0,
        "interest_expense": -22_000_000.0,
    }

    result = calculate_score_with_context(
        metrics,
        filename="Магнит retail report.pdf",
        text="ПАО Магнит retail report",
    )

    methodology = result["score_payload"]["methodology"]
    ratios_en = result["ratios_en"]

    assert ratios_en["financial_leverage_total"] is None
    assert ratios_en["financial_leverage_debt_only"] is None
    assert ratios_en["financial_leverage"] is None
    assert methodology["leverage_basis"] == "total_liabilities"
    assert methodology["ifrs16_adjusted"] is False
    assert "interest_coverage_sign_corrected" in methodology["adjustments"]
    assert "leverage_debt_only" not in methodology["adjustments"]
    assert methodology["peer_context"]


def test_calculate_score_with_context_keeps_total_liability_leverage_for_non_retail():
    metrics = {
        "revenue": 200_000_000.0,
        "net_profit": 20_000_000.0,
        "total_assets": 150_000_000.0,
        "equity": 50_000_000.0,
        "liabilities": 100_000_000.0,
        "current_assets": 60_000_000.0,
        "short_term_liabilities": 30_000_000.0,
        "short_term_borrowings": 10_000_000.0,
        "long_term_borrowings": 15_000_000.0,
        "ebit": 30_000_000.0,
        "interest_expense": 5_000_000.0,
    }

    result = calculate_score_with_context(
        metrics,
        filename="Industrial issuer annual report.pdf",
        text="Industrial issuer annual report",
    )

    methodology = result["score_payload"]["methodology"]
    ratios_en = result["ratios_en"]

    assert methodology["benchmark_profile"] == "generic"
    assert methodology["leverage_basis"] == "total_liabilities"
    assert methodology["ifrs16_adjusted"] is False
    assert ratios_en["financial_leverage_total"] is None
    assert ratios_en["financial_leverage_debt_only"] is None
    assert ratios_en["financial_leverage"] is None


def test_calculate_integral_score_skips_suppressed_metrics() -> None:
    score = calculate_integral_score(
        {
            "Коэффициент текущей ликвидности": 2.0,
            "EBITDA маржа": None,
            "Финансовый рычаг": None,
        }
    )

    assert score["score"] >= 0
    assert "EBITDA маржа" not in score["details"]


def test_calculate_score_with_context_captures_issuer_override_adjustments():
    metrics = {
        "revenue": 1_673_223_617_000.0,
        "net_profit": 154_479_000.0,
        "ebitda": 1_846_067_000.0,
        "ebit": 73_037_223_000.0,
        "interest_expense": -79_896_062_000.0,
        "total_assets": 1_670_048_135_000.0,
        "equity": 175_381_814_000.0,
        "liabilities": 1_486_023_626_000.0,
        "current_assets": 533_367_626_000.0,
        "short_term_liabilities": 670_066_479_000.0,
        "inventory": 302_102_443_000.0,
        "accounts_receivable": 20_060_895_000.0,
        "cash_and_equivalents": 71_205_955_000.0,
        "short_term_borrowings": 281_924_752_000.0,
        "long_term_borrowings": 220_922_477_000.0,
        "short_term_lease_liabilities": 211_182_682_000.0,
        "long_term_lease_liabilities": 431_637_396_000.0,
    }
    extraction_metadata = {
        "ebitda": {"confidence": 1.0, "source": "issuer_fallback"},
        "interest_expense": {"confidence": 1.0, "source": "issuer_fallback"},
        "net_profit": {"confidence": 1.0, "source": "issuer_fallback"},
    }

    result = calculate_score_with_context(
        metrics,
        filename="Консолидированная финансовая отчетность ПАО «Магнит» по МСФО за 1 полугодие 2025 год.pdf",
        text="ПАО Магнит. Отчетность за 1 полугодие 2025 года.",
        extraction_metadata=extraction_metadata,
    )

    methodology = result["score_payload"]["methodology"]

    assert methodology["benchmark_profile"] == "retail_demo"
    assert methodology["period_basis"] == "annualized_h1"
    assert methodology["ifrs16_adjusted"] is True
    assert "issuer_override:ebitda" in methodology["adjustments"]
    assert "issuer_override:interest_expense" in methodology["adjustments"]
    assert "issuer_override:net_profit" in methodology["adjustments"]


def test_calculate_score_from_precomputed_ratios_matches_existing_score_context_shape():
    methodology = {
        "benchmark_profile": "generic",
        "period_basis": "reported",
        "detection_mode": "auto",
        "reasons": [],
        "guardrails": [],
        "leverage_basis": "total_liabilities",
        "ifrs16_adjusted": False,
        "adjustments": [],
        "peer_context": [],
    }
    ratios_ru = {
        "Коэффициент текущей ликвидности": 2.0,
        "Рентабельность активов (ROA)": 0.1,
        "Рентабельность собственного капитала (ROE)": 0.2,
        "Оборачиваемость активов": 1.0,
    }
    ratios_en = {
        "current_ratio": 2.0,
        "roa": 0.1,
        "roe": 0.2,
        "asset_turnover": 1.0,
    }

    result = calculate_score_from_precomputed_ratios(
        metrics={
            "revenue": 120.0,
            "net_profit": 12.0,
            "total_assets": 140.0,
            "equity": 70.0,
        },
        ratios_ru=ratios_ru,
        ratios_en=ratios_en,
        methodology=methodology,
        extraction_metadata=None,
    )

    assert set(result.keys()) == {
        "ratios_ru",
        "ratios_en",
        "raw_score",
        "score_payload",
        "methodology",
    }
    for key, value in ratios_en.items():
        assert result["ratios_en"][key] == value
    assert result["score_payload"]["methodology"]["benchmark_profile"] == "generic"
