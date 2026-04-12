from __future__ import annotations

import math

from src.analysis.ratios import _safe_div
from src.analysis.scoring import _normalize_inverse


def test_normalize_inverse_rejects_non_positive_values() -> None:
    assert _normalize_inverse(-1.0, max_acceptable=3.0) is None
    assert _normalize_inverse(0.0, max_acceptable=3.0) is None


def test_safe_div_rejects_zero_negative_near_zero_and_non_finite() -> None:
    assert _safe_div(10.0, 0.0) is None
    assert _safe_div(10.0, -5.0) is None
    assert _safe_div(10.0, 1e-12) is None
    assert _safe_div(10.0, math.inf) is None
    assert _safe_div(10.0, math.nan) is None
