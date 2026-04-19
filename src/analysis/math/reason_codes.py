"""Wave 4 — canonical math-layer reason vocabulary (governance-only).

This module is the single source of truth for **outward-governed** reason string
identifiers emitted by the math layer. It does not assemble traces or merge
pipeline stages. **Final primary + supporting outward selection** lives in
``reason_resolution.py`` at engine assembly time (Wave 4).

Classification (pre-implementation inventory, Wave 4):
- Tokens promoted here are **category 1 — canonical outward reason codes** only.
- Internal composites (e.g. ``missing_required_input:<key>``), ``guard_failure``
  lexemes, precompute lineage markers, and ``ValueError`` prose stay **out** of
  this registry until later phases wire structured context separately.

Ambiguity note:
- ``MATH_INVALID_BASIS`` covers resolver ``wave3_invalid_basis`` (debt basis
  refusal at the math orchestration boundary). A ``COMPARATIVE_*`` split was
  considered; see ``.agent/open_design_ambiguities.md``. Narrowest safe choice:
  keep under ``MATH_*`` until a dedicated design decision lands.

Registry integrity:
- ``CANONICAL_REASON_CODE_BINDINGS`` lists every constant value exactly once;
  ``validate_reason_code_registry`` rejects duplicate string bindings and drift
  vs ``ALL_REASON_CODES``.
- Token shape: ``^(?:MATH|COMPARATIVE|PERIOD|NORMALIZATION|SYNTHETIC)_[A-Z0-9_]+$``
  (no lowercase, no ``:`` / composite leakage in identifiers).
"""

from __future__ import annotations

import re

# -----------------------------------------------------------------------------
# MATH_* — orchestration, coverage gates, resolver refusals, input/formula/denom
# -----------------------------------------------------------------------------

MATH_RESOLVER_AMBIGUOUS_CANDIDATES = "MATH_RESOLVER_AMBIGUOUS_CANDIDATES"
MATH_RESOLVER_NO_CANDIDATE = "MATH_RESOLVER_NO_CANDIDATE"
MATH_INVALID_BASIS = "MATH_INVALID_BASIS"

MATH_COVERAGE_INTENTIONALLY_SUPPRESSED = "MATH_COVERAGE_INTENTIONALLY_SUPPRESSED"
MATH_COVERAGE_OUT_OF_SCOPE = "MATH_COVERAGE_OUT_OF_SCOPE"
MATH_COVERAGE_REPORTED_CANDIDATE_REQUIRED = "MATH_COVERAGE_REPORTED_CANDIDATE_REQUIRED"
MATH_COVERAGE_APPROXIMATION_SEMANTICS_REQUIRED = (
    "MATH_COVERAGE_APPROXIMATION_SEMANTICS_REQUIRED"
)

MATH_DEBT_MIXED_BASIS = "MATH_DEBT_MIXED_BASIS"
MATH_DEBT_LEASE_LIABILITY_MIXING_FORBIDDEN = (
    "MATH_DEBT_LEASE_LIABILITY_MIXING_FORBIDDEN"
)

MATH_COMPUTE_BASIS_MISSING = "MATH_COMPUTE_BASIS_MISSING"
MATH_UNIT_INCOMPATIBLE = "MATH_UNIT_INCOMPATIBLE"

MATH_INPUT_NOT_NUMERIC = "MATH_INPUT_NOT_NUMERIC"
MATH_INPUT_UNEXPECTED_UNIT = "MATH_INPUT_UNEXPECTED_UNIT"
MATH_INPUT_NON_FINITE = "MATH_INPUT_NON_FINITE"
MATH_INPUT_UNEXPECTED_NEGATIVE = "MATH_INPUT_UNEXPECTED_NEGATIVE"

MATH_FORMULA_INPUTS_MISSING = "MATH_FORMULA_INPUTS_MISSING"
MATH_FORMULA_INPUT_NON_FINITE = "MATH_FORMULA_INPUT_NON_FINITE"
MATH_FORMULA_DENOMINATOR_ZERO = "MATH_FORMULA_DENOMINATOR_ZERO"
MATH_FORMULA_DENOMINATOR_NEAR_ZERO = "MATH_FORMULA_DENOMINATOR_NEAR_ZERO"
MATH_FORMULA_DIVISION_ERROR = "MATH_FORMULA_DIVISION_ERROR"

MATH_DENOMINATOR_INPUT_MISSING = "MATH_DENOMINATOR_INPUT_MISSING"
MATH_DENOMINATOR_POLICY_REFUSED = "MATH_DENOMINATOR_POLICY_REFUSED"
MATH_REQUIRED_INPUT_MISSING = "MATH_REQUIRED_INPUT_MISSING"

# -----------------------------------------------------------------------------
# COMPARATIVE_* — eligibility, average-balance context, metadata clashes
# -----------------------------------------------------------------------------

COMPARATIVE_MISSING_OPENING_BALANCE = "COMPARATIVE_MISSING_OPENING_BALANCE"
COMPARATIVE_MISSING_CLOSING_BALANCE = "COMPARATIVE_MISSING_CLOSING_BALANCE"
COMPARATIVE_INCOMPATIBLE_OPENING_BASIS = "COMPARATIVE_INCOMPATIBLE_OPENING_BASIS"
COMPARATIVE_INCOMPATIBLE_CLOSING_BASIS = "COMPARATIVE_INCOMPATIBLE_CLOSING_BASIS"
COMPARATIVE_FORBIDDEN_APPROXIMATION = "COMPARATIVE_FORBIDDEN_APPROXIMATION"
COMPARATIVE_UNKNOWN_AVERAGE_BALANCE_POLICY = (
    "COMPARATIVE_UNKNOWN_AVERAGE_BALANCE_POLICY"
)

COMPARATIVE_PARTIALLY_COMPARABLE_CONTEXT = "COMPARATIVE_PARTIALLY_COMPARABLE_CONTEXT"
COMPARATIVE_INCONSISTENT_UNITS_METADATA = "COMPARATIVE_INCONSISTENT_UNITS_METADATA"
COMPARATIVE_INCONSISTENT_CURRENCY_METADATA = (
    "COMPARATIVE_INCONSISTENT_CURRENCY_METADATA"
)
COMPARATIVE_AVERAGE_BALANCE_CONTEXT_MISSING = (
    "COMPARATIVE_AVERAGE_BALANCE_CONTEXT_MISSING"
)

# -----------------------------------------------------------------------------
# PERIOD_* — period parse + linkage identifiers (machine-stable)
# -----------------------------------------------------------------------------

PERIOD_UNSUPPORTED_PERIOD_CLASS = "PERIOD_UNSUPPORTED_PERIOD_CLASS"
PERIOD_MISSING_PRIOR_PERIOD = "PERIOD_MISSING_PRIOR_PERIOD"
PERIOD_DUPLICATE_PERIOD_ID = "PERIOD_DUPLICATE_PERIOD_ID"

# -----------------------------------------------------------------------------
# NORMALIZATION_* / SYNTHETIC_* — reserved families (empty in vocabulary-only phase)
# -----------------------------------------------------------------------------

NORMALIZATION_REASON_CODES: frozenset[str] = frozenset()
SYNTHETIC_REASON_CODES: frozenset[str] = frozenset()

MATH_REASON_CODES: frozenset[str] = frozenset(
    {
        MATH_RESOLVER_AMBIGUOUS_CANDIDATES,
        MATH_RESOLVER_NO_CANDIDATE,
        MATH_INVALID_BASIS,
        MATH_COVERAGE_INTENTIONALLY_SUPPRESSED,
        MATH_COVERAGE_OUT_OF_SCOPE,
        MATH_COVERAGE_REPORTED_CANDIDATE_REQUIRED,
        MATH_COVERAGE_APPROXIMATION_SEMANTICS_REQUIRED,
        MATH_DEBT_MIXED_BASIS,
        MATH_DEBT_LEASE_LIABILITY_MIXING_FORBIDDEN,
        MATH_COMPUTE_BASIS_MISSING,
        MATH_UNIT_INCOMPATIBLE,
        MATH_INPUT_NOT_NUMERIC,
        MATH_INPUT_UNEXPECTED_UNIT,
        MATH_INPUT_NON_FINITE,
        MATH_INPUT_UNEXPECTED_NEGATIVE,
        MATH_FORMULA_INPUTS_MISSING,
        MATH_FORMULA_INPUT_NON_FINITE,
        MATH_FORMULA_DENOMINATOR_ZERO,
        MATH_FORMULA_DENOMINATOR_NEAR_ZERO,
        MATH_FORMULA_DIVISION_ERROR,
        MATH_DENOMINATOR_INPUT_MISSING,
        MATH_DENOMINATOR_POLICY_REFUSED,
        MATH_REQUIRED_INPUT_MISSING,
    }
)

COMPARATIVE_REASON_CODES: frozenset[str] = frozenset(
    {
        COMPARATIVE_MISSING_OPENING_BALANCE,
        COMPARATIVE_MISSING_CLOSING_BALANCE,
        COMPARATIVE_INCOMPATIBLE_OPENING_BASIS,
        COMPARATIVE_INCOMPATIBLE_CLOSING_BASIS,
        COMPARATIVE_FORBIDDEN_APPROXIMATION,
        COMPARATIVE_UNKNOWN_AVERAGE_BALANCE_POLICY,
        COMPARATIVE_PARTIALLY_COMPARABLE_CONTEXT,
        COMPARATIVE_INCONSISTENT_UNITS_METADATA,
        COMPARATIVE_INCONSISTENT_CURRENCY_METADATA,
        COMPARATIVE_AVERAGE_BALANCE_CONTEXT_MISSING,
    }
)

PERIOD_REASON_CODES: frozenset[str] = frozenset(
    {
        PERIOD_UNSUPPORTED_PERIOD_CLASS,
        PERIOD_MISSING_PRIOR_PERIOD,
        PERIOD_DUPLICATE_PERIOD_ID,
    }
)

ALLOWED_REASON_PREFIXES: frozenset[str] = frozenset(
    {
        "MATH_",
        "COMPARATIVE_",
        "PERIOD_",
        "NORMALIZATION_",
        "SYNTHETIC_",
    }
)

ALL_REASON_CODES: frozenset[str] = frozenset().union(
    MATH_REASON_CODES,
    COMPARATIVE_REASON_CODES,
    PERIOD_REASON_CODES,
    NORMALIZATION_REASON_CODES,
    SYNTHETIC_REASON_CODES,
)

_PREFIX_TO_NAMESPACE: tuple[tuple[str, str], ...] = (
    ("MATH_", "MATH"),
    ("COMPARATIVE_", "COMPARATIVE"),
    ("PERIOD_", "PERIOD"),
    ("NORMALIZATION_", "NORMALIZATION"),
    ("SYNTHETIC_", "SYNTHETIC"),
)

REASON_CODE_TOKEN_PATTERN = re.compile(
    r"^(?:MATH|COMPARATIVE|PERIOD|NORMALIZATION|SYNTHETIC)_[A-Z0-9_]+$"
)

# Every canonical string must appear exactly once (catches duplicate bindings).
CANONICAL_REASON_CODE_BINDINGS: tuple[str, ...] = (
    MATH_RESOLVER_AMBIGUOUS_CANDIDATES,
    MATH_RESOLVER_NO_CANDIDATE,
    MATH_INVALID_BASIS,
    MATH_COVERAGE_INTENTIONALLY_SUPPRESSED,
    MATH_COVERAGE_OUT_OF_SCOPE,
    MATH_COVERAGE_REPORTED_CANDIDATE_REQUIRED,
    MATH_COVERAGE_APPROXIMATION_SEMANTICS_REQUIRED,
    MATH_DEBT_MIXED_BASIS,
    MATH_DEBT_LEASE_LIABILITY_MIXING_FORBIDDEN,
    MATH_COMPUTE_BASIS_MISSING,
    MATH_UNIT_INCOMPATIBLE,
    MATH_INPUT_NOT_NUMERIC,
    MATH_INPUT_UNEXPECTED_UNIT,
    MATH_INPUT_NON_FINITE,
    MATH_INPUT_UNEXPECTED_NEGATIVE,
    MATH_FORMULA_INPUTS_MISSING,
    MATH_FORMULA_INPUT_NON_FINITE,
    MATH_FORMULA_DENOMINATOR_ZERO,
    MATH_FORMULA_DENOMINATOR_NEAR_ZERO,
    MATH_FORMULA_DIVISION_ERROR,
    MATH_DENOMINATOR_INPUT_MISSING,
    MATH_DENOMINATOR_POLICY_REFUSED,
    MATH_REQUIRED_INPUT_MISSING,
    COMPARATIVE_MISSING_OPENING_BALANCE,
    COMPARATIVE_MISSING_CLOSING_BALANCE,
    COMPARATIVE_INCOMPATIBLE_OPENING_BASIS,
    COMPARATIVE_INCOMPATIBLE_CLOSING_BASIS,
    COMPARATIVE_FORBIDDEN_APPROXIMATION,
    COMPARATIVE_UNKNOWN_AVERAGE_BALANCE_POLICY,
    COMPARATIVE_PARTIALLY_COMPARABLE_CONTEXT,
    COMPARATIVE_INCONSISTENT_UNITS_METADATA,
    COMPARATIVE_INCONSISTENT_CURRENCY_METADATA,
    COMPARATIVE_AVERAGE_BALANCE_CONTEXT_MISSING,
    PERIOD_UNSUPPORTED_PERIOD_CLASS,
    PERIOD_MISSING_PRIOR_PERIOD,
    PERIOD_DUPLICATE_PERIOD_ID,
)


def is_declared_reason_code(code: str) -> bool:
    return code in ALL_REASON_CODES


def get_reason_namespace(code: str) -> str | None:
    for prefix, namespace in _PREFIX_TO_NAMESPACE:
        if code.startswith(prefix):
            return namespace
    return None


def validate_reason_code_declared(code: str) -> None:
    if not is_declared_reason_code(code):
        raise ValueError(f"reason code is not declared: {code!r}")


def assert_declared_reason_code(code: str) -> None:
    validate_reason_code_declared(code)


def validate_reason_code_namespace(code: str, expected_namespace: str) -> None:
    validate_reason_code_declared(code)
    actual = get_reason_namespace(code)
    if actual != expected_namespace:
        raise ValueError(
            f"reason code {code!r} has namespace {actual!r}, expected {expected_namespace!r}"
        )


def assert_reason_code_in_namespace(code: str, namespace_prefix: str) -> None:
    validate_reason_code_declared(code)
    if not code.startswith(namespace_prefix):
        raise ValueError(
            f"reason code {code!r} does not start with prefix {namespace_prefix!r}"
        )


def validate_reason_code_registry() -> None:
    """Fail-fast registry integrity check (startup/tests)."""
    _validate_prefix_registry_alignment()
    _validate_non_empty_strings(ALL_REASON_CODES)
    _validate_token_shape(ALL_REASON_CODES)
    _validate_prefix_membership(ALL_REASON_CODES)
    _validate_disjoint_groups()
    _validate_namespace_group_coherence()
    _validate_aggregate_union()
    _validate_binding_uniqueness_and_completeness()


def _validate_prefix_registry_alignment() -> None:
    derived = frozenset(prefix for prefix, _ in _PREFIX_TO_NAMESPACE)
    if derived != ALLOWED_REASON_PREFIXES:
        raise ValueError(
            "ALLOWED_REASON_PREFIXES out of sync with _PREFIX_TO_NAMESPACE: "
            f"derived={sorted(derived)!r} allowed={sorted(ALLOWED_REASON_PREFIXES)!r}"
        )


def _validate_non_empty_strings(codes: frozenset[str]) -> None:
    for code in codes:
        if not code or not code.strip():
            raise ValueError("reason code must be non-empty")
        if code != code.strip():
            raise ValueError(
                f"reason code must not have surrounding whitespace: {code!r}"
            )
        if code != code.upper():
            raise ValueError(f"reason code must be UPPER_SNAKE_CASE: {code!r}")
        if " " in code:
            raise ValueError(f"reason code must not contain spaces: {code!r}")


def _validate_token_shape(codes: frozenset[str]) -> None:
    for code in codes:
        if REASON_CODE_TOKEN_PATTERN.fullmatch(code) is None:
            raise ValueError(f"reason code has invalid token shape: {code!r}")


def _validate_prefix_membership(codes: frozenset[str]) -> None:
    for code in codes:
        if get_reason_namespace(code) is None:
            raise ValueError(f"reason code has no allowed prefix: {code!r}")


def _validate_namespace_group_coherence() -> None:
    _assert_group_matches_prefix("MATH", MATH_REASON_CODES, "MATH_")
    _assert_group_matches_prefix(
        "COMPARATIVE", COMPARATIVE_REASON_CODES, "COMPARATIVE_"
    )
    _assert_group_matches_prefix("PERIOD", PERIOD_REASON_CODES, "PERIOD_")
    _assert_group_matches_prefix(
        "NORMALIZATION", NORMALIZATION_REASON_CODES, "NORMALIZATION_"
    )
    _assert_group_matches_prefix("SYNTHETIC", SYNTHETIC_REASON_CODES, "SYNTHETIC_")


def _assert_group_matches_prefix(
    label: str, group: frozenset[str], expected_prefix: str
) -> None:
    for code in group:
        if not code.startswith(expected_prefix):
            raise ValueError(
                f"{label} registry incoherence: {code!r} does not start with "
                f"{expected_prefix!r}"
            )


def _validate_disjoint_groups() -> None:
    groups = (
        MATH_REASON_CODES,
        COMPARATIVE_REASON_CODES,
        PERIOD_REASON_CODES,
        NORMALIZATION_REASON_CODES,
        SYNTHETIC_REASON_CODES,
    )
    for i, first in enumerate(groups):
        for j, second in enumerate(groups):
            if j <= i:
                continue
            shared = first & second
            if shared:
                joined = ", ".join(sorted(shared))
                raise ValueError(
                    f"overlapping reason codes between group index {i} and {j}: {joined}"
                )


def _validate_aggregate_union() -> None:
    groups = (
        MATH_REASON_CODES,
        COMPARATIVE_REASON_CODES,
        PERIOD_REASON_CODES,
        NORMALIZATION_REASON_CODES,
        SYNTHETIC_REASON_CODES,
    )
    combined = frozenset().union(*groups)
    if combined != ALL_REASON_CODES:
        missing = sorted(ALL_REASON_CODES - combined)
        extra = sorted(combined - ALL_REASON_CODES)
        raise ValueError(
            "ALL_REASON_CODES must equal the disjoint union of namespace groups; "
            f"missing={missing!r} extra={extra!r}"
        )


def _validate_binding_uniqueness_and_completeness() -> None:
    bindings = CANONICAL_REASON_CODE_BINDINGS
    if len(bindings) != len(set(bindings)):
        raise ValueError(
            "duplicate canonical reason string in CANONICAL_REASON_CODE_BINDINGS"
        )
    bound = set(bindings)
    if bound != ALL_REASON_CODES:
        missing = sorted(ALL_REASON_CODES - bound)
        extra = sorted(bound - ALL_REASON_CODES)
        raise ValueError(
            "CANONICAL_REASON_CODE_BINDINGS must match ALL_REASON_CODES exactly: "
            f"missing={missing!r} extra={extra!r}"
        )
