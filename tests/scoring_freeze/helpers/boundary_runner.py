from typing import Any, Mapping

from src.analysis.scoring import (
    calculate_score_from_precomputed_ratios,
    calculate_score_with_context,
)
from tests.scoring_freeze.fixtures.models import (
    BoundaryExecutionResult,
    DocumentInputBundle,
    PrecomputedInputBundle,
    ScoringFreezeCase,
)

_RESULT_KIND_PAYLOAD = "payload"
_RESULT_KIND_STRUCTURED_REFUSAL = "structured_refusal"


def run_document_case(
    case: ScoringFreezeCase,
    bundle: DocumentInputBundle,
) -> BoundaryExecutionResult:
    if case.boundary_kind != "document":
        raise ValueError(f"Case {case.case_id} is not a document-boundary case")
    return _run_boundary_case(
        case=case,
        payload_factory=lambda: calculate_score_with_context(
            metrics=dict(bundle.metrics),
            filename=bundle.filename,
            text=bundle.text,
            extraction_metadata=_to_mutable_dict(bundle.extraction_metadata),
            profile=bundle.profile,
        ),
    )


def run_precomputed_case(
    case: ScoringFreezeCase,
    bundle: PrecomputedInputBundle,
) -> BoundaryExecutionResult:
    if case.boundary_kind != "precomputed":
        raise ValueError(f"Case {case.case_id} is not a precomputed-boundary case")
    return _run_boundary_case(
        case=case,
        payload_factory=lambda: calculate_score_from_precomputed_ratios(
            metrics=dict(bundle.metrics),
            ratios_ru=dict(bundle.ratios_ru),
            ratios_en=dict(bundle.ratios_en),
            methodology=dict(bundle.methodology),
            extraction_metadata=_to_mutable_dict(bundle.extraction_metadata),
        ),
    )


def _run_boundary_case(
    case: ScoringFreezeCase,
    payload_factory: Any,
) -> BoundaryExecutionResult:
    raw_result = payload_factory()
    payload = _extract_boundary_payload(raw_result)
    return BoundaryExecutionResult(
        case_id=case.case_id,
        boundary_kind=case.boundary_kind,
        result_kind=_detect_result_kind(payload),
        payload=payload,
        exception_type=None,
        exception_message=None,
    )


def _extract_boundary_payload(raw_result: Any) -> Mapping[str, Any] | None:
    if not isinstance(raw_result, dict):
        return None
    score_payload = raw_result.get("score_payload")
    if isinstance(score_payload, dict):
        return score_payload
    if isinstance(raw_result, Mapping):
        return raw_result
    return None


def _detect_result_kind(payload: Mapping[str, Any] | None) -> str:
    if payload is None:
        return _RESULT_KIND_STRUCTURED_REFUSAL
    status_value = payload.get("status")
    if status_value in {"refused", "error"}:
        return _RESULT_KIND_STRUCTURED_REFUSAL
    if "score" in payload or "methodology" in payload:
        return _RESULT_KIND_PAYLOAD
    return _RESULT_KIND_STRUCTURED_REFUSAL


def _to_mutable_dict(data: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if data is None:
        return None
    return dict(data)
