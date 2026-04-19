"""Wave 4 — final outward reason resolution (unit tests)."""

from __future__ import annotations

import pytest

from src.analysis.math import reason_codes as rc
from src.analysis.math.contracts import ValidityState
from src.analysis.math.precompute import APPROXIMATED_EBITDA_REASON_CODES
from src.analysis.math.reason_resolution import (
    resolve_outward_reasons_for_non_success,
    resolve_outward_reasons_for_success,
)


def test_multiple_eligible_primary_is_highest_priority_tier() -> None:
    """Missing-input outranks formula-level when both are declared candidates."""
    primary, ordered = resolve_outward_reasons_for_non_success(
        [
            rc.MATH_FORMULA_INPUTS_MISSING,
            rc.MATH_REQUIRED_INPUT_MISSING,
            rc.MATH_UNIT_INCOMPATIBLE,
        ],
        validity_state=ValidityState.INVALID,
    )
    assert primary == rc.MATH_REQUIRED_INPUT_MISSING
    assert ordered[0] == primary
    assert set(ordered) == {
        rc.MATH_REQUIRED_INPUT_MISSING,
        rc.MATH_UNIT_INCOMPATIBLE,
        rc.MATH_FORMULA_INPUTS_MISSING,
    }


def test_deterministic_ordering_lexicographic_tiebreak() -> None:
    """Same tier breaks lexicographically on code string (stable across runs)."""
    a, b = rc.MATH_FORMULA_DENOMINATOR_ZERO, rc.MATH_FORMULA_DIVISION_ERROR
    primary1, ord1 = resolve_outward_reasons_for_non_success(
        [b, a],
        validity_state=ValidityState.INVALID,
    )
    primary2, ord2 = resolve_outward_reasons_for_non_success(
        [a, b],
        validity_state=ValidityState.INVALID,
    )
    assert primary1 == primary2
    assert ord1 == ord2
    assert set(ord1) == {a, b}


def test_reason_codes_zero_is_reason_code() -> None:
    primary, ordered = resolve_outward_reasons_for_non_success(
        [rc.MATH_DENOMINATOR_POLICY_REFUSED],
        validity_state=ValidityState.INVALID,
    )
    assert ordered[0] == primary


def test_suppression_override_wins_over_higher_priority_candidate() -> None:
    primary, ordered = resolve_outward_reasons_for_non_success(
        [
            rc.MATH_REQUIRED_INPUT_MISSING,
            rc.MATH_COVERAGE_INTENTIONALLY_SUPPRESSED,
        ],
        validity_state=ValidityState.SUPPRESSED,
    )
    assert primary == rc.MATH_COVERAGE_INTENTIONALLY_SUPPRESSED
    assert ordered[0] == primary


def test_not_applicable_override_wins() -> None:
    primary, ordered = resolve_outward_reasons_for_non_success(
        [rc.MATH_FORMULA_INPUTS_MISSING, rc.MATH_COVERAGE_OUT_OF_SCOPE],
        validity_state=ValidityState.NOT_APPLICABLE,
    )
    assert primary == rc.MATH_COVERAGE_OUT_OF_SCOPE
    assert ordered[0] == primary


def test_diagnostics_and_provenance_filtered_not_promoted() -> None:
    """Undeclared strings never appear on outward lists (guard / lineage)."""
    lineage = next(iter(APPROXIMATED_EBITDA_REASON_CODES))
    primary, ordered = resolve_outward_reasons_for_non_success(
        [lineage, "guard_failure_near_zero", rc.MATH_FORMULA_DENOMINATOR_ZERO],
        validity_state=ValidityState.INVALID,
    )
    assert primary == rc.MATH_FORMULA_DENOMINATOR_ZERO
    assert lineage not in ordered
    assert not any("guard_failure" in c for c in ordered)


def test_empty_candidates_non_success_fallback() -> None:
    primary, ordered = resolve_outward_reasons_for_non_success(
        [],
        validity_state=ValidityState.INVALID,
    )
    assert primary == rc.MATH_COMPUTE_BASIS_MISSING
    assert ordered == [rc.MATH_COMPUTE_BASIS_MISSING]


def test_success_path_no_primary_sorted_supporting() -> None:
    p, ordered = resolve_outward_reasons_for_success(
        [rc.MATH_FORMULA_DENOMINATOR_ZERO, rc.MATH_FORMULA_DENOMINATOR_NEAR_ZERO]
    )
    assert p is None
    assert ordered == sorted(
        [rc.MATH_FORMULA_DENOMINATOR_ZERO, rc.MATH_FORMULA_DENOMINATOR_NEAR_ZERO]
    )


@pytest.mark.parametrize(
    "state,expected_primary",
    [
        (ValidityState.SUPPRESSED, rc.MATH_COVERAGE_INTENTIONALLY_SUPPRESSED),
        (ValidityState.NOT_APPLICABLE, rc.MATH_COVERAGE_OUT_OF_SCOPE),
    ],
)
def test_policy_state_empty_candidates_emits_canonical_primary(
    state: ValidityState,
    expected_primary: str,
) -> None:
    primary, ordered = resolve_outward_reasons_for_non_success([], validity_state=state)
    assert primary == expected_primary
    assert ordered == [expected_primary]


def test_primary_always_first_in_ordered_non_success() -> None:
    """D. ``reason_code`` is always ``reason_codes[0]`` after resolution."""
    primary, ordered = resolve_outward_reasons_for_non_success(
        [rc.MATH_FORMULA_DIVISION_ERROR, rc.MATH_REQUIRED_INPUT_MISSING],
        validity_state=ValidityState.INVALID,
    )
    assert ordered[0] == primary
    assert primary in ordered


def test_success_supporting_sorted_deterministically() -> None:
    a, b = rc.MATH_FORMULA_DENOMINATOR_ZERO, rc.MATH_FORMULA_DENOMINATOR_NEAR_ZERO
    _, o1 = resolve_outward_reasons_for_success([b, a])
    _, o2 = resolve_outward_reasons_for_success([a, b])
    assert o1 == o2
