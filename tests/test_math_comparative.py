from __future__ import annotations

import pytest

from src.analysis.math.comparative import ComparativePeriodInput, run_comparative_math
from src.analysis.math.comparative_reasons import (
    AVERAGE_BALANCE_CONTEXT_MISSING,
    DUPLICATE_PERIOD_ID,
    INCONSISTENT_UNITS,
    MISSING_OPENING_BALANCE,
    MISSING_PRIOR_PERIOD,
    PARTIALLY_COMPARABLE_CONTEXT,
    UNSUPPORTED_PERIOD_CLASS,
)
from src.analysis.math.contracts import ValidityState
from src.analysis.math.periods import ComparabilityState


def _period_input(
    period_label: str,
    *,
    revenue: float,
    net_profit: float,
    total_assets: float,
    equity: float,
    extraction_metadata: dict | None = None,
) -> ComparativePeriodInput:
    return ComparativePeriodInput(
        period_label=period_label,
        metrics={
            "revenue": revenue,
            "net_profit": net_profit,
            "total_assets": total_assets,
            "equity": equity,
        },
        extraction_metadata=extraction_metadata,
    )


def test_run_comparative_math_enables_strict_metrics_for_fy_pair() -> None:
    results = run_comparative_math(
        [
            _period_input(
                "2023",
                revenue=100.0,
                net_profit=10.0,
                total_assets=100.0,
                equity=50.0,
            ),
            _period_input(
                "2024",
                revenue=120.0,
                net_profit=12.0,
                total_assets=140.0,
                equity=70.0,
            ),
        ]
    )

    latest = results[1].derived_metrics
    assert latest["roa"].validity_state is ValidityState.VALID
    assert latest["roe"].validity_state is ValidityState.VALID
    assert latest["asset_turnover"].validity_state is ValidityState.VALID
    assert latest["roa"].value == 12.0 / 120.0
    assert latest["roe"].value == 12.0 / 60.0
    assert latest["asset_turnover"].value == 120.0 / 120.0


def test_run_comparative_math_uses_prior_fy_as_opening_for_q1() -> None:
    results = run_comparative_math(
        [
            _period_input(
                "2024",
                revenue=100.0,
                net_profit=10.0,
                total_assets=100.0,
                equity=50.0,
            ),
            _period_input(
                "Q1/2025",
                revenue=30.0,
                net_profit=6.0,
                total_assets=140.0,
                equity=70.0,
            ),
        ]
    )

    quarter = results[1]
    assert quarter.links.opening_balance_link is not None
    assert (
        quarter.links.opening_balance_link.period_id == results[0].period_ref.period_id
    )
    assert quarter.derived_metrics["roa"].validity_state is ValidityState.VALID
    assert quarter.derived_metrics["roa"].value == 6.0 / 120.0


def test_run_comparative_math_fails_closed_for_duplicate_periods() -> None:
    results = run_comparative_math(
        [
            _period_input(
                "2024",
                revenue=100.0,
                net_profit=10.0,
                total_assets=100.0,
                equity=50.0,
            ),
            _period_input(
                "2024",
                revenue=120.0,
                net_profit=12.0,
                total_assets=140.0,
                equity=70.0,
            ),
        ]
    )

    duplicate = results[1]
    assert DUPLICATE_PERIOD_ID in duplicate.comparability_flags
    assert duplicate.derived_metrics["roa"].validity_state is ValidityState.INVALID
    assert AVERAGE_BALANCE_CONTEXT_MISSING in duplicate.derived_metrics["roa"].reason_codes


def test_run_comparative_math_keeps_q4_fail_closed_for_strict_metrics() -> None:
    results = run_comparative_math(
        [
            _period_input(
                "2024",
                revenue=100.0,
                net_profit=10.0,
                total_assets=100.0,
                equity=50.0,
            ),
            _period_input(
                "Q4/2025",
                revenue=120.0,
                net_profit=12.0,
                total_assets=140.0,
                equity=70.0,
            ),
        ]
    )

    quarter = results[1]
    assert UNSUPPORTED_PERIOD_CLASS in quarter.comparability_flags
    assert quarter.derived_metrics["roa"].validity_state is ValidityState.INVALID
    assert quarter.derived_metrics["roe"].value is None


def test_q1_resolves_opening_balance_without_prior_comparable_link() -> None:
    results = run_comparative_math(
        [
            _period_input(
                "2023",
                revenue=80.0,
                net_profit=8.0,
                total_assets=80.0,
                equity=40.0,
            ),
            _period_input(
                "2024",
                revenue=100.0,
                net_profit=10.0,
                total_assets=100.0,
                equity=50.0,
            ),
            _period_input(
                "Q1/2025",
                revenue=30.0,
                net_profit=6.0,
                total_assets=140.0,
                equity=70.0,
            ),
        ]
    )

    q1 = results[2]
    assert q1.links.prior_comparable_link is None
    assert q1.links.opening_balance_link is not None
    assert q1.links.opening_balance_link.period_id == "FY/2024"


def test_run_comparative_math_uses_prior_fy_as_opening_for_h1() -> None:
    results = run_comparative_math(
        [
            _period_input(
                "2024",
                revenue=100.0,
                net_profit=10.0,
                total_assets=100.0,
                equity=50.0,
            ),
            _period_input(
                "H1/2025",
                revenue=60.0,
                net_profit=8.0,
                total_assets=130.0,
                equity=65.0,
            ),
        ]
    )

    h1 = results[1]
    assert h1.links.opening_balance_link is not None
    assert h1.links.opening_balance_link.period_id == "FY/2024"

    metrics = h1.derived_metrics
    assert metrics["roa"].validity_state is ValidityState.VALID
    assert metrics["roe"].validity_state is ValidityState.VALID
    assert metrics["asset_turnover"].validity_state is ValidityState.VALID
    # Wave 1a rounding policy: RATIO_STANDARD rounds to 4 decimal places
    assert metrics["roa"].value == pytest.approx(8.0 / 115.0, abs=0.0001)
    assert metrics["roe"].value == pytest.approx(8.0 / 57.5, abs=0.0001)
    assert metrics["asset_turnover"].value == pytest.approx(60.0 / 115.0, abs=0.0001)


def test_run_comparative_math_keeps_strict_metrics_fail_closed_for_single_period() -> (
    None
):
    results = run_comparative_math(
        [
            _period_input(
                "2024",
                revenue=100.0,
                net_profit=10.0,
                total_assets=100.0,
                equity=50.0,
            ),
        ]
    )

    sole = results[0]
    assert sole.links.prior_comparable_link is None
    assert sole.links.opening_balance_link is None
    assert sole.comparability_state is ComparabilityState.NOT_COMPARABLE
    assert MISSING_PRIOR_PERIOD in sole.comparability_flags
    assert MISSING_OPENING_BALANCE in sole.comparability_flags
    assert sole.derived_metrics["roa"].validity_state is ValidityState.INVALID
    assert sole.derived_metrics["roa"].value is None
    assert sole.derived_metrics["asset_turnover"].value is None


def test_partially_comparable_context_allows_average_balance_but_flags_missing_growth_dimension() -> (
    None
):
    results = run_comparative_math(
        [
            _period_input(
                "2023",
                revenue=80.0,
                net_profit=8.0,
                total_assets=80.0,
                equity=40.0,
            ),
            _period_input(
                "2024",
                revenue=100.0,
                net_profit=10.0,
                total_assets=100.0,
                equity=50.0,
            ),
            _period_input(
                "Q1/2025",
                revenue=30.0,
                net_profit=6.0,
                total_assets=140.0,
                equity=70.0,
            ),
        ]
    )

    q1 = results[2]
    assert q1.comparability_state is ComparabilityState.PARTIALLY_COMPARABLE
    assert MISSING_PRIOR_PERIOD in q1.comparability_flags
    assert PARTIALLY_COMPARABLE_CONTEXT in q1.comparability_flags
    assert q1.links.prior_comparable_link is None
    assert q1.links.opening_balance_link is not None
    assert q1.derived_metrics["roa"].validity_state is ValidityState.VALID
    assert q1.derived_metrics["roe"].validity_state is ValidityState.VALID
    assert q1.derived_metrics["asset_turnover"].validity_state is ValidityState.VALID


def test_inconsistent_unit_metadata_fail_closes_strict_metrics() -> None:
    results = run_comparative_math(
        [
            _period_input(
                "2023",
                revenue=100.0,
                net_profit=10.0,
                total_assets=100.0,
                equity=50.0,
                extraction_metadata={
                    "total_assets": {"unit": "thousands"},
                },
            ),
            _period_input(
                "2024",
                revenue=120.0,
                net_profit=12.0,
                total_assets=140.0,
                equity=70.0,
                extraction_metadata={
                    "total_assets": {"unit": "currency"},
                },
            ),
        ]
    )

    latest = results[1]
    assert INCONSISTENT_UNITS in latest.comparability_flags
    assert latest.derived_metrics["roa"].validity_state is ValidityState.INVALID
    assert latest.derived_metrics["roa"].value is None
