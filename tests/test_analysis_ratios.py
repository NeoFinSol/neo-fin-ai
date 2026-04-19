"""Tests for financial ratios calculations via Math Layer bridge."""

import math

import pytest

from src.analysis.ratios import calculate_ratios


class TestCalculateRatios:
    """Tests for calculate_ratios function."""

    def test_all_ratios_calculated(self):
        financial_data = {
            "revenue": 1000000,
            "net_profit": 150000,
            "total_assets": 2000000,
            "equity": 800000,
            "liabilities": 1200000,
            "current_assets": 500000,
            "short_term_liabilities": 300000,
            "cash_and_equivalents": 50000,
        }

        result = calculate_ratios(financial_data)

        assert "Коэффициент текущей ликвидности" in result
        assert "Коэффициент автономии" in result
        # Wave 1a rounding policy: RATIO_STANDARD rounds to 4 decimal places
        assert result["Коэффициент текущей ликвидности"] == pytest.approx(
            500000 / 300000, abs=0.0001
        )
        assert result["Коэффициент автономии"] == pytest.approx(800000 / 2000000)

    def test_missing_fields_returns_none(self):
        result = calculate_ratios({"revenue": 1000000})

        assert result["Коэффициент автономии"] is None

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

    def test_invalid_string_values_handled(self):
        financial_data = {
            "revenue": "invalid",
            "net_profit": None,
            "total_assets": "N/A",
            "equity": "",
            "current_assets": float("nan"),
            "short_term_liabilities": 300000,
        }

        result = calculate_ratios(financial_data)

        assert result["Коэффициент текущей ликвидности"] is None

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

    def test_negative_values_handled_by_math_layer(self):
        financial_data = {
            "revenue": -1000000,
            "net_profit": -150000,
            "total_assets": 2000000,
            "equity": -800000,
            "current_assets": 500000,
            "short_term_liabilities": 300000,
        }

        result = calculate_ratios(financial_data)

        assert result["Коэффициент текущей ликвидности"] is not None
        assert result["Коэффициент автономии"] is None
