"""Wave 4 — ValidityState ↔ outward reason emission guard tests."""

from __future__ import annotations

import pytest

from src.analysis.math import emission_guard as eg
from src.analysis.math import reason_codes as rc
from src.analysis.math.contracts import DerivedMetric, MetricUnit, ValidityState


def _dm(
    *,
    validity_state: ValidityState,
    reason_code: str | None,
    reason_codes: list[str],
) -> DerivedMetric:
    return DerivedMetric(
        metric_id="probe",
        canonical_value=None,
        projected_value=None,
        unit=MetricUnit.RATIO,
        formula_id="probe",
        formula_version="v1",
        validity_state=validity_state,
        reason_code=reason_code,
        reason_codes=reason_codes,
        trace={},
    )


def test_invalid_without_primary_fails() -> None:
    with pytest.raises(ValueError, match="non-success state requires reason_code"):
        _dm(
            validity_state=ValidityState.INVALID,
            reason_code=None,
            reason_codes=[rc.MATH_FORMULA_INPUTS_MISSING],
        )


def test_not_applicable_wrong_primary_rejected() -> None:
    with pytest.raises(ValueError, match="NOT_APPLICABLE"):
        _dm(
            validity_state=ValidityState.NOT_APPLICABLE,
            reason_code=rc.MATH_FORMULA_INPUTS_MISSING,
            reason_codes=[rc.MATH_FORMULA_INPUTS_MISSING],
        )


def test_not_applicable_ok_with_out_of_scope() -> None:
    m = _dm(
        validity_state=ValidityState.NOT_APPLICABLE,
        reason_code=rc.MATH_COVERAGE_OUT_OF_SCOPE,
        reason_codes=[rc.MATH_COVERAGE_OUT_OF_SCOPE],
    )
    assert m.reason_code == rc.MATH_COVERAGE_OUT_OF_SCOPE


def test_suppressed_semantics_enforced() -> None:
    with pytest.raises(ValueError, match="SUPPRESSED requires primary"):
        _dm(
            validity_state=ValidityState.SUPPRESSED,
            reason_code=rc.MATH_REQUIRED_INPUT_MISSING,
            reason_codes=[
                rc.MATH_REQUIRED_INPUT_MISSING,
                rc.MATH_COVERAGE_INTENTIONALLY_SUPPRESSED,
            ],
        )

    ok = _dm(
        validity_state=ValidityState.SUPPRESSED,
        reason_code=rc.MATH_COVERAGE_INTENTIONALLY_SUPPRESSED,
        reason_codes=[rc.MATH_COVERAGE_INTENTIONALLY_SUPPRESSED],
    )
    assert ok.reason_code == rc.MATH_COVERAGE_INTENTIONALLY_SUPPRESSED


def test_partial_blocked_by_default() -> None:
    with pytest.raises(ValueError, match="PARTIAL validity_state is not enabled"):
        _dm(
            validity_state=ValidityState.PARTIAL,
            reason_code=rc.MATH_FORMULA_INPUTS_MISSING,
            reason_codes=[rc.MATH_FORMULA_INPUTS_MISSING],
        )


def test_partial_allowed_when_flag_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(eg, "ALLOW_PARTIAL_OUTWARD_EMISSION", True)
    m = _dm(
        validity_state=ValidityState.PARTIAL,
        reason_code=rc.MATH_FORMULA_INPUTS_MISSING,
        reason_codes=[rc.MATH_FORMULA_INPUTS_MISSING],
    )
    assert m.validity_state is ValidityState.PARTIAL


def test_undeclared_reason_code_rejected() -> None:
    with pytest.raises(ValueError, match="undeclared outward primary"):
        _dm(
            validity_state=ValidityState.INVALID,
            reason_code="not_a_registry_token",
            reason_codes=["not_a_registry_token"],
        )


def test_undeclared_supporting_entry_rejected() -> None:
    with pytest.raises(ValueError, match="undeclared outward reason_codes"):
        _dm(
            validity_state=ValidityState.INVALID,
            reason_code=rc.MATH_FORMULA_INPUTS_MISSING,
            reason_codes=[rc.MATH_FORMULA_INPUTS_MISSING, "trace_only_diagnostic"],
        )


def test_invalid_must_not_use_coverage_primary() -> None:
    with pytest.raises(ValueError, match="INVALID must not use coverage"):
        _dm(
            validity_state=ValidityState.INVALID,
            reason_code=rc.MATH_COVERAGE_INTENTIONALLY_SUPPRESSED,
            reason_codes=[rc.MATH_COVERAGE_INTENTIONALLY_SUPPRESSED],
        )


def test_valid_supporting_only_no_primary_ok() -> None:
    m = _dm(
        validity_state=ValidityState.VALID,
        reason_code=None,
        reason_codes=[rc.MATH_FORMULA_DENOMINATOR_ZERO],
    )
    assert m.reason_code is None


def test_valid_with_primary_must_align() -> None:
    with pytest.raises(ValueError, match="reason_codes\\[0\\] must equal reason_code"):
        _dm(
            validity_state=ValidityState.VALID,
            reason_code=rc.MATH_FORMULA_INPUTS_MISSING,
            reason_codes=[rc.MATH_FORMULA_DENOMINATOR_ZERO],
        )


def test_diagnostics_not_required_in_registry_for_trace_only() -> None:
    """Guard only validates outward fields; absence of diagnostics in reason_codes is fine."""
    m = _dm(
        validity_state=ValidityState.INVALID,
        reason_code=rc.MATH_INPUT_NOT_NUMERIC,
        reason_codes=[rc.MATH_INPUT_NOT_NUMERIC],
    )
    assert "guard_failure" not in m.reason_codes


def test_valid_empty_supporting_reason_codes_ok() -> None:
    m = _dm(
        validity_state=ValidityState.VALID,
        reason_code=None,
        reason_codes=[],
    )
    assert m.reason_code is None
    assert m.reason_codes == []


def test_non_success_requires_primary_in_registry_not_diagnostic_alias() -> None:
    """C. Non-success must use declared primary; arbitrary strings rejected."""
    with pytest.raises(ValueError, match="undeclared outward primary"):
        _dm(
            validity_state=ValidityState.INVALID,
            reason_code="guard_failure_near_zero",
            reason_codes=["guard_failure_near_zero"],
        )
