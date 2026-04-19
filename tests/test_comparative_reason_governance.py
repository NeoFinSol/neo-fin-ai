"""Wave 4 — comparative / period alignment with canonical outward reasons (layer-aware).

Does **not** require comparability enum strings (e.g. ``missing_opening_balance``) to be
registry tokens; those live in ``MetricInputRef`` wiring and comparative flags.
"""

from __future__ import annotations

from src.analysis.math import reason_codes as rc
from src.analysis.math.comparative import ComparativePeriodInput, run_comparative_math
from src.analysis.math.comparative_reasons import (
    DUPLICATE_PERIOD_ID,
    UNSUPPORTED_PERIOD_CLASS,
)
from src.analysis.math.contracts import ValidityState
from src.analysis.math.engine import MathEngine
from src.analysis.math.validators import normalize_inputs


def _period(
    label: str,
    *,
    revenue: float,
    net_profit: float,
    total_assets: float,
    equity: float,
) -> ComparativePeriodInput:
    return ComparativePeriodInput(
        period_label=label,
        metrics={
            "revenue": revenue,
            "net_profit": net_profit,
            "total_assets": total_assets,
            "equity": equity,
        },
        extraction_metadata=None,
    )


def test_comparative_reason_constants_alias_registry() -> None:
    """E. Re-exports reference the same strings as ``reason_codes``."""
    assert DUPLICATE_PERIOD_ID == rc.PERIOD_DUPLICATE_PERIOD_ID
    assert UNSUPPORTED_PERIOD_CLASS == rc.PERIOD_UNSUPPORTED_PERIOD_CLASS


def test_engine_roa_missing_opening_emits_comparative_canonical_outward() -> None:
    """Runtime path: eligibility surfaces multiple ``COMPARATIVE_*`` candidates; primary is resolved."""
    engine = MathEngine()
    result = engine.compute(
        normalize_inputs(
            {
                "net_profit": {"value": 12.0},
                "closing_total_assets": {"value": 140.0},
            }
        )
    )["roa"]
    assert result.validity_state is ValidityState.INVALID
    assert rc.COMPARATIVE_MISSING_OPENING_BALANCE in result.reason_codes
    assert result.reason_code.startswith("COMPARATIVE_")
    assert result.reason_code in result.reason_codes


def test_duplicate_period_surfaces_period_token_in_flags_not_lost() -> None:
    """E. Period duplicate is represented via canonical ``PERIOD_DUPLICATE_PERIOD_ID`` flag."""
    results = run_comparative_math(
        [
            _period(
                "2024",
                revenue=100.0,
                net_profit=10.0,
                total_assets=100.0,
                equity=50.0,
            ),
            _period(
                "2024",
                revenue=120.0,
                net_profit=12.0,
                total_assets=140.0,
                equity=70.0,
            ),
        ]
    )
    dup = results[1]
    assert DUPLICATE_PERIOD_ID in dup.comparability_flags
