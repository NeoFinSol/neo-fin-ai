"""Wave 4 — final outward reason resolution (Math Layer v2 assembly boundary).

Authority: **Engine final result assembly** (`engine.py` → `DerivedMetric`) owns
selection of ``reason_code`` (primary) and ordered ``reason_codes`` (supporting).

Semantic classes
----------------

**Eligible for final outward resolution** (may become ``reason_code`` / ``reason_codes``):

- Any string in ``reason_codes.ALL_REASON_CODES`` (canonical outward vocabulary).
- These are the only machine tokens that may appear on ``DerivedMetric.reason_code``
  and ``DerivedMetric.reason_codes`` after assembly.

**Explicitly excluded** (must never drive primary selection; never promoted here):

- Trace-only diagnostics (e.g. ``guard_failure`` lexemes, policy prose tails).
- Lineage / provenance markers (e.g. precompute synthetic markers not in
  ``ALL_REASON_CODES``).
- Arbitrary debug tokens and composite contextual strings (``:``-style payloads).

Callers MUST pass only **declared** codes into this module; ``resolve_*`` filters
with ``is_declared_reason_code`` as a final guard.

Candidate vs final
------------------

* **Candidate reasons** — stage-local lists (refusal tuples, merged engine inputs,
  ``MetricComputationResult.extra_reason_codes``) before assembly.

* **Final outward reasons** — the pair ``(reason_code, reason_codes)`` on
  ``DerivedMetric`` after deterministic resolution: exactly one primary for each
  non-success validity state, supporting list ordered with primary first.

Suppression / policy overrides
------------------------------

``emission_guard`` requires a **fixed** outward primary for these states; this
module must match it or ``DerivedMetric`` construction fails.

When ``validity_state`` is ``SUPPRESSED``, primary is **always**
``MATH_COVERAGE_INTENTIONALLY_SUPPRESSED``. Other eligible declared codes (if
any) follow as supporting reasons, deterministically ordered.

When ``validity_state`` is ``NOT_APPLICABLE``, primary is **always**
``MATH_COVERAGE_OUT_OF_SCOPE``, with the same supporting ordering.

Otherwise primary is the **eligible** candidate with the **lowest** priority tier
(see ``_PRIORITY_LADDER``); ties break lexicographically on the code string.
"""

from __future__ import annotations

from collections.abc import Sequence

from src.analysis.math import reason_codes as rc
from src.analysis.math.contracts import ValidityState
from src.analysis.math.reason_codes import is_declared_reason_code

# Lower tier = higher priority for primary selection among competing eligible codes.
# Ladder aligns with Wave 4 task ordering: structural input → unit → denom/basis
# → per-input semantics → formula → comparative/period → resolver/coverage/debt
# → suppression/out-of-scope (last in open competition; see state overrides above).
_PRIORITY_LADDER: tuple[tuple[int, frozenset[str]], ...] = (
    (10, frozenset({rc.MATH_REQUIRED_INPUT_MISSING})),
    (20, frozenset({rc.MATH_UNIT_INCOMPATIBLE})),
    (
        30,
        frozenset(
            {
                rc.MATH_DENOMINATOR_INPUT_MISSING,
                rc.MATH_DENOMINATOR_POLICY_REFUSED,
                rc.MATH_COMPUTE_BASIS_MISSING,
            }
        ),
    ),
    (
        40,
        frozenset(
            {
                rc.MATH_INPUT_NOT_NUMERIC,
                rc.MATH_INPUT_UNEXPECTED_UNIT,
                rc.MATH_INPUT_NON_FINITE,
                rc.MATH_INPUT_UNEXPECTED_NEGATIVE,
            }
        ),
    ),
    (
        50,
        frozenset(
            {
                rc.MATH_FORMULA_INPUTS_MISSING,
                rc.MATH_FORMULA_INPUT_NON_FINITE,
                rc.MATH_FORMULA_DENOMINATOR_ZERO,
                rc.MATH_FORMULA_DENOMINATOR_NEAR_ZERO,
                rc.MATH_FORMULA_DIVISION_ERROR,
            }
        ),
    ),
    (60, rc.COMPARATIVE_REASON_CODES),
    (70, rc.PERIOD_REASON_CODES),
    (
        80,
        frozenset(
            {
                rc.MATH_RESOLVER_AMBIGUOUS_CANDIDATES,
                rc.MATH_RESOLVER_NO_CANDIDATE,
                rc.MATH_INVALID_BASIS,
                rc.MATH_COVERAGE_REPORTED_CANDIDATE_REQUIRED,
                rc.MATH_COVERAGE_APPROXIMATION_SEMANTICS_REQUIRED,
                rc.MATH_DEBT_MIXED_BASIS,
                rc.MATH_DEBT_LEASE_LIABILITY_MIXING_FORBIDDEN,
            }
        ),
    ),
    (
        90,
        frozenset(
            {rc.MATH_COVERAGE_INTENTIONALLY_SUPPRESSED, rc.MATH_COVERAGE_OUT_OF_SCOPE}
        ),
    ),
)

_ASSEMBLY_FALLBACK_PRIMARY = rc.MATH_COMPUTE_BASIS_MISSING


def _priority_key(code: str) -> tuple[int, str]:
    """Return (tier, code) for sorting. Codes absent from ``_PRIORITY_LADDER`` use tier 999.

    New registry constants should be added to the ladder; until then they compete only
    on lexicographic ``code`` within the same tier (deterministic, but review when adding codes).
    """
    tier = 999
    for t, codes in _PRIORITY_LADDER:
        if code in codes:
            tier = t
            break
    return (tier, code)


def _eligible_only(candidates: Sequence[str]) -> list[str]:
    return [c for c in dict.fromkeys(candidates) if is_declared_reason_code(c)]


def resolve_outward_reasons_for_non_success(
    candidates: Sequence[str],
    *,
    validity_state: ValidityState,
) -> tuple[str, list[str]]:
    """Pick primary + ordered supporting reasons for INVALID / SUPPRESSED / NOT_APPLICABLE."""
    eligible = _eligible_only(candidates)

    if validity_state is ValidityState.SUPPRESSED:
        primary = rc.MATH_COVERAGE_INTENTIONALLY_SUPPRESSED
    elif validity_state is ValidityState.NOT_APPLICABLE:
        primary = rc.MATH_COVERAGE_OUT_OF_SCOPE
    else:
        if not eligible:
            primary = _ASSEMBLY_FALLBACK_PRIMARY
        else:
            primary = min(eligible, key=_priority_key)

    rest = [c for c in eligible if c != primary]
    rest.sort(key=_priority_key)
    ordered = [primary, *rest]
    return primary, ordered


def resolve_outward_reasons_for_success(
    candidates: Sequence[str],
) -> tuple[None, list[str]]:
    """VALID metrics: no primary ``reason_code``; supporting list is declared-only, sorted."""
    eligible = _eligible_only(candidates)
    if not eligible:
        return None, []
    ordered = sorted(eligible, key=_priority_key)
    return None, ordered
