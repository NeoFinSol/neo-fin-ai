from __future__ import annotations

AMBIGUOUS_PERIOD_LABEL = "ambiguous_period_label"
UNSUPPORTED_PERIOD_CLASS = "unsupported_period_class"
MISSING_PRIOR_PERIOD = "missing_prior_period"
MISSING_OPENING_BALANCE = "missing_opening_balance"
INCOMPATIBLE_PERIOD_CLASS = "incompatible_period_class"
PARTIALLY_COMPARABLE_CONTEXT = "partially_comparable_context"
INCONSISTENT_UNITS = "inconsistent_units"
INCONSISTENT_CURRENCY = "inconsistent_currency"
AVERAGE_BALANCE_CONTEXT_MISSING = "average_balance_context_missing"
DUPLICATE_PERIOD_ID = "duplicate_period_id"

ALL_COMPARATIVE_REASON_CODES = frozenset(
    {
        AMBIGUOUS_PERIOD_LABEL,
        UNSUPPORTED_PERIOD_CLASS,
        MISSING_PRIOR_PERIOD,
        MISSING_OPENING_BALANCE,
        INCOMPATIBLE_PERIOD_CLASS,
        PARTIALLY_COMPARABLE_CONTEXT,
        INCONSISTENT_UNITS,
        INCONSISTENT_CURRENCY,
        AVERAGE_BALANCE_CONTEXT_MISSING,
        DUPLICATE_PERIOD_ID,
    }
)
