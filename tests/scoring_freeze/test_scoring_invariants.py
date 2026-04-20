from __future__ import annotations

from dataclasses import replace
from typing import Any

from tests.scoring_freeze.fixtures.case_registry import (
    ALL_FREEZE_CASES,
    BLOCKER_CASES,
    CANONICAL_FREEZE_CASES,
    CASES_WITH_DUPLICATE_DOMAIN_ASSIGNMENT,
    CASES_WITH_INVALID_INVARIANT_LINKAGE,
    CASES_WITHOUT_CLASSIFICATION,
    CASES_WITHOUT_EXPECTATION,
    CASES_WITHOUT_INPUT_BUNDLE,
    CASES_WITHOUT_INVARIANT_SEEDS,
    CASES_WITHOUT_INVENTORY_LINKAGE,
    CASES_WITHOUT_PAYLOAD_RULE_SET,
)
from tests.scoring_freeze.fixtures.classification_registry import BLOCKER_CASES as BLOCKER_CASE_IDS
from tests.scoring_freeze.fixtures.input_bundles import (
    DOCUMENT_INPUT_BUNDLES,
    INPUT_BUNDLE_INDEX,
)
from tests.scoring_freeze.fixtures.invariant_registry import INVARIANT_SEEDS
from tests.scoring_freeze.fixtures.models import (
    DocumentInputBundle,
    PrecomputedInputBundle,
    ScoringFreezeCase,
)
from tests.scoring_freeze.helpers.boundary_runner import run_document_case, run_precomputed_case
from tests.scoring_freeze.helpers.payload_classifier import resolve_payload_class

_EXPECTED_INVARIANT_GROUPS = {
    "deterministic",
    "anti_coupling",
    "machine_contract",
    "data_binding",
    "payload_typing",
    "equivalence_preparation",
}


def test_invariant_groups_are_fully_covered_by_seeds() -> None:
    groups = {seed.group for seed in INVARIANT_SEEDS}
    assert groups == _EXPECTED_INVARIANT_GROUPS


def test_deterministic_invariants_same_case_same_payload_and_class() -> None:
    deterministic_seeds = [seed for seed in INVARIANT_SEEDS if seed.group == "deterministic"]
    assert deterministic_seeds
    for seed in deterministic_seeds:
        case = _find_case(seed.case_id)
        first = _execute_case(case)
        second = _execute_case(case)
        assert first["payload"] == second["payload"]
        assert first["resolution"].primary_payload_class == second["resolution"].primary_payload_class
        assert _machine_status_fields(first["payload"]) == _machine_status_fields(second["payload"])


def test_anti_coupling_invariants_machine_fields_not_display_text_primary() -> None:
    anti_coupling_seeds = [seed for seed in INVARIANT_SEEDS if seed.group == "anti_coupling"]
    assert anti_coupling_seeds
    for seed in anti_coupling_seeds:
        case = _find_case(seed.case_id)
        baseline = _execute_case(case)["payload"]
        variant = _execute_case(case, mutate_doc_context=True)["payload"]
        assert baseline["methodology"]["period_basis"] == variant["methodology"]["period_basis"]
        assert isinstance(baseline["factors"][0]["description"], str)
        assert isinstance(variant["factors"][0]["description"], str)


def test_machine_contract_invariants_status_reason_explanation_separated() -> None:
    machine_contract_seeds = [seed for seed in INVARIANT_SEEDS if seed.group == "machine_contract"]
    assert machine_contract_seeds
    for seed in machine_contract_seeds:
        payload = _execute_case(_find_case(seed.case_id))["payload"]
        assert isinstance(payload["score"], (int, float))
        assert payload["risk_level"] in {"low", "medium", "high", "critical"}
        assert isinstance(payload["methodology"]["guardrails"], list)
        assert isinstance(payload["factors"], list)
        for factor in payload["factors"]:
            assert isinstance(factor.get("description"), str)


def test_data_binding_invariants_are_stable_for_same_paths() -> None:
    data_binding_seeds = [seed for seed in INVARIANT_SEEDS if seed.group == "data_binding"]
    assert data_binding_seeds
    for seed in data_binding_seeds:
        case = _find_case(seed.case_id)
        first = _execute_case(case)["payload"]
        second = _execute_case(case)["payload"]
        assert first["methodology"]["benchmark_profile"] == second["methodology"]["benchmark_profile"]
        assert first["methodology"]["period_basis"] == second["methodology"]["period_basis"]
        assert first["normalized_scores"] == second["normalized_scores"]


def test_payload_typing_invariants_keep_numeric_boolean_and_omission_shapes() -> None:
    payload_typing_seeds = [seed for seed in INVARIANT_SEEDS if seed.group == "payload_typing"]
    assert payload_typing_seeds
    for seed in payload_typing_seeds:
        payload = _execute_case(_find_case(seed.case_id))["payload"]
        assert isinstance(payload["score"], (int, float))
        assert isinstance(payload["confidence_score"], (int, float))
        assert isinstance(payload["methodology"]["ifrs16_adjusted"], bool)
        assert isinstance(payload["methodology"]["guardrails"], list)
        assert isinstance(payload["factors"], list)


def test_equivalence_preparation_invariants_full_linkage_and_blocker_separation() -> None:
    equivalence_seeds = [seed for seed in INVARIANT_SEEDS if seed.group == "equivalence_preparation"]
    assert equivalence_seeds
    assert not CASES_WITHOUT_INPUT_BUNDLE
    assert not CASES_WITHOUT_CLASSIFICATION
    assert not CASES_WITHOUT_PAYLOAD_RULE_SET
    assert not CASES_WITHOUT_INVENTORY_LINKAGE
    assert not CASES_WITHOUT_EXPECTATION
    assert not CASES_WITHOUT_INVARIANT_SEEDS
    assert not CASES_WITH_INVALID_INVARIANT_LINKAGE
    assert not CASES_WITH_DUPLICATE_DOMAIN_ASSIGNMENT
    canonical_case_ids = {case.case_id for case in CANONICAL_FREEZE_CASES}
    assert canonical_case_ids.isdisjoint(BLOCKER_CASE_IDS)
    assert {case.case_id for case in BLOCKER_CASES} == set(BLOCKER_CASE_IDS)


def _execute_case(
    case: ScoringFreezeCase,
    *,
    mutate_doc_context: bool = False,
) -> dict[str, Any]:
    bundle = INPUT_BUNDLE_INDEX[case.input_bundle_id]
    if case.boundary_kind == "document":
        assert isinstance(bundle, DocumentInputBundle)
        run_bundle = bundle
        if mutate_doc_context:
            run_bundle = replace(
                bundle,
                filename=(bundle.filename or "") + "   ",
                text=((bundle.text or "") + " // Q1 // display-only formatting"),
            )
        execution = run_document_case(case, run_bundle)
    else:
        assert isinstance(bundle, PrecomputedInputBundle)
        execution = run_precomputed_case(case, bundle)
    assert execution.payload is not None
    resolution = resolve_payload_class(case.case_id, execution.payload)
    return {"payload": execution.payload, "resolution": resolution}


def _find_case(case_id: str) -> ScoringFreezeCase:
    for case in ALL_FREEZE_CASES:
        if case.case_id == case_id:
            return case
    raise AssertionError(f"Invariant seed references unknown case: {case_id}")


def _machine_status_fields(payload: dict[str, Any]) -> tuple[Any, Any, Any]:
    return (
        payload.get("score"),
        payload.get("risk_level"),
        payload.get("methodology", {}).get("period_basis"),
    )
