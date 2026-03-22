from __future__ import annotations

from src.analysis.scoring import calculate_integral_score


def test_calculate_integral_score_happy_path():
    ratios = {
        "Коэффициент текущей ликвидности": 2.0,
        "Коэффициент автономии": 0.5,
        "Рентабельность активов (ROA)": 0.1,
        "Рентабельность собственного капитала (ROE)": 0.2,
        "Долговая нагрузка": 1.0,
    }

    score = calculate_integral_score(ratios)

    assert score["score"] == 95.0
    assert score["risk_level"] == "низкий"
    assert score["details"]["Долговая нагрузка"] == 0.5


def test_calculate_integral_score_empty():
    score = calculate_integral_score({})

    assert score["score"] == 0.0
    assert score["risk_level"] == "высокий"
    assert score["details"] == {}
