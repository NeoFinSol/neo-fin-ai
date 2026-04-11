from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from src.analysis import pdf_extractor
from src.analysis.issuer_fallback import apply_issuer_metric_overrides
from src.analysis.ratios import calculate_ratios
from src.analysis.scoring import calculate_score_with_context

REPO_ROOT = Path(__file__).resolve().parents[1]
DEMO_MANIFEST_PATH = REPO_ROOT / "tests" / "data" / "demo_manifest.json"
_TRUTHY_VALUES = {"1", "true", "yes", "on"}


def _should_run_local_regression() -> bool:
    return os.getenv("RUN_LOCAL_PDF_REGRESSION", "").strip().lower() in _TRUTHY_VALUES


def _load_demo_manifest() -> dict:
    with DEMO_MANIFEST_PATH.open("r", encoding="utf-8") as file:
        return json.load(file)


def _get_fixture_root(manifest: dict) -> Path:
    fixtures_root = manifest.get("fixtures_root", "tests/PDFforTests")
    return (REPO_ROOT / fixtures_root).resolve()


def _load_case_params() -> list[pytest.ParameterSet]:
    if not _should_run_local_regression():
        return [
            pytest.param(
                None,
                id="local-pdf-regression-disabled",
                marks=pytest.mark.skip(
                    reason="Set RUN_LOCAL_PDF_REGRESSION=1 to run local Magnit PDF regression checks."
                ),
            )
        ]

    manifest = _load_demo_manifest()
    cases = manifest.get("local_regression_cases", [])
    fixture_root = _get_fixture_root(manifest)

    params: list[pytest.ParameterSet] = []
    for case in cases:
        normalized_case = dict(case)
        normalized_case.setdefault("expected_none", [])
        normalized_case.setdefault("expected", {})

        pdf_path = fixture_root / normalized_case["filename"]
        if not pdf_path.exists():
            params.append(
                pytest.param(
                    None,
                    id=f"{normalized_case['id']}-missing",
                    marks=pytest.mark.skip(
                        reason=f"Local PDF fixture missing: {pdf_path.name}"
                    ),
                )
            )
            continue
        params.append(pytest.param(normalized_case, id=normalized_case["id"]))

    return params


def pytest_generate_tests(metafunc: pytest.Metafunc) -> None:
    if "case" in metafunc.fixturenames:
        metafunc.parametrize("case", _load_case_params())


@pytest.fixture(scope="module")
def extracted_payload_cache() -> dict[tuple[str, bool], tuple[str, list]]:
    return {}


def test_local_magnit_regression(
    case: dict | None,
    extracted_payload_cache: dict[tuple[str, bool], tuple[str, list]],
) -> None:
    if case is None:
        pytest.skip("Local Magnit regression is disabled or fixture is unavailable.")

    manifest = _load_demo_manifest()
    fixture_root = _get_fixture_root(manifest)
    pdf_path = fixture_root / case["filename"]
    cache_key = (case["filename"], bool(case.get("scanned")))
    cached_payload = extracted_payload_cache.get(cache_key)
    if cached_payload is None:
        if case.get("scanned"):
            text = pdf_extractor.extract_text_from_scanned(str(pdf_path))
            tables = []
        else:
            text = pdf_extractor.extract_text(str(pdf_path))
            tables = pdf_extractor.extract_tables(str(pdf_path))
        cached_payload = (text, tables)
        extracted_payload_cache[cache_key] = cached_payload

    text, tables = cached_payload
    metadata = pdf_extractor.parse_financial_statements_with_metadata(tables, text)
    metadata, _overrides = apply_issuer_metric_overrides(
        metadata,
        filename=case["filename"],
        text=text,
    )

    for key, expected_value in case["expected"].items():
        assert metadata[key].value == expected_value, (
            f"{case['id']}: expected {key}={expected_value}, got {metadata[key].value}"
        )

    for key in case.get("expected_none", []):
        assert metadata[key].value is None, (
            f"{case['id']}: expected {key}=None, got {metadata[key].value}"
        )

    expected_long_term = case.get("expected_long_term_liabilities")
    if expected_long_term is not None:
        liabilities = metadata["liabilities"].value
        short_term = metadata["short_term_liabilities"].value
        assert liabilities is not None and short_term is not None, (
            f"{case['id']}: expected liabilities/short_term_liabilities for long-term check"
        )
        assert liabilities - short_term == expected_long_term, (
            f"{case['id']}: expected long_term_liabilities={expected_long_term}, "
            f"got {liabilities - short_term}"
        )

    if case["id"] in {"magnit_2025_q1_scanned", "magnit_2025_h1_ifrs"}:
        metrics_values = {key: value.value for key, value in metadata.items()}
        ratios = calculate_ratios(metrics_values)
        quick_ratio = ratios["Коэффициент быстрой ликвидности"]
        current_assets = metrics_values.get("current_assets")
        inventory = metrics_values.get("inventory")

        assert quick_ratio is None or quick_ratio >= 0, (
            f"{case['id']}: quick_ratio must be non-negative or None, got {quick_ratio}"
        )
        assert (
            current_assets is None or inventory is None or current_assets >= inventory
        ), (
            f"{case['id']}: current_assets must be >= inventory when both present, "
            f"got current_assets={current_assets}, inventory={inventory}"
        )

    expected_scoring = case.get("expected_scoring")
    if expected_scoring:
        metrics_values = {key: value.value for key, value in metadata.items()}
        scoring_result = calculate_score_with_context(
            metrics_values,
            filename=case["filename"],
            text=text,
            extraction_metadata={
                key: {"confidence": value.confidence, "source": value.source}
                for key, value in metadata.items()
            },
        )
        score_payload = scoring_result["score_payload"]
        methodology = score_payload["methodology"]

        assert score_payload["score"] == expected_scoring["score"], (
            f"{case['id']}: expected score={expected_scoring['score']}, got {score_payload['score']}"
        )
        assert score_payload["risk_level"] == expected_scoring["risk_level"], (
            f"{case['id']}: expected risk_level={expected_scoring['risk_level']}, "
            f"got {score_payload['risk_level']}"
        )
        assert (
            score_payload["confidence_score"] == expected_scoring["confidence_score"]
        ), (
            f"{case['id']}: expected confidence_score={expected_scoring['confidence_score']}, "
            f"got {score_payload['confidence_score']}"
        )
        assert (
            methodology["benchmark_profile"] == expected_scoring["benchmark_profile"]
        ), (
            f"{case['id']}: expected benchmark_profile={expected_scoring['benchmark_profile']}, "
            f"got {methodology['benchmark_profile']}"
        )
        assert methodology["period_basis"] == expected_scoring["period_basis"], (
            f"{case['id']}: expected period_basis={expected_scoring['period_basis']}, "
            f"got {methodology['period_basis']}"
        )
        expected_leverage_basis = expected_scoring.get("leverage_basis")
        if expected_leverage_basis is not None:
            assert methodology["leverage_basis"] == expected_leverage_basis, (
                f"{case['id']}: expected leverage_basis={expected_leverage_basis}, "
                f"got {methodology['leverage_basis']}"
            )
        for guardrail in expected_scoring.get("guardrails", []):
            assert guardrail in methodology["guardrails"], (
                f"{case['id']}: expected guardrail {guardrail}, got {methodology['guardrails']}"
            )
        for adjustment in expected_scoring.get("adjustments", []):
            assert adjustment in methodology["adjustments"], (
                f"{case['id']}: expected adjustment {adjustment}, got {methodology['adjustments']}"
            )
