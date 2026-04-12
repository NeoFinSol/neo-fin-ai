from __future__ import annotations

import ast
from pathlib import Path

from src.analysis.ratios import calculate_ratios


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
        node.name
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
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
