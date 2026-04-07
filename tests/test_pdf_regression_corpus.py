from __future__ import annotations

import json
import warnings
from pathlib import Path

import pytest
from cryptography.utils import CryptographyDeprecationWarning

from src.analysis import pdf_extractor

warnings.filterwarnings(
    "ignore",
    message=r"ARC4 has been moved.*",
    category=CryptographyDeprecationWarning,
)


def _load_corpus() -> list[dict]:
    corpus_path = Path(__file__).parent / "data" / "pdf_regression_corpus.json"
    with corpus_path.open(encoding="utf-8") as fh:
        return json.load(fh)


def _load_real_fixture_manifest() -> list[dict]:
    manifest_path = (
        Path(__file__).parent / "data" / "pdf_real_fixtures" / "manifest.json"
    )
    with manifest_path.open(encoding="utf-8") as fh:
        return json.load(fh)


def _load_local_demo_cases() -> list[dict]:
    manifest_path = Path(__file__).parent / "data" / "demo_manifest.json"
    with manifest_path.open(encoding="utf-8") as fh:
        payload = json.load(fh)
    return payload["local_regression_cases"]


CORPUS_CASES = _load_corpus()

_LEGACY_SOURCE_TO_V2 = {
    "table_exact": "table",
    "table_partial": "table",
    "text_regex": "text",
    "derived": "derived",
    "issuer_fallback": "issuer_fallback",
}


@pytest.mark.parametrize(
    "case", CORPUS_CASES, ids=[case["name"] for case in CORPUS_CASES]
)
def test_pdf_regression_corpus(case: dict) -> None:
    metadata = pdf_extractor.parse_financial_statements_with_metadata(
        case.get("tables", []),
        case.get("text", ""),
    )

    for key, expected_value in case.get("expected_values", {}).items():
        assert (
            metadata[key].value == expected_value
        ), f"{case['name']}: expected {key}={expected_value}, got {metadata[key].value}"

    for key, expected_source in case.get("expected_sources", {}).items():
        normalized_expected = _LEGACY_SOURCE_TO_V2.get(expected_source, expected_source)
        assert (
            metadata[key].source == normalized_expected
        ), f"{case['name']}: expected source {key}={normalized_expected}, got {metadata[key].source}"


def test_extract_first_numeric_cell_skips_year_markers() -> None:
    value = pdf_extractor._extract_first_numeric_cell(
        ["2023", "2 300 000", "2022", "2 100 000"]
    )

    assert value == 2300000.0


def test_acceptance_corpus_covers_all_metric_keys() -> None:
    covered: set[str] = set()

    for case in _load_corpus():
        covered.update(case.get("expected_values", {}).keys())

    for case in _load_real_fixture_manifest():
        covered.update(case.get("expected_values", {}).keys())

    for case in _load_local_demo_cases():
        covered.update(case.get("expected", {}).keys())

    missing = set(pdf_extractor._METRIC_KEYWORDS) - covered

    assert not missing, f"Missing acceptance coverage for metrics: {sorted(missing)}"
