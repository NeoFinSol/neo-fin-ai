from __future__ import annotations

from datetime import date

from src.analysis.math.periods import (
    ComparabilityState,
    PeriodClass,
    parse_period_label,
)
from src.analysis.math.reason_codes import PERIOD_UNSUPPORTED_PERIOD_CLASS


def test_parse_period_label_supports_year_label() -> None:
    parsed = parse_period_label("2024")

    assert parsed.period_ref is not None
    assert parsed.period_ref.period_class is PeriodClass.FY
    assert parsed.period_ref.fiscal_year == 2024
    assert parsed.period_ref.period_end == date(2024, 12, 31)
    assert parsed.comparability_state is ComparabilityState.COMPARABLE


def test_parse_period_label_supports_q1_label() -> None:
    parsed = parse_period_label("Q1/2025")

    assert parsed.period_ref is not None
    assert parsed.period_ref.period_class is PeriodClass.Q1
    assert parsed.period_ref.fiscal_year == 2025
    assert parsed.period_ref.period_end == date(2025, 3, 31)


def test_parse_period_label_supports_h1_label() -> None:
    parsed = parse_period_label("H1/2025")

    assert parsed.period_ref is not None
    assert parsed.period_ref.period_class is PeriodClass.H1
    assert parsed.period_ref.fiscal_year == 2025
    assert parsed.period_ref.period_end == date(2025, 6, 30)


def test_parse_period_label_parses_q4_but_does_not_equate_it_to_fy() -> None:
    parsed = parse_period_label("Q4/2024")

    assert parsed.period_ref is not None
    assert parsed.period_ref.period_class is PeriodClass.Q4
    assert parsed.period_ref.period_end == date(2024, 12, 31)
    assert parsed.period_ref.period_class is not PeriodClass.FY


def test_parse_period_label_marks_unknown_label_as_not_comparable() -> None:
    parsed = parse_period_label("9M/2025")

    assert parsed.period_ref is None
    assert parsed.comparability_state is ComparabilityState.NOT_COMPARABLE
    assert PERIOD_UNSUPPORTED_PERIOD_CLASS in parsed.reason_codes
