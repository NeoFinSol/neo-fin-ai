"""G. Proof-of-usage: at least one runtime or API path per active outward family.

``NORMALIZATION_*`` / ``SYNTHETIC_*`` registries are empty in ``reason_codes`` — skipped until codes exist.
"""

from __future__ import annotations

import pytest

from src.analysis.math import reason_codes as rc
from src.analysis.math.comparative import ComparativePeriodInput, run_comparative_math
from src.analysis.math.engine import MathEngine
from src.analysis.math.periods import parse_period_label
from src.analysis.math.validators import normalize_inputs


def test_math_family_engine_path_covers_math_token() -> None:
    """Fixed inputs → deterministic outward codes (denominator missing when liability absent)."""
    engine = MathEngine()
    out = engine.compute(normalize_inputs({"current_assets": {"value": 100.0}}))[
        "current_ratio"
    ]
    assert out.validity_state.value == "invalid"
    assert out.reason_code == rc.MATH_DENOMINATOR_INPUT_MISSING
    assert out.reason_codes == [rc.MATH_DENOMINATOR_INPUT_MISSING]


def test_comparative_family_engine_path() -> None:
    engine = MathEngine()
    out = engine.compute(
        normalize_inputs(
            {
                "net_profit": {"value": 12.0},
                "closing_total_assets": {"value": 140.0},
            }
        )
    )["roa"]
    assert any(c.startswith("COMPARATIVE_") for c in out.reason_codes)


def test_period_family_parse_period_label_path() -> None:
    parsed = parse_period_label("not_a_valid_period_label_🌊")
    assert rc.PERIOD_UNSUPPORTED_PERIOD_CLASS in parsed.reason_codes


@pytest.mark.parametrize(
    "registry,label",
    [
        (rc.NORMALIZATION_REASON_CODES, "NORMALIZATION"),
        (rc.SYNTHETIC_REASON_CODES, "SYNTHETIC"),
    ],
)
def test_normalization_synthetic_registries_empty_skipped(
    registry: frozenset[str],
    label: str,
) -> None:
    if registry:
        pytest.fail(f"{label} registry non-empty: add a proof test for a runtime path")
    else:
        pytest.skip(f"no active outward {label} codes in registry yet")


def test_period_engine_path_when_duplicate_period_in_comparative_math() -> None:
    """Comparative path surfaces ``PERIOD_DUPLICATE_PERIOD_ID`` on period flags."""

    def p(label: str) -> ComparativePeriodInput:
        return ComparativePeriodInput(
            period_label=label,
            metrics={
                "revenue": 100.0,
                "net_profit": 10.0,
                "total_assets": 100.0,
                "equity": 50.0,
            },
            extraction_metadata=None,
        )

    results = run_comparative_math([p("2024"), p("2024")])
    assert rc.PERIOD_DUPLICATE_PERIOD_ID in results[1].comparability_flags
