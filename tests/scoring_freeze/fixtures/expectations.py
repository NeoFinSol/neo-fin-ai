from tests.scoring_freeze.fixtures.models import BoundaryExpectation

BOUNDARY_EXPECTATIONS: tuple[BoundaryExpectation, ...] = (
    BoundaryExpectation(
        expectation_id="exp-period-marker-annualization",
        expected_status_fields={"result_kind": "payload"},
        expected_reason_fields={},
        expected_numeric_fields={"score": None},
        expected_annualization_fields={"period_basis": "annualized_q1"},
        expected_guardrail_fields={},
        soft_presentation_fields={"notes": "marker-driven annualization path"},
    ),
    BoundaryExpectation(
        expectation_id="exp-ru-label-semantic-coupling",
        expected_status_fields={"result_kind": "payload"},
        expected_reason_fields={},
        expected_numeric_fields={"score": None},
        expected_annualization_fields={"period_basis": "reported"},
        expected_guardrail_fields={},
        soft_presentation_fields={"notes": "ru-label keyed data-binding hotspot"},
    ),
    BoundaryExpectation(
        expectation_id="exp-anomaly-helper-boundary-impact",
        expected_status_fields={"result_kind": "payload"},
        expected_reason_fields={"anomaly_filtered": True},
        expected_numeric_fields={"score": None},
        expected_annualization_fields={"period_basis": "reported"},
        expected_guardrail_fields={},
        soft_presentation_fields={"notes": "helper-origin boundary effect"},
    ),
    BoundaryExpectation(
        expectation_id="exp-empty-factors-preserved-quirk",
        expected_status_fields={"result_kind": "payload"},
        expected_reason_fields={"quirk": "empty_factors"},
        expected_numeric_fields={"score": 0.0, "confidence_score": 0.0},
        expected_annualization_fields={"period_basis": "reported"},
        expected_guardrail_fields={"guardrails": ["missing_core:revenue"]},
        soft_presentation_fields={"notes": "preserved temporary bug"},
    ),
)

EXPECTATION_INDEX: dict[str, BoundaryExpectation] = {
    item.expectation_id: item for item in BOUNDARY_EXPECTATIONS
}
