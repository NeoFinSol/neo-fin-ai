"""Basic smoke tests for calculate_integral_score (legacy compatibility)."""
from __future__ import annotations

import pytest

from src.analysis.scoring import calculate_integral_score, WEIGHTS


def test_calculate_integral_score_happy_path():
    """All 12 ratios at or above benchmark — score should be 100."""
    ratios = {
        "Коэффициент текущей ликвидности": 2.0,       # target 2.0 → norm 1.0
        "Коэффициент быстрой ликвидности": 1.0,       # target 1.0 → norm 1.0
        "Коэффициент абсолютной ликвидности": 0.2,    # target 0.2 → norm 1.0
        "Рентабельность активов (ROA)": 0.08,         # target 0.08 → norm 1.0
        "Рентабельность собственного капитала (ROE)": 0.15,  # target 0.15 → norm 1.0
        "Рентабельность продаж (ROS)": 0.10,          # target 0.10 → norm 1.0
        "EBITDA маржа": 0.15,                         # target 0.15 → norm 1.0
        "Коэффициент автономии": 0.5,                 # target 0.5 → norm 1.0
        "Финансовый рычаг": 0.0,                      # max_acceptable 2.0, value=0 → norm 1.0
        "Покрытие процентов": 3.0,                    # target 3.0 → norm 1.0
        "Оборачиваемость активов": 1.0,               # target 1.0 → norm 1.0
        "Оборачиваемость запасов": 8.0,               # target 8.0 → norm 1.0
        "Оборачиваемость дебиторской задолженности": 8.0,  # target 8.0 → norm 1.0
    }

    score = calculate_integral_score(ratios)

    assert score["score"] == pytest.approx(100.0)
    assert score["risk_level"] == "низкий"
    assert len(score["details"]) == 13


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
