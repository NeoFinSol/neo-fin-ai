"""Tests for financial ratios calculations (legacy + updated)."""
import math
from unittest.mock import patch

import pytest

from src.analysis.ratios import _safe_div, calculate_ratios


class TestCalculateRatios:
    """Tests for calculate_ratios function."""

    def test_all_ratios_calculated(self):
        """Test all 12 ratios calculated with valid data."""
        financial_data = {
            "revenue": 1000000,
            "net_profit": 150000,
            "total_assets": 2000000,
            "equity": 800000,
            "liabilities": 1200000,
            "current_assets": 500000,
            "short_term_liabilities": 300000,
            "inventory": 100000,
            "cash_and_equivalents": 50000,
            "ebit": 200000,
            "interest_expense": 20000,
            "cost_of_goods_sold": 600000,
            "average_inventory": 120000,
            "accounts_receivable": 150000,
        }

        result = calculate_ratios(financial_data)

        assert "Коэффициент текущей ликвидности" in result
        assert "Коэффициент автономии" in result
        assert "Рентабельность активов (ROA)" in result
        assert "Рентабельность собственного капитала (ROE)" in result
        assert "Финансовый рычаг" in result  # was "Долговая нагрузка" — now correct key

        # Verify calculations
        assert result["Коэффициент текущей ликвидности"] == pytest.approx(500000 / 300000)
        assert result["Коэффициент автономии"] == pytest.approx(800000 / 2000000)
        assert result["Рентабельность активов (ROA)"] == pytest.approx(150000 / 2000000)
        assert result["Рентабельность собственного капитала (ROE)"] == pytest.approx(150000 / 800000)
        # Финансовый рычаг = liabilities / equity
        assert result["Финансовый рычаг"] == pytest.approx(1200000 / 800000)

    def test_missing_fields_returns_none(self):
        """Test missing fields result in None ratios."""
        financial_data = {
            "revenue": 1000000,
            # Missing other required fields
        }

        result = calculate_ratios(financial_data)

        assert result["Коэффициент автономии"] is None
        assert result["Рентабельность активов (ROA)"] is None

    def test_zero_denominator_returns_none(self):
        """Test division by zero returns None."""
        financial_data = {
            "revenue": 1000000,
            "net_profit": 150000,
            "total_assets": 0,
            "equity": 0,
            "liabilities": 1200000,
            "current_assets": 0,
            "short_term_liabilities": 0,
        }

        result = calculate_ratios(financial_data)

        assert result["Коэффициент текущей ликвидности"] is None
        assert result["Коэффициент автономии"] is None
        assert result["Рентабельность активов (ROA)"] is None
        assert result["Рентабельность собственного капитала (ROE)"] is None

    def test_string_values_converted(self):
        """Test string values are converted to numbers."""
        financial_data = {
            "revenue": "1000000",
            "net_profit": "150000",
            "total_assets": "2000000",
            "equity": "800000",
            "liabilities": "1200000",
            "current_assets": "500000",
            "short_term_liabilities": "300000",
        }

        result = calculate_ratios(financial_data)

        assert result["Коэффициент текущей ликвидности"] is not None
        assert result["Коэффициент автономии"] is not None

    def test_invalid_string_values_handled(self):
        """Test invalid string values handled gracefully."""
        financial_data = {
            "revenue": "invalid",
            "net_profit": None,
            "total_assets": "N/A",
            "equity": "",
            "liabilities": "unknown",
            "current_assets": float("nan"),
            "short_term_liabilities": 300000,
        }

        result = calculate_ratios(financial_data)

        current_liquidity = result["Коэффициент текущей ликвидности"]
        assert current_liquidity is None or (
            isinstance(current_liquidity, float) and math.isnan(current_liquidity)
        )

    def test_empty_dict(self):
        """Test empty dictionary input."""
        result = calculate_ratios({})

        for key, value in result.items():
            assert value is None

    def test_partial_data(self):
        """Test calculation with partial data."""
        financial_data = {
            "revenue": 1000000,
            "net_profit": 150000,
            "total_assets": 2000000,
            "equity": 800000,
            # Missing liabilities, current_assets, short_term_liabilities
        }

        result = calculate_ratios(financial_data)

        assert result["Коэффициент автономии"] is not None
        assert result["Рентабельность активов (ROA)"] is not None
        assert result["Рентабельность собственного капитала (ROE)"] is not None
        assert result["Коэффициент текущей ликвидности"] is None
        assert result["Финансовый рычаг"] is None  # liabilities missing

    def test_negative_values(self):
        """Test negative values are handled."""
        financial_data = {
            "revenue": -1000000,
            "net_profit": -150000,
            "total_assets": 2000000,
            "equity": -800000,
            "liabilities": 1200000,
            "current_assets": 500000,
            "short_term_liabilities": 300000,
        }

        result = calculate_ratios(financial_data)

        assert result["Рентабельность активов (ROA)"] < 0
        assert result["Рентабельность собственного капитала (ROE)"] > 0  # negative/negative

    def test_mixed_types(self):
        """Test mixed numeric types — only ratios with available data should be non-None."""
        financial_data = {
            "revenue": 1000000,
            "net_profit": 150000.5,
            "total_assets": "2000000",
            "equity": 800000,
            "liabilities": 1200000.0,
            "current_assets": "500000",
            "short_term_liabilities": 300000,
            # inventory NOT provided → quick_ratio and inventory_turnover will be None
        }

        result = calculate_ratios(financial_data)

        # Ratios that CAN be calculated with provided data
        calculable = [
            "Коэффициент текущей ликвидности",
            "Рентабельность активов (ROA)",
            "Рентабельность собственного капитала (ROE)",
            "Рентабельность продаж (ROS)",
            "Коэффициент автономии",
            "Финансовый рычаг",
            "Оборачиваемость активов",
        ]
        for ratio_name in calculable:
            assert result[ratio_name] is not None, f"{ratio_name} should not be None"

        # Ratios that require missing fields
        assert result["Коэффициент быстрой ликвидности"] is None  # needs inventory
        assert result["Коэффициент абсолютной ликвидности"] is None  # needs cash

    def test_safe_div_exception_handling(self):
        """Test that exceptions in division are caught and return None."""
        with patch("src.analysis.ratios.logger") as mock_logger:

            class ProblematicNumber:
                def __truediv__(self, other):
                    raise RuntimeError("Unexpected error")

            result = _safe_div(ProblematicNumber(), 5)
            assert result is None
            mock_logger.warning.assert_called_once()
