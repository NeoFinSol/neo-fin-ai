"""Wave 4 — trace shape for reason semantics (governance, not vocabulary expansion).

``DerivedMetric.reason_code`` / ``reason_codes`` are the outward-authoritative
fields. The trace duplicates them only under ``final_outward`` so consumers can
distinguish:

- **final outward** snapshot (canonical identifiers, must match the model)
- **merged declared candidates** (input to ``reason_resolution``)
- **stage / refusal fragments** (candidate tuples from eligibility, resolver,
  compute basis — not final outward)
- **diagnostics** (``guard_failure``, ``input_invalidity_details``, etc.)

This module does **not** scan arbitrary trace strings for registry membership.
"""

from __future__ import annotations

from typing import Any

FINAL_OUTWARD_KEY = "final_outward"

MERGED_DECLARED_CANDIDATE_REASON_CODES_KEY = "merged_declared_candidate_reason_codes"

COMPUTATION_EXTRA_REASON_CODES_RAW_KEY = "computation_extra_reason_codes_raw"


def final_outward_snapshot(
    reason_code: str | None,
    reason_codes: list[str],
) -> dict[str, Any]:
    """Canonical block for final outward identifiers (must match ``DerivedMetric``)."""
    return {
        "reason_code": reason_code,
        "reason_codes": list(reason_codes),
    }


def validate_trace_final_outward_matches_model(metric: Any) -> None:
    """Raise ``ValueError`` if ``trace['final_outward']`` disagrees with outward fields.

    When ``final_outward`` is absent, no check (minimal test probes / legacy stubs).
    Assembly paths (``engine``, ``DerivedMetric.invalid``) always populate it.
    """
    block = metric.trace.get(FINAL_OUTWARD_KEY)
    if block is None:
        return
    expected = final_outward_snapshot(metric.reason_code, list(metric.reason_codes))
    if block.get("reason_code") != expected["reason_code"]:
        raise ValueError(
            "trace final_outward.reason_code does not match DerivedMetric.reason_code: "
            f"{block.get('reason_code')!r} vs {metric.reason_code!r}"
        )
    if list(block.get("reason_codes") or []) != expected["reason_codes"]:
        raise ValueError(
            "trace final_outward.reason_codes does not match DerivedMetric.reason_codes: "
            f"{block.get('reason_codes')!r} vs {metric.reason_codes!r}"
        )
