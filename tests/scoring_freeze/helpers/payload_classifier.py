from typing import Any, Mapping

from tests.scoring_freeze.fixtures.models import PayloadClass, PayloadClassResolution

_PAYLOAD_CLASS_PRIORITY: tuple[PayloadClass, ...] = (
    "refused_payload",
    "invalid_or_suppressed_factor",
    "degraded_valid",
    "with_exclusions",
    "with_annualization",
    "empty_optional_sections",
    "full_success",
)


def resolve_payload_class(
    case_id: str,
    payload: Mapping[str, Any],
) -> PayloadClassResolution:
    traits = _collect_secondary_traits(payload)
    resolved_class = _resolve_primary_payload_class(payload, traits)
    return PayloadClassResolution(
        case_id=case_id,
        primary_payload_class=resolved_class,
        secondary_traits=frozenset(traits),
    )


def _resolve_primary_payload_class(
    payload: Mapping[str, Any],
    traits: set[str],
) -> PayloadClass:
    candidate_flags: dict[PayloadClass, bool] = {
        "refused_payload": _is_refused_payload(payload),
        "invalid_or_suppressed_factor": bool(
            {"has_invalid_factor", "has_suppressed_factor", "has_unavailable_factor"}
            & traits
        ),
        "degraded_valid": _is_degraded_payload(payload),
        "with_exclusions": "has_exclusions" in traits,
        "with_annualization": "annualized" in traits,
        "empty_optional_sections": "has_empty_optional_sections" in traits,
        "full_success": True,
    }
    for payload_class in _PAYLOAD_CLASS_PRIORITY:
        if candidate_flags[payload_class]:
            return payload_class
    return "full_success"


def _collect_secondary_traits(payload: Mapping[str, Any]) -> set[str]:
    traits: set[str] = set()
    methodology = payload.get("methodology")
    if isinstance(methodology, dict):
        period_basis = methodology.get("period_basis")
        if isinstance(period_basis, str) and period_basis.startswith("annualized"):
            traits.add("annualized")
        guardrails = methodology.get("guardrails")
        if isinstance(guardrails, list) and guardrails:
            traits.add("has_exclusions")
    factors = payload.get("factors")
    if isinstance(factors, list):
        if not factors:
            traits.add("has_empty_optional_sections")
        for factor in factors:
            if not isinstance(factor, dict):
                continue
            status = factor.get("status")
            if status == "invalid":
                traits.add("has_invalid_factor")
            if status == "suppressed":
                traits.add("has_suppressed_factor")
            if status == "unavailable":
                traits.add("has_unavailable_factor")
            if factor.get("impact") == "excluded":
                traits.add("has_exclusions")
    return traits


def _is_refused_payload(payload: Mapping[str, Any]) -> bool:
    if payload.get("status") in {"refused", "error"}:
        return True
    return payload.get("score") is None and not isinstance(payload.get("factors"), list)


def _is_degraded_payload(payload: Mapping[str, Any]) -> bool:
    confidence = payload.get("confidence_score")
    if isinstance(confidence, (int, float)) and confidence < 1.0:
        return True
    normalized_scores = payload.get("normalized_scores")
    if isinstance(normalized_scores, dict):
        return any(value is None for value in normalized_scores.values())
    return False
