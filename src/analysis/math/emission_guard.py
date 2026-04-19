"""Wave 4 — ValidityState ↔ final outward reason compatibility (emission guard).

Central policy for **outward canonical** ``reason_code`` / ``reason_codes`` on
``DerivedMetric``. Trace-only diagnostics and provenance markers are **not**
validated here (they do not belong in these fields).

**UNAVAILABLE** in product language maps to ``ValidityState.NOT_APPLICABLE`` in
this codebase (coverage / metric not applicable).

``PARTIAL`` outward emission is blocked until a dedicated contract exists; flip
``ALLOW_PARTIAL_OUTWARD_EMISSION`` when explicitly supported.
"""

from __future__ import annotations

from typing import Any

from src.analysis.math import reason_codes as rc
from src.analysis.math.reason_codes import is_declared_reason_code

ALLOW_PARTIAL_OUTWARD_EMISSION = False


def validate_final_outward_emission(metric: Any) -> None:
    """Raise ``ValueError`` if final outward reason fields violate Wave 4 rules.

    Intended to run on every ``DerivedMetric`` construction (Pydantic validator).
    Does not inspect ``trace`` for diagnostics — only ``reason_code`` /
    ``reason_codes`` / ``validity_state``.
    """
    from src.analysis.math.contracts import ValidityState

    vs = metric.validity_state
    primary = metric.reason_code
    supporting: list[str] = list(metric.reason_codes)

    if vs is ValidityState.PARTIAL:
        if not ALLOW_PARTIAL_OUTWARD_EMISSION:
            raise ValueError(
                "Wave 4 emission guard: PARTIAL validity_state is not enabled for "
                "outward emission (set ALLOW_PARTIAL_OUTWARD_EMISSION when supported)"
            )
        _validate_partial_when_enabled(primary, supporting)
        return

    if vs is ValidityState.VALID:
        _validate_valid(primary, supporting)
        return

    _validate_non_success(vs, primary, supporting)


def _validate_partial_when_enabled(primary: str | None, supporting: list[str]) -> None:
    """When PARTIAL is explicitly allowed, still require declared outward-only tokens."""
    if primary is None:
        raise ValueError(
            "Wave 4 emission guard: PARTIAL requires reason_code when outward emission is enabled"
        )
    if not supporting:
        raise ValueError(
            "Wave 4 emission guard: PARTIAL requires non-empty reason_codes when enabled"
        )
    if supporting[0] != primary:
        raise ValueError(
            "Wave 4 emission guard: PARTIAL reason_codes[0] must equal reason_code"
        )
    if not is_declared_reason_code(primary):
        raise ValueError(
            f"Wave 4 emission guard: undeclared outward primary reason_code {primary!r}"
        )
    for code in supporting:
        if not is_declared_reason_code(code):
            raise ValueError(
                f"Wave 4 emission guard: undeclared outward reason_codes entry {code!r}"
            )


def _validate_valid(primary: str | None, supporting: list[str]) -> None:
    for code in supporting:
        if not is_declared_reason_code(code):
            raise ValueError(
                f"Wave 4 emission guard: undeclared outward reason_codes entry {code!r}"
            )
    if primary is None:
        return
    if not is_declared_reason_code(primary):
        raise ValueError(
            f"Wave 4 emission guard: undeclared outward reason_code {primary!r}"
        )
    if not supporting:
        raise ValueError(
            "Wave 4 emission guard: VALID with reason_code requires non-empty reason_codes"
        )
    if supporting[0] != primary:
        raise ValueError(
            "Wave 4 emission guard: VALID reason_codes[0] must equal reason_code "
            "when reason_code is set"
        )


def _validate_non_success(
    vs: Any,
    primary: str | None,
    supporting: list[str],
) -> None:
    from src.analysis.math.contracts import ValidityState

    if primary is None:
        raise ValueError(
            "Wave 4 emission guard: non-success state requires reason_code (declared)"
        )
    if not supporting:
        raise ValueError(
            "Wave 4 emission guard: non-success state requires non-empty reason_codes"
        )
    if supporting[0] != primary:
        raise ValueError(
            "Wave 4 emission guard: reason_codes[0] must equal reason_code"
        )
    if not is_declared_reason_code(primary):
        raise ValueError(
            f"Wave 4 emission guard: undeclared outward primary reason_code {primary!r}"
        )
    for code in supporting:
        if not is_declared_reason_code(code):
            raise ValueError(
                f"Wave 4 emission guard: undeclared outward reason_codes entry {code!r}"
            )

    if vs is ValidityState.SUPPRESSED:
        if primary != rc.MATH_COVERAGE_INTENTIONALLY_SUPPRESSED:
            raise ValueError(
                "Wave 4 emission guard: SUPPRESSED requires primary "
                f"{rc.MATH_COVERAGE_INTENTIONALLY_SUPPRESSED!r}"
            )
        return

    if vs is ValidityState.NOT_APPLICABLE:
        if primary != rc.MATH_COVERAGE_OUT_OF_SCOPE:
            raise ValueError(
                "Wave 4 emission guard: NOT_APPLICABLE (unavailable) requires primary "
                f"{rc.MATH_COVERAGE_OUT_OF_SCOPE!r}"
            )
        return

    if vs is ValidityState.INVALID:
        if primary in (
            rc.MATH_COVERAGE_INTENTIONALLY_SUPPRESSED,
            rc.MATH_COVERAGE_OUT_OF_SCOPE,
        ):
            raise ValueError(
                "Wave 4 emission guard: INVALID must not use coverage suppression / "
                "out-of-scope codes as primary outward reason"
            )
        return


def assert_engine_emission_contract(metric: Any) -> None:
    """Explicit engine-boundary hook (optional duplicate of model guard).

    Call after assembling a metric in ``engine`` if an extra boundary assertion
    is desired; model construction already runs ``validate_final_outward_emission``.
    """
    validate_final_outward_emission(metric)
