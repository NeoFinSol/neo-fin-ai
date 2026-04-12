"""Tests for financial ratios calculations via Math Layer bridge (extended coverage)."""

import math

import pytest

from src.analysis.ratios import calculate_ratios


class TestCalculateRatios:
    """Tests for calculate_ratios function with extended fields."""

    def test_safe_metrics_with_full_data(self):
        financial_data = {
            "revenue": 1000000,
            "net_profit": 150000,
            "total_assets": 2000000,
            "equity": 800000,
            "current_assets": 500000,
            "short_term_liabilities": 300000,
            "cash_and_equivalents": 50000,
        }

        result = calculate_ratios(financial_data)

        assert result["Коэффициент текущей ликвидности"] == pytest.approx(
            500000 / 300000
        )
        assert result["Коэффициент абсолютной ликвидности"] == pytest.approx(
            50000 / 300000
        )
        assert result["Рентабельность продаж (ROS)"] == pytest.approx(150000 / 1000000)
        assert result["Коэффициент автономии"] == pytest.approx(800000 / 2000000)

    def test_unsafe_metrics_return_none(self):
        financial_data = {
            "revenue": 1000000,
            "net_profit": 150000,
            "total_assets": 2000000,
            "equity": 800000,
            "current_assets": 500000,
            "short_term_liabilities": 300000,
            "ebitda": 250000,
            "ebit": 200000,
            "interest_expense": 20000,
        }

        result = calculate_ratios(financial_data)

        assert result["EBITDA маржа"] is None
        assert result["Покрытие процентов"] is None
        assert result["Рентабельность активов (ROA)"] is None
        assert result["Рентабельность собственного капитала (ROE)"] is None
        assert result["Финансовый рычаг"] is None

    def test_backwards_compatibility(self):
        financial_data = {
            "revenue": 1000000,
            "net_profit": 150000,
            "total_assets": 2000000,
            "equity": 800000,
            "current_assets": 500000,
            "short_term_liabilities": 300000,
        }

        result = calculate_ratios(financial_data)

        assert result["Коэффициент текущей ликвидности"] == pytest.approx(
            500000 / 300000
        )
        assert result["Коэффициент автономии"] == pytest.approx(800000 / 2000000)

    def test_zero_denominator_returns_none(self):
        financial_data = {
            "revenue": 1000000,
            "net_profit": 150000,
            "total_assets": 0,
            "equity": 0,
            "current_assets": 0,
            "short_term_liabilities": 0,
        }

        result = calculate_ratios(financial_data)

        assert result["Коэффициент текущей ликвидности"] is None
        assert result["Коэффициент автономии"] is None

    def test_string_values_converted(self):
        financial_data = {
            "revenue": "1000000",
            "net_profit": "150000",
            "total_assets": "2000000",
            "equity": "800000",
            "current_assets": "500000",
            "short_term_liabilities": "300000",
        }

        result = calculate_ratios(financial_data)

        assert result["Коэффициент текущей ликвидности"] is not None
        assert result["Коэффициент автономии"] is not None

    def test_empty_dict(self):
        result = calculate_ratios({})

        for value in result.values():
            assert value is None

    def test_partial_data(self):
        financial_data = {
            "revenue": 1000000,
            "net_profit": 150000,
            "total_assets": 2000000,
            "equity": 800000,
        }

        result = calculate_ratios(financial_data)

        assert result["Коэффициент автономии"] is not None
        assert result["Коэффициент текущей ликвидности"] is None
