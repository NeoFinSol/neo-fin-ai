from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from enum import Enum

from src.analysis.math.reason_codes import PERIOD_UNSUPPORTED_PERIOD_CLASS


class PeriodClass(str, Enum):
    FY = "fy"
    Q1 = "q1"
    Q2 = "q2"
    Q3 = "q3"
    Q4 = "q4"
    H1 = "h1"
    NINE_MONTHS = "nine_months"
    LTM = "ltm"


class ComparabilityState(str, Enum):
    COMPARABLE = "comparable"
    PARTIALLY_COMPARABLE = "partially_comparable"
    NOT_COMPARABLE = "not_comparable"


class ComparabilityFlag(str, Enum):
    AMBIGUOUS_PERIOD_LABEL = "ambiguous_period_label"
    UNSUPPORTED_PERIOD_CLASS = "unsupported_period_class"
    MISSING_PRIOR_PERIOD = "missing_prior_period"
    MISSING_OPENING_BALANCE = "missing_opening_balance"
    INCOMPATIBLE_PERIOD_CLASS = "incompatible_period_class"
    INCONSISTENT_UNITS = "inconsistent_units"
    INCONSISTENT_CURRENCY = "inconsistent_currency"
    DUPLICATE_PERIOD_ID = "duplicate_period_id"


@dataclass(frozen=True, slots=True)
class PeriodRef:
    period_id: str
    period_class: PeriodClass
    period_end: date
    fiscal_year: int
    source_period_label: str


@dataclass(frozen=True, slots=True)
class PeriodLinks:
    prior_comparable_link: PeriodRef | None = None
    opening_balance_link: PeriodRef | None = None


@dataclass(frozen=True, slots=True)
class RawPeriodParseResult:
    raw_label: str
    period_ref: PeriodRef | None
    comparability_state: ComparabilityState
    reason_codes: tuple[str, ...] = ()


_QUARTER_CLASS_MAP = {
    1: PeriodClass.Q1,
    2: PeriodClass.Q2,
    3: PeriodClass.Q3,
    4: PeriodClass.Q4,
}
_PERIOD_SORT_ORDER = {
    PeriodClass.FY: 0,
    PeriodClass.Q1: 1,
    PeriodClass.Q2: 2,
    PeriodClass.H1: 2,
    PeriodClass.Q3: 3,
    PeriodClass.NINE_MONTHS: 3,
    PeriodClass.Q4: 4,
    PeriodClass.LTM: 5,
}
STRICT_LINKAGE_PERIOD_CLASSES = frozenset(
    {
        PeriodClass.FY,
        PeriodClass.Q1,
        PeriodClass.H1,
    }
)


def parse_period_label(label: str) -> RawPeriodParseResult:
    normalized = label.strip()

    quarter_match = re.fullmatch(r"Q([1-4])/(\d{4})", normalized, re.IGNORECASE)
    if quarter_match:
        quarter = int(quarter_match.group(1))
        year = int(quarter_match.group(2))
        period_class = _QUARTER_CLASS_MAP[quarter]
        return RawPeriodParseResult(
            raw_label=normalized,
            period_ref=PeriodRef(
                period_id=f"{period_class.name}/{year}",
                period_class=period_class,
                period_end=_period_end_for(period_class, year),
                fiscal_year=year,
                source_period_label=normalized,
            ),
            comparability_state=ComparabilityState.COMPARABLE,
        )

    half_year_match = re.fullmatch(r"H1/(\d{4})", normalized, re.IGNORECASE)
    if half_year_match:
        year = int(half_year_match.group(1))
        return RawPeriodParseResult(
            raw_label=normalized,
            period_ref=PeriodRef(
                period_id=f"H1/{year}",
                period_class=PeriodClass.H1,
                period_end=_period_end_for(PeriodClass.H1, year),
                fiscal_year=year,
                source_period_label=normalized,
            ),
            comparability_state=ComparabilityState.COMPARABLE,
        )

    year_match = re.fullmatch(r"(\d{4})", normalized)
    if year_match:
        year = int(year_match.group(1))
        return RawPeriodParseResult(
            raw_label=normalized,
            period_ref=PeriodRef(
                period_id=f"FY/{year}",
                period_class=PeriodClass.FY,
                period_end=_period_end_for(PeriodClass.FY, year),
                fiscal_year=year,
                source_period_label=normalized,
            ),
            comparability_state=ComparabilityState.COMPARABLE,
        )

    return RawPeriodParseResult(
        raw_label=normalized,
        period_ref=None,
        comparability_state=ComparabilityState.NOT_COMPARABLE,
        reason_codes=(PERIOD_UNSUPPORTED_PERIOD_CLASS,),
    )


def compatibility_sort_key(label: str) -> tuple[int, int]:
    parsed = parse_period_label(label)
    if parsed.period_ref is None:
        return 9999, 99
    return (
        parsed.period_ref.fiscal_year,
        _PERIOD_SORT_ORDER.get(parsed.period_ref.period_class, 99),
    )


def supports_strict_linkage(period_class: PeriodClass) -> bool:
    return period_class in STRICT_LINKAGE_PERIOD_CLASSES


def _period_end_for(period_class: PeriodClass, fiscal_year: int) -> date:
    month_day_map = {
        PeriodClass.FY: (12, 31),
        PeriodClass.Q1: (3, 31),
        PeriodClass.Q2: (6, 30),
        PeriodClass.H1: (6, 30),
        PeriodClass.Q3: (9, 30),
        PeriodClass.NINE_MONTHS: (9, 30),
        PeriodClass.Q4: (12, 31),
        PeriodClass.LTM: (12, 31),
    }
    month, day = month_day_map[period_class]
    return date(fiscal_year, month, day)
