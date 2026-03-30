from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from src.analysis import pdf_extractor


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
                    marks=pytest.mark.skip(reason=f"Local PDF fixture missing: {pdf_path.name}"),
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
