from __future__ import annotations

from copy import deepcopy
from typing import Any

from src.analysis.scoring import (
    calculate_score_from_precomputed_ratios,
    calculate_score_with_context,
)
from tests.scoring_freeze.fixtures.classification_registry import (
    PRESERVED_TEMPORARY_BUG_CASES,
)
from tests.scoring_freeze.fixtures.payload_rules import PAYLOAD_RULE_SET_INDEX
from tests.scoring_freeze.helpers.payload_assertions import (
    assert_payload_matches_matrix,
)

_BASE_METRICS: dict[str, Any] = {
    "revenue": 120_000_000.0,
    "net_profit": 5_000_000.0,
    "total_assets": 80_000_000.0,
    "liabilities": 30_000_000.0,
    "current_assets": 40_000_000.0,
    "short_term_liabilities": 20_000_000.0,
    "equity": 50_000_000.0,
    "cash_and_equivalents": 10_000_000.0,
    "inventory": 15_000_000.0,
    "cost_of_goods_sold": 90_000_000.0,
    "accounts_receivable": 10_000_000.0,
    "ebitda": 12_000_000.0,
    "ebit": 9_000_000.0,
    "interest_expense": 1_000_000.0,
}


def test_with_annualization_payload_contract_with_limited_snapshot() -> None:
    result = calculate_score_with_context(
        metrics=deepcopy(_BASE_METRICS),
        filename="payload_case_q1.pdf",
        text="Промежуточная отчетность за 1 квартал 2026",
        extraction_metadata=None,
        profile="generic",
    )
    payload = result["score_payload"]
    assert_payload_matches_matrix(
        payload, PAYLOAD_RULE_SET_INDEX["prs-with-annualization"]
    )

    # Soft snapshot: only stable, non-critical top-level shape.
    shape_snapshot = {
        "top_level_keys": tuple(sorted(payload.keys())),
        "methodology_keys": tuple(sorted(payload["methodology"].keys())),
    }
    assert shape_snapshot == {
        "top_level_keys": (
            "confidence_score",
            "factors",
            "methodology",
            "normalized_scores",
            "risk_level",
            "score",
        ),
        "methodology_keys": (
            "adjustments",
            "benchmark_profile",
            "detection_mode",
            "guardrails",
            "ifrs16_adjusted",
            "leverage_basis",
            "peer_context",
            "period_basis",
            "reasons",
        ),
    }


def test_degraded_valid_payload_contract_with_limited_snapshot() -> None:
    ratios_ru = {
        "Коэффициент текущей ликвидности": 2.0,
        "Коэффициент быстрой ликвидности": 1.0,
        "Коэффициент абсолютной ликвидности": 0.5,
        "Рентабельность активов (ROA)": 0.1,
        "Рентабельность собственного капитала (ROE)": 0.2,
        "Рентабельность продаж (ROS)": 2.01,  # anomaly -> excluded from normalized score
        "EBITDA маржа": 0.3,
        "Коэффициент автономии": 0.4,
        "Финансовый рычаг": 1.2,
        "Покрытие процентов": 5.0,
        "Оборачиваемость активов": 2.0,
        "Оборачиваемость запасов": 11.0,
        "Оборачиваемость дебиторской задолженности": 12.0,
    }
    result = calculate_score_from_precomputed_ratios(
        metrics=deepcopy(_BASE_METRICS),
        ratios_ru=ratios_ru,
        ratios_en={},
        methodology={
            "benchmark_profile": "generic",
            "period_basis": "reported",
            "reasons": [],
            "guardrails": [],
            "adjustments": [],
            "peer_context": [],
        },
        extraction_metadata=None,
    )
    payload = result["score_payload"]
    assert_payload_matches_matrix(payload, PAYLOAD_RULE_SET_INDEX["prs-degraded-valid"])

    # Soft snapshot: cardinality-focused shape check, not hard business contract.
    assert {
        "factors_count": len(payload["factors"]),
        "normalized_scores_keys_count": len(payload["normalized_scores"]),
    } == {"factors_count": 11, "normalized_scores_keys_count": 15}


def test_empty_optional_sections_preserved_quirk_remains_frozen() -> None:
    result = calculate_score_from_precomputed_ratios(
        metrics={
            "revenue": None,
            "net_profit": None,
            "current_assets": None,
            "short_term_liabilities": None,
            "equity": None,
            "liabilities": None,
        },
        ratios_ru={},
        ratios_en={},
        methodology={"benchmark_profile": "generic", "period_basis": "reported"},
        extraction_metadata=None,
    )
    payload = result["score_payload"]
    assert_payload_matches_matrix(
        payload, PAYLOAD_RULE_SET_INDEX["prs-empty-optional-sections"]
    )
    assert payload["score"] == 0.0
    assert payload["methodology"]["period_basis"] == "reported"
    assert "freeze-case-empty-factors-preserved-quirk" in PRESERVED_TEMPORARY_BUG_CASES
