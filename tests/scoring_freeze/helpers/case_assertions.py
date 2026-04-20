from typing import Any

from tests.scoring_freeze.fixtures.models import (
    BoundaryExecutionResult,
    BoundaryExpectation,
    ClassificationDecision,
    PayloadClassResolution,
    PayloadFieldRule,
    ScoringFreezeCase,
)
from tests.scoring_freeze.helpers.domain_assertions import (
    assert_annualization_behavior,
    assert_guardrail_behavior,
)
from tests.scoring_freeze.helpers.machine_contract_assertions import (
    assert_machine_methodology_contract,
    assert_machine_reason_contract,
    assert_machine_status_contract,
)
from tests.scoring_freeze.helpers.numeric_assertions import (
    assert_hard_frozen_number,
    assert_soft_presentation_number,
)
from tests.scoring_freeze.helpers.payload_assertions import (
    assert_payload_matches_matrix,
)


def assert_boundary_case(
    case: ScoringFreezeCase,
    execution: BoundaryExecutionResult,
    resolution: PayloadClassResolution,
    expectation: BoundaryExpectation,
    classification: ClassificationDecision,
    payload_rules: tuple[PayloadFieldRule, ...],
) -> None:
    payload = _assert_boundary_execution(case, execution)
    _assert_crash_refusal_admissibility(execution)
    _assert_classification_admissibility(case, classification)
    _assert_payload_class_resolution(case, resolution)
    assert_payload_matches_matrix(payload, payload_rules)
    assert_machine_status_contract(payload, expectation.expected_status_fields)
    assert_machine_reason_contract(payload, expectation.expected_reason_fields)
    assert_machine_methodology_contract(
        payload, expectation.expected_annualization_fields
    )
    assert_annualization_behavior(payload, expectation.expected_annualization_fields)
    assert_guardrail_behavior(payload, expectation.expected_guardrail_fields)
    _assert_numeric_contract(payload, expectation)
    _assert_soft_presentation(payload, expectation)


def _assert_boundary_execution(
    case: ScoringFreezeCase,
    execution: BoundaryExecutionResult,
) -> dict[str, Any]:
    assert execution.case_id == case.case_id, "Execution case_id mismatch"
    assert execution.boundary_kind == case.boundary_kind, "Boundary kind mismatch"
    assert execution.payload is not None, "Boundary execution returned empty payload"
    payload = dict(execution.payload)
    payload["result_kind"] = execution.result_kind
    return payload


def _assert_crash_refusal_admissibility(execution: BoundaryExecutionResult) -> None:
    assert execution.result_kind in {"payload", "structured_refusal", "fixture_error"}
    if execution.result_kind == "fixture_error":
        error_repr = f"{execution.exception_type}: {execution.exception_message}"
        raise AssertionError(f"Fixture error is not admissible: {error_repr}")


def _assert_classification_admissibility(
    case: ScoringFreezeCase,
    classification: ClassificationDecision,
) -> None:
    assert (
        classification.case_id == case.case_id
    ), "Classification decision must match case"
    assert (
        classification.classification_id == case.classification_id
    ), "Case classification_id mismatch"


def _assert_payload_class_resolution(
    case: ScoringFreezeCase,
    resolution: PayloadClassResolution,
) -> None:
    assert resolution.case_id == case.case_id, "Resolution case_id mismatch"
    assert (
        resolution.primary_payload_class == case.primary_payload_class
    ), "Primary payload class mismatch"


def _assert_numeric_contract(
    payload: dict[str, Any],
    expectation: BoundaryExpectation,
) -> None:
    for field_path, expected_value in expectation.expected_numeric_fields.items():
        assert_hard_frozen_number(payload, field_path, expected_value)


def _assert_soft_presentation(
    payload: dict[str, Any],
    expectation: BoundaryExpectation,
) -> None:
    for field_path, expected_value in expectation.soft_presentation_fields.items():
        if isinstance(expected_value, (int, float)) or expected_value is None:
            assert_soft_presentation_number(payload, field_path, expected_value)
