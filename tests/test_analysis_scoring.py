"""Tests for financial scoring calculations."""
import pytest

from src.analysis.scoring import (
    _normalize_inverse,
    _normalize_positive,
    _risk_level,
    _to_number,
    apply_data_quality_guardrails,
    calculate_integral_score,
)


class TestCalculateIntegralScore:
    """Tests for calculate_integral_score function."""

    def test_all_ratios_present(self):
        """Test score calculation with all ratios present."""
        ratios = {
            "Коэффициент текущей ликвидности": 2.5,
            "Коэффициент автономии": 0.6,
            "Рентабельность активов (ROA)": 0.15,
            "Рентабельность собственного капитала (ROE)": 0.25,
            "Финансовый рычаг": 1.0,
        }

        result = calculate_integral_score(ratios)

        assert "score" in result
        assert "risk_level" in result
        assert "details" in result
        assert isinstance(result["score"], float)
        assert 0 <= result["score"] <= 100

    def test_missing_ratios(self):
        """Test score calculation with missing ratios."""
        ratios = {
            "Коэффициент текущей ликвидности": 2.0,
            # Missing other ratios
        }

        result = calculate_integral_score(ratios)

        assert "score" in result
        assert result["risk_level"] in ("низкий", "средний", "высокий")
        # Only one ratio should be in details
        assert len(result["details"]) == 1

    def test_empty_ratios(self):
        """Test empty ratios dict returns zero score."""
        result = calculate_integral_score({})

        assert result["score"] == 0.0
        assert result["risk_level"] == "критический"
        assert result["details"] == {}

    def test_all_none_ratios(self):
        """Test all None ratios returns zero score."""
        ratios = {
            "Коэффициент текущей ликвидности": None,
            "Коэффициент автономии": None,
            "Рентабельность активов (ROA)": None,
            "Рентабельность собственного капитала (ROE)": None,
            "Финансовый рычаг": None,
        }

        result = calculate_integral_score(ratios)

        assert result["score"] == 0.0
        assert result["details"] == {}

    def test_risk_levels(self):
        """Test different risk level thresholds."""
        # High score - low risk
        high_ratios = {
            "Коэффициент текущей ликвидности": 3.0,
            "Коэффициент автономии": 0.8,
            "Рентабельность активов (ROA)": 0.2,
            "Рентабельность собственного капитала (ROE)": 0.3,
            "Финансовый рычаг": 0.5,
        }
        result = calculate_integral_score(high_ratios)
        assert result["risk_level"] == "низкий"

        # Medium score - medium risk
        med_ratios = {
            "Коэффициент текущей ликвидности": 1.5,
            "Коэффициент автономии": 0.4,
            "Рентабельность активов (ROA)": 0.05,
            "Рентабельность собственного капитала (ROE)": 0.1,
            "Финансовый рычаг": 1.2,
        }
        result = calculate_integral_score(med_ratios)
        assert result["risk_level"] in ("средний", "высокий")

    def test_string_values_converted(self):
        """Test string values are converted to numbers."""
        ratios = {
            "Коэффициент текущей ликвидности": "2.0",
            "Коэффициент автономии": "0.5",
            "Рентабельность активов (ROA)": "0.1",
            "Рентабельность собственного капитала (ROE)": "0.2",
            "Финансовый рычаг": "1.0",
        }

        result = calculate_integral_score(ratios)

        assert result["score"] > 0
        assert len(result["details"]) == 5

    def test_unknown_ratio_ignored(self):
        """Test unknown ratio names are ignored."""
        from src.analysis.scoring import _normalize_ratio

        # Unknown ratio should return None
        result = _normalize_ratio("Unknown Ratio Name", 5.0)
        assert result is None

    def test_data_quality_guardrails_cap_sparse_score(self):
        payload = {
            "score": 100.0,
            "risk_level": "low",
            "confidence_score": 0.25,
            "factors": [],
            "normalized_scores": {},
        }
        metrics = {
            "total_assets": 393923000.0,
            "liabilities": 191747000.0,
            "current_assets": 243770000.0,
            "short_term_liabilities": 167887000.0,
            "revenue": None,
            "net_profit": None,
            "equity": None,
        }

        guarded = apply_data_quality_guardrails(payload, metrics)

        assert guarded["score"] == 39.99
        assert guarded["risk_level"] == "high"


class TestNormalizePositive:
    """Tests for _normalize_positive function."""

    def test_value_below_target(self):
        """Test normalization when value is below target."""
        assert _normalize_positive(1.0, 2.0) == 0.5
        assert _normalize_positive(0.5, 2.0) == 0.25

    def test_value_equals_target(self):
        """Test normalization when value equals target."""
        assert _normalize_positive(2.0, 2.0) == 1.0
        assert _normalize_positive(0.1, 0.1) == 1.0

    def test_value_above_target(self):
        """Test normalization caps at 1.0."""
        assert _normalize_positive(3.0, 2.0) == 1.0
        assert _normalize_positive(10.0, 2.0) == 1.0

    def test_zero_value(self):
        """Test zero value returns 0.0."""
        assert _normalize_positive(0.0, 2.0) == 0.0

    def test_negative_value(self):
        """Test negative value returns 0.0."""
        assert _normalize_positive(-1.0, 2.0) == 0.0
        assert _normalize_positive(-10.0, 2.0) == 0.0


class TestNormalizeInverse:
    """Tests for _normalize_inverse function."""

    def test_zero_value(self):
        """Test zero value is treated as unavailable."""
        assert _normalize_inverse(0.0, 2.0) is None

    def test_negative_value(self):
        """Test negative value is treated as unavailable."""
        assert _normalize_inverse(-1.0, 2.0) is None

    def test_value_at_max_acceptable(self):
        """Test value at max_acceptable returns 0.0."""
        assert _normalize_inverse(2.0, 2.0) == 0.0

    def test_value_above_max(self):
        """Test value above max returns 0.0."""
        assert _normalize_inverse(3.0, 2.0) == 0.0
        assert _normalize_inverse(10.0, 2.0) == 0.0

    def test_value_halfway(self):
        """Test value halfway to max."""
        assert _normalize_inverse(1.0, 2.0) == 0.5

    def test_small_value(self):
        """Test small positive value."""
        assert _normalize_inverse(0.5, 2.0) == 0.75


class TestRiskLevel:
    """Tests for _risk_level function."""

    def test_low_risk(self):
        """Test low risk threshold (>= 75)."""
        assert _risk_level(75.0) == "низкий"
        assert _risk_level(90.0) == "низкий"
        assert _risk_level(100.0) == "низкий"

    def test_medium_risk(self):
        """Test medium risk threshold (55–74.9)."""
        assert _risk_level(55.0) == "средний"
        assert _risk_level(60.0) == "средний"
        assert _risk_level(74.9) == "средний"

    def test_high_risk(self):
        """Test high and critical risk thresholds below medium band."""
        assert _risk_level(54.9) == "высокий"
        assert _risk_level(35.0) == "высокий"
        assert _risk_level(34.9) == "критический"
        assert _risk_level(0.0) == "критический"


class TestToNumber:
    """Tests for _to_number function."""

    def test_int_conversion(self):
        """Test integer conversion."""
        assert _to_number(42) == 42.0
        assert _to_number(0) == 0.0
        assert _to_number(-10) == -10.0

    def test_float_conversion(self):
        """Test float conversion."""
        assert _to_number(3.14) == 3.14
        assert _to_number(0.0) == 0.0

    def test_string_conversion(self):
        """Test string conversion."""
        assert _to_number("42") == 42.0
        assert _to_number("3.14") == 3.14
        assert _to_number("-10.5") == -10.5

    def test_none_returns_none(self):
        """Test None returns None."""
        assert _to_number(None) is None

    def test_invalid_string_returns_none(self):
        """Test invalid string returns None."""
        assert _to_number("invalid") is None
        assert _to_number("") is None
        assert _to_number("N/A") is None

    def test_nan_value(self):
        """Test nan value is returned as nan."""
        result = _to_number(float('nan'))
        assert isinstance(result, float)
