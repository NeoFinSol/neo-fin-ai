"""Registry integrity tests for Wave 4 canonical reason vocabulary."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from src.analysis.math import reason_codes as rc


def test_validate_reason_code_registry_passes() -> None:
    rc.validate_reason_code_registry()


def test_all_reason_codes_is_exact_union_of_disjoint_groups() -> None:
    combined = frozenset().union(
        rc.MATH_REASON_CODES,
        rc.COMPARATIVE_REASON_CODES,
        rc.PERIOD_REASON_CODES,
        rc.NORMALIZATION_REASON_CODES,
        rc.SYNTHETIC_REASON_CODES,
    )
    assert combined == rc.ALL_REASON_CODES
    sizes = (
        len(rc.MATH_REASON_CODES),
        len(rc.COMPARATIVE_REASON_CODES),
        len(rc.PERIOD_REASON_CODES),
        len(rc.NORMALIZATION_REASON_CODES),
        len(rc.SYNTHETIC_REASON_CODES),
    )
    assert len(rc.ALL_REASON_CODES) == sum(sizes)


def test_uniqueness_across_all_declared_codes() -> None:
    assert len(rc.ALL_REASON_CODES) == len(set(rc.ALL_REASON_CODES))


def test_canonical_bindings_match_all_and_are_unique() -> None:
    bindings = rc.CANONICAL_REASON_CODE_BINDINGS
    assert len(bindings) == len(set(bindings))
    assert set(bindings) == rc.ALL_REASON_CODES


def test_allowed_prefixes_cover_every_code() -> None:
    for code in rc.ALL_REASON_CODES:
        assert rc.get_reason_namespace(code) is not None
        assert any(code.startswith(p) for p in rc.ALLOWED_REASON_PREFIXES)


def test_namespace_group_prefix_coherence() -> None:
    for code in rc.MATH_REASON_CODES:
        assert code.startswith("MATH_")
    for code in rc.COMPARATIVE_REASON_CODES:
        assert code.startswith("COMPARATIVE_")
    for code in rc.PERIOD_REASON_CODES:
        assert code.startswith("PERIOD_")
    for code in rc.NORMALIZATION_REASON_CODES:
        assert code.startswith("NORMALIZATION_")
    for code in rc.SYNTHETIC_REASON_CODES:
        assert code.startswith("SYNTHETIC_")


def test_is_declared_reason_code() -> None:
    assert rc.is_declared_reason_code(rc.MATH_UNIT_INCOMPATIBLE) is True
    assert rc.is_declared_reason_code("wave3_math_unit_incompatible") is False
    assert rc.is_declared_reason_code("SCORING_ANYTHING") is False


def test_get_reason_namespace_returns_family() -> None:
    assert rc.get_reason_namespace(rc.MATH_FORMULA_INPUTS_MISSING) == "MATH"
    assert (
        rc.get_reason_namespace(rc.COMPARATIVE_MISSING_OPENING_BALANCE) == "COMPARATIVE"
    )
    assert rc.get_reason_namespace(rc.PERIOD_UNSUPPORTED_PERIOD_CLASS) == "PERIOD"
    assert rc.get_reason_namespace("not_a_code") is None


def test_validate_reason_code_declared() -> None:
    rc.validate_reason_code_declared(rc.MATH_UNIT_INCOMPATIBLE)
    with pytest.raises(ValueError, match="not declared"):
        rc.validate_reason_code_declared("NOT_A_CANONICAL_CODE")


def test_validate_reason_code_namespace() -> None:
    rc.validate_reason_code_namespace(rc.MATH_UNIT_INCOMPATIBLE, "MATH")
    with pytest.raises(ValueError, match="namespace"):
        rc.validate_reason_code_namespace(rc.MATH_UNIT_INCOMPATIBLE, "COMPARATIVE")


def test_assert_reason_code_in_namespace() -> None:
    rc.assert_reason_code_in_namespace(rc.MATH_UNIT_INCOMPATIBLE, "MATH_")
    with pytest.raises(ValueError, match="does not start"):
        rc.assert_reason_code_in_namespace(rc.MATH_UNIT_INCOMPATIBLE, "COMPARATIVE_")


def test_token_shape_rejects_composite_like_strings() -> None:
    assert rc.REASON_CODE_TOKEN_PATTERN.fullmatch("MATH_MISSING:INPUT") is None
    assert rc.REASON_CODE_TOKEN_PATTERN.fullmatch("MATH_lowercase") is None
    assert (
        rc.REASON_CODE_TOKEN_PATTERN.fullmatch(rc.MATH_REQUIRED_INPUT_MISSING)
        is not None
    )


def test_assert_declared_reason_code_raises_on_unknown() -> None:
    with pytest.raises(ValueError, match="not declared"):
        rc.assert_declared_reason_code("UNKNOWN_CODE")


def test_validate_fails_on_cross_group_duplicate() -> None:
    contaminated = rc.MATH_REASON_CODES | {rc.PERIOD_UNSUPPORTED_PERIOD_CLASS}
    with patch.object(rc, "MATH_REASON_CODES", contaminated):
        with pytest.raises(ValueError, match="overlapping"):
            rc.validate_reason_code_registry()


def test_validate_fails_on_prefix_incoherence() -> None:
    bad = frozenset({*rc.MATH_REASON_CODES, "BADPREFIX_CODE"})
    with patch.object(rc, "MATH_REASON_CODES", bad):
        with pytest.raises(ValueError, match="incoherence"):
            rc.validate_reason_code_registry()
