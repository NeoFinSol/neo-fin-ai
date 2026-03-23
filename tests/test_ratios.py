from __future__ import annotations

from src.analysis.ratios import calculate_ratios


def test_calculate_ratios_basic():
    data = {
        "revenue": 600,
        "net_profit": 30,
        "total_assets": 300,
        "equity": 150,
        "liabilities": 120,
        "current_assets": 200,
        "short_term_liabilities": 100,
    }

    ratios = calculate_ratios(data)

    assert ratios["Коэффициент текущей ликвидности"] == 2.0
    assert ratios["Коэффициент автономии"] == 0.5
    assert ratios["Рентабельность активов (ROA)"] == 0.1
    assert ratios["Рентабельность собственного капитала (ROE)"] == 0.2
    assert ratios["Долговая нагрузка"] == 0.2


def test_calculate_ratios_missing_data():
    data = {
        "current_assets": 100,
        "short_term_liabilities": 0,
        "total_assets": None,
    }

    ratios = calculate_ratios(data)

    assert ratios["Коэффициент текущей ликвидности"] is None
    assert ratios["Коэффициент автономии"] is None
    assert ratios["Рентабельность активов (ROA)"] is None
    assert ratios["Рентабельность собственного капитала (ROE)"] is None
    assert ratios["Долговая нагрузка"] is None
