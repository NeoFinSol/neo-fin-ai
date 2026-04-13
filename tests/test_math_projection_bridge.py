from __future__ import annotations

import ast
from pathlib import Path

from src.analysis.math.engine import MathEngine
from src.analysis.math.projections import project_legacy_ratios
from src.analysis.math.validators import normalize_inputs
from src.analysis.ratios import RATIO_KEY_MAP, calculate_ratios


def test_calculate_ratios_uses_math_engine_projection() -> None:
    ratios = calculate_ratios(
        {
            "current_assets": 200.0,
            "short_term_liabilities": 100.0,
            "cash_and_equivalents": 25.0,
            "revenue": 500.0,
            "net_profit": 50.0,
            "equity": 300.0,
            "total_assets": 600.0,
        }
    )

    assert ratios["Коэффициент текущей ликвидности"] == 2.0
    assert ratios["EBITDA маржа"] is None
    assert ratios["Финансовый рычаг (долг/капитал)"] is None


def test_ratios_module_has_no_local_formula_helpers() -> None:
    source = Path("src/analysis/ratios.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    function_names = {
        node.name for node in tree.body if isinstance(node, ast.FunctionDef)
    }

    forbidden = {"_safe_div", "_subtract", "_sum_required", "_abs_value"}
    assert forbidden.isdisjoint(function_names)


def test_projection_does_not_mutate_domain_metric() -> None:
    from src.analysis.math.contracts import DerivedMetric, MetricUnit, ValidityState
    from src.analysis.math.projections import project_metric_value

    metric = DerivedMetric(
        metric_id="ebitda_margin",
        unit=MetricUnit.RATIO,
        formula_id="ebitda_margin",
        formula_version="v1",
        validity_state=ValidityState.SUPPRESSED,
        trace={"status": "suppressed"},
    )

    _, projection_trace = project_metric_value(metric)

    assert projection_trace["projection"] == "suppressed_to_none"
    assert "projection" not in metric.trace


def test_projection_uses_suppressed_trace_for_unsupported_legacy_exports() -> None:
    engine = MathEngine()
    metrics = engine.compute(
        normalize_inputs(
            {
                "current_assets": {"value": 200.0},
                "short_term_liabilities": {"value": 100.0},
                "cash_and_equivalents": {"value": 25.0},
                "revenue": {"value": 500.0},
                "net_profit": {"value": 50.0},
                "equity": {"value": 300.0},
                "total_assets": {"value": 600.0},
            }
        )
    )

    _, projection_trace = project_legacy_ratios(metrics)

    assert projection_trace["Коэффициент быстрой ликвидности"]["projection"] == (
        "suppressed_to_none"
    )
    assert projection_trace["Финансовый рычаг (долг/капитал)"]["projection"] == (
        "suppressed_to_none"
    )


def test_projection_returns_enabled_average_balance_metrics_when_valid() -> None:
    engine = MathEngine()
    metrics = engine.compute(
        normalize_inputs(
            {
                "revenue": {"value": 120.0},
                "net_profit": {"value": 12.0},
                "average_total_assets": {"value": 120.0},
                "average_equity": {"value": 60.0},
            }
        )
    )

    values, _trace = project_legacy_ratios(metrics)

    assert values["Рентабельность активов (ROA)"] == 0.1
    assert values["Рентабельность собственного капитала (ROE)"] == 0.2
    assert values["Оборачиваемость активов"] == 1.0


def test_project_legacy_ratios_returns_all_map_keys() -> None:
    engine = MathEngine()
    metrics = engine.compute(
        normalize_inputs(
            {
                "current_assets": {"value": 200.0},
                "short_term_liabilities": {"value": 100.0},
                "cash_and_equivalents": {"value": 25.0},
                "revenue": {"value": 500.0},
                "net_profit": {"value": 50.0},
                "equity": {"value": 300.0},
                "total_assets": {"value": 600.0},
            }
        )
    )

    values, _trace = project_legacy_ratios(metrics)
    from src.analysis.math.projections import LEGACY_RATIO_NAME_MAP

    for metric_id, label in LEGACY_RATIO_NAME_MAP.items():
        assert label in values, f"Missing projection key for {metric_id} -> {label}"


def test_calculate_ratios_delegates_to_math_engine(monkeypatch) -> None:
    from src.analysis import ratios as ratios_module

    call_log: list[object] = []

    class SpyEngine:
        def compute(self, typed_inputs):
            call_log.append(typed_inputs)
            from src.analysis.math.contracts import (
                DerivedMetric,
                MetricUnit,
                ValidityState,
            )

            return {
                "current_ratio": DerivedMetric(
                    metric_id="current_ratio",
                    value=99.0,
                    unit=MetricUnit.RATIO,
                    formula_id="current_ratio",
                    formula_version="v1",
                    validity_state=ValidityState.VALID,
                    trace={"status": "valid"},
                ),
            }

    monkeypatch.setattr(ratios_module, "MathEngine", lambda: SpyEngine())

    ratios = calculate_ratios(
        {"current_assets": 200.0, "short_term_liabilities": 100.0}
    )

    assert len(call_log) == 1
    assert ratios["Коэффициент текущей ликвидности"] == 99.0


def test_scoring_handles_all_suppressed_ratios_without_crash() -> None:
    from src.analysis.scoring import build_score_payload

    all_none_ratios = {
        "current_ratio": None,
        "quick_ratio": None,
        "absolute_liquidity_ratio": None,
        "ros": None,
        "equity_ratio": None,
        "ebitda_margin": None,
        "roa": None,
        "roe": None,
        "financial_leverage": None,
        "financial_leverage_total": None,
        "financial_leverage_debt_only": None,
        "interest_coverage": None,
        "asset_turnover": None,
        "inventory_turnover": None,
        "receivables_turnover": None,
    }

    result = build_score_payload(
        raw_score={"liquidity": 0, "profitability": 0, "stability": 0, "activity": 0},
        ratios_en=all_none_ratios,
        methodology=None,
    )

    assert isinstance(result, dict)
    assert "score" in result
    assert "risk_level" in result


def test_legacy_and_ratio_key_maps_are_consistent() -> None:
    from src.analysis.math.projections import LEGACY_RATIO_NAME_MAP

    assert set(LEGACY_RATIO_NAME_MAP.keys()) == set(RATIO_KEY_MAP.values())


def test_metric_definitions_encode_naming_projections() -> None:
    from src.analysis.math.registry import REGISTRY

    definition = REGISTRY["current_ratio"]

    assert definition.legacy_label == "Коэффициент текущей ликвидности"
    assert definition.frontend_key == "current_ratio"


def test_ratio_lookup_maps_are_reexported_from_canonical_registry() -> None:
    from src.analysis import ratios
    from src.analysis.math import projections
    from src.analysis.math.registry import LEGACY_RATIO_NAME_MAP as canonical_legacy_map
    from src.analysis.math.registry import RATIO_KEY_MAP as canonical_ratio_key_map

    assert projections.LEGACY_RATIO_NAME_MAP is canonical_legacy_map
    assert ratios.RATIO_KEY_MAP is canonical_ratio_key_map
