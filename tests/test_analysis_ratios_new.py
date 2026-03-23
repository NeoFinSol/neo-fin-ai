"""Tests for financial ratios calculations."""
import math
from unittest.mock import patch

import pytest

from src.analysis.ratios import _safe_div, _subtract, calculate_ratios


class TestCalculateRatios:
    """Tests for calculate_ratios function."""

    def test_all_12_ratios_calculated(self):
        """Test all 12 ratios calculated with valid data."""
        financial_data = {
            # Basic fields
            "revenue": 1000000,
            "net_profit": 150000,
            "total_assets": 2000000,
            "equity": 800000,
            "liabilities": 1200000,
            "current_assets": 500000,
            "short_term_liabilities": 300000,
            # Extended fields for new ratios
            "inventory": 100000,
            "cash_and_equivalents": 50000,
            "ebitda": 250000,
            "ebit": 200000,
            "interest_expense": 20000,
            "cost_of_goods_sold": 600000,
            "accounts_receivable": 150000,
            "average_inventory": 120000,
        }
        
        result = calculate_ratios(financial_data)
        
        # Verify all 12 ratios are present
        expected_ratios = [
            "Коэффициент текущей ликвидности",
            "Коэффициент быстрой ликвидности",
            "Коэффициент абсолютной ликвидности",
            "Рентабельность активов (ROA)",
            "Рентабельность собственного капитала (ROE)",
            "Рентабельность продаж (ROS)",
            "EBITDA маржа",
            "Коэффициент автономии",
            "Финансовый рычаг",
            "Покрытие процентов",
            "Оборачиваемость активов",
            "Оборачиваемость запасов",
            "Оборачиваемость дебиторской задолженности",
        ]
        
        for ratio_name in expected_ratios:
            assert ratio_name in result, f"Missing ratio: {ratio_name}"
        
        # Verify calculations for liquidity ratios
        assert result["Коэффициент текущей ликвидности"] == pytest.approx(500000 / 300000)
        assert result["Коэффициент быстрой ликвидности"] == pytest.approx(400000 / 300000)  # (500k - 100k) / 300k
        assert result["Коэффициент абсолютной ликвидности"] == pytest.approx(50000 / 300000)
        
        # Verify calculations for profitability ratios
        assert result["Рентабельность активов (ROA)"] == pytest.approx(150000 / 2000000)
        assert result["Рентабельность собственного капитала (ROE)"] == pytest.approx(150000 / 800000)
        assert result["Рентабельность продаж (ROS)"] == pytest.approx(150000 / 1000000)
        assert result["EBITDA маржа"] == pytest.approx(250000 / 1000000)
        
        # Verify calculations for stability ratios
        assert result["Коэффициент автономии"] == pytest.approx(800000 / 2000000)
        assert result["Финансовый рычаг"] == pytest.approx(1200000 / 800000)
        assert result["Покрытие процентов"] == pytest.approx(200000 / 20000)
        
        # Verify calculations for activity ratios
        assert result["Оборачиваемость активов"] == pytest.approx(1000000 / 2000000)
        assert result["Оборачиваемость запасов"] == pytest.approx(600000 / 120000)
        assert result["Оборачиваемость дебиторской задолженности"] == pytest.approx(1000000 / 150000)

    def test_backwards_compatibility(self):
        """Test backward compatibility with original ratios."""
        financial_data = {
            "revenue": 1000000,
            "net_profit": 150000,
            "total_assets": 2000000,
            "equity": 800000,
            "liabilities": 1200000,
            "current_assets": 500000,
            "short_term_liabilities": 300000
        }
        
        result = calculate_ratios(financial_data)
        
        # Original ratios should still work
        assert result["Коэффициент текущей ликвидности"] == pytest.approx(500000 / 300000)
        assert result["Коэффициент автономии"] == pytest.approx(800000 / 2000000)
        assert result["Рентабельность активов (ROA)"] == pytest.approx(150000 / 2000000)
        assert result["Рентабельность собственного капитала (ROE)"] == pytest.approx(150000 / 800000)
        
        # New ratios should have None values if extended fields are missing
        assert result["Коэффициент быстрой ликвидности"] is None
        assert result["Коэффициент абсолютной ликвидности"] is None

    def test_missing_fields_returns_none(self):
        """Test missing fields result in None ratios."""
        financial_data = {
            "revenue": 1000000,
            # Missing other required fields
        }
        
        result = calculate_ratios(financial_data)
        
        # Ratios requiring missing fields should be None
        assert result["Коэффициент автономии"] is None
        assert result["Рентабельность активов (ROA)"] is None
        assert result["Рентабельность собственного капитала (ROE)"] is None

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
            "ebit": 200000,
            "interest_expense": 0,
        }
        
        result = calculate_ratios(financial_data)
        
        # All ratios with zero denominators should be None
        assert result["Коэффициент текущей ликвидности"] is None
        assert result["Коэффициент автономии"] is None
        assert result["Рентабельность активов (ROA)"] is None
        assert result["Рентабельность собственного капитала (ROE)"] is None
        assert result["Покрытие процентов"] is None

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
            "inventory": "100000",
            "ebit": "200000",
            "interest_expense": "20000",
        }
        
        result = calculate_ratios(financial_data)
        
        # Should successfully calculate despite string inputs
        assert result["Коэффициент текущей ликвидности"] is not None
        assert result["Коэффициент автономии"] is not None
        assert result["Коэффициент быстрой ликвидности"] is not None

    def test_invalid_string_values_handled(self):
        """Test invalid string values handled gracefully."""
        financial_data = {
            "revenue": "invalid",
            "net_profit": None,
            "total_assets": "N/A",
            "equity": "",
            "liabilities": "unknown",
            "current_assets": "500000",
            "short_term_liabilities": 300000
        }
        
        result = calculate_ratios(financial_data)
        
        # Should handle invalid values gracefully
        assert result["Коэффициент текущей ликвидности"] == pytest.approx(500000 / 300000)
        assert result["Коэффициент автономии"] is None

    def test_empty_dict(self):
        """Test empty dictionary input."""
        result = calculate_ratios({})
        
        # All ratios should be None
        for key, value in result.items():
            assert value is None

    def test_partial_data(self):
        """Test calculation with partial data."""
        financial_data = {
            "revenue": 1000000,
            "net_profit": 150000,
            "total_assets": 2000000,
            "equity": 800000,
        }
        
        result = calculate_ratios(financial_data)
        
        # Some ratios can be calculated
        assert result["Коэффициент автономии"] is not None
        assert result["Рентабельность активов (ROA)"] is not None
        assert result["Рентабельность собственного капитала (ROE)"] is not None
        
        # Others require missing data
        assert result["Коэффициент текущей ликвидности"] is None

    def test_negative_values(self):
        """Test negative values are handled."""
        financial_data = {
            "revenue": -1000000,
            "net_profit": -150000,
            "total_assets": 2000000,
            "equity": -800000,
            "liabilities": 1200000,
            "current_assets": 500000,
            "short_term_liabilities": 300000
        }
        
        result = calculate_ratios(financial_data)
        
        # Should calculate with negative values
        assert result["Рентабельность активов (ROA)"] < 0
        assert result["Рентабельность собственного капитала (ROE)"] > 0


class TestSubtract:
    """Tests for _subtract helper function."""
    
    def test_subtract_valid_numbers(self):
        """Test subtraction of valid numbers."""
        result = _subtract(100, 30)
        assert result == 70
    
    def test_subtract_none_minuend(self):
        """Test subtraction with None minuend."""
        result = _subtract(None, 30)
        assert result is None
    
    def test_subtract_none_subtrahend(self):
        """Test subtraction with None subtrahend."""
        result = _subtract(100, None)
        assert result is None
    
    def test_subtract_negative_result(self):
        """Test subtraction resulting in negative."""
        result = _subtract(30, 100)
        assert result == -70


class TestSafeDiv:
    """Tests for _safe_div helper function."""
    
    def test_safe_div_normal_division(self):
        """Test normal division."""
        result = _safe_div(100, 4)
        assert result == 25
    
    def test_safe_div_none_numerator(self):
        """Test division with None numerator."""
        result = _safe_div(None, 10)
        assert result is None
    
    def test_safe_div_none_denominator(self):
        """Test division with None denominator."""
        result = _safe_div(100, None)
        assert result is None
    
    def test_safe_div_zero_denominator(self):
        """Test division by zero."""
        result = _safe_div(100, 0)
        assert result is None
    
    def test_safe_div_exception_handling(self):
        """Test that exceptions in division are caught and return None."""
        with patch('src.analysis.ratios.logger') as mock_logger:
            class ProblematicNumber:
                def __truediv__(self, other):
                    raise RuntimeError("Unexpected error")
            
            result = _safe_div(ProblematicNumber(), 5)
            assert result is None
            mock_logger.warning.assert_called_once()
