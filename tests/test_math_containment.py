from __future__ import annotations

import math

from src.analysis.scoring import _normalize_inverse
from src.analysis.math.validators import classify_denominator


def test_normalize_inverse_rejects_non_positive_values() -> None:
    assert _normalize_inverse(-1.0, max_acceptable=3.0) is None
    assert _normalize_inverse(0.0, max_acceptable=3.0) is None


def test_denominator_classification_rejects_zero_negative_near_zero_and_non_finite() -> None:
    assert classify_denominator(0.0) == "zero"
    assert classify_denominator(-5.0) == "negative"
    assert classify_denominator(1e-12) == "near_zero"
    assert classify_denominator(math.inf) == "non_finite"
    assert classify_denominator(math.nan) == "non_finite"
