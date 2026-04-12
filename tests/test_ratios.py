"""Basic smoke tests for calculate_ratios (legacy compatibility)."""
from __future__ import annotations

import pytest

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

    assert ratios["Коэффициент текущей ликвидности"] == pytest.approx(2.0)
    assert ratios["Рентабельность продаж (ROS)"] == pytest.approx(0.05)
    assert ratios["Коэффициент автономии"] == pytest.approx(0.5)
    assert ratios["Рентабельность активов (ROA)"] is None
    assert ratios["Рентабельность собственного капитала (ROE)"] is None
    assert ratios["Финансовый рычаг"] is None


def test_calculate_ratios_missing_data():
    data = {
        "current_assets": 100,
        "short_term_liabilities": 0,
        "total_assets": None,
    }

    ratios = calculate_ratios(data)

    assert ratios["Коэффициент текущей ликвидности"] is None  # denominator = 0
    assert ratios["Коэффициент автономии"] is None
    assert ratios["Рентабельность активов (ROA)"] is None
    assert ratios["Рентабельность собственного капитала (ROE)"] is None
    assert ratios["Финансовый рычаг"] is None


def test_calculate_ratios_suppresses_unsafe_ebitda_metrics():
    data = {
        "revenue": 1_000_000.0,
        "net_profit": 120_000.0,
        "total_assets": 2_000_000.0,
        "equity": 800_000.0,
        "liabilities": 1_200_000.0,
        "current_assets": 700_000.0,
        "short_term_liabilities": 400_000.0,
        "ebit": 210_000.0,
        "interest_expense": -70_000.0,
    }

    ratios = calculate_ratios(data)

    assert ratios["EBITDA маржа"] is None
    assert ratios["Покрытие процентов"] is None


def test_calculate_ratios_keeps_debt_metrics_unavailable_without_safe_math_support():
    data = {
        "revenue": 1_000_000.0,
        "net_profit": 120_000.0,
        "total_assets": 2_000_000.0,
        "equity": 500_000.0,
        "liabilities": 1_500_000.0,
        "current_assets": 700_000.0,
        "short_term_liabilities": 400_000.0,
        "short_term_borrowings": 150_000.0,
        "long_term_borrowings": 350_000.0,
    }

    ratios = calculate_ratios(data)

    assert ratios["Финансовый рычаг"] is None
    assert ratios["Финансовый рычаг (обязательства/капитал)"] is None
    assert ratios["Финансовый рычаг (долг/капитал)"] is None
