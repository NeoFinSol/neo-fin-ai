from __future__ import annotations

import math

from src.analysis.math.policies import DenominatorClass
from src.analysis.math.validators import classify_denominator
from src.analysis.scoring import _normalize_inverse


def test_normalize_inverse_rejects_non_positive_values() -> None:
    assert _normalize_inverse(-1.0, max_acceptable=3.0) is None
    assert _normalize_inverse(0.0, max_acceptable=3.0) is None


def test_denominator_classification_rejects_zero_negative_near_zero_and_non_finite() -> None:
    assert classify_denominator(0.0) == DenominatorClass.ZERO
    assert classify_denominator(-5.0) == DenominatorClass.NEGATIVE_FINITE
    assert classify_denominator(1e-12) == DenominatorClass.NEAR_ZERO_FORBIDDEN
    assert classify_denominator(math.inf) == DenominatorClass.NON_FINITE
    assert classify_denominator(math.nan) == DenominatorClass.NON_FINITE
