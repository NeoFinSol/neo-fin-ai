from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.analysis import pdf_extractor


def _load_corpus() -> list[dict]:
    corpus_path = Path(__file__).parent / "data" / "pdf_regression_corpus.json"
    with corpus_path.open(encoding="utf-8") as fh:
        return json.load(fh)


CORPUS_CASES = _load_corpus()


@pytest.mark.parametrize("case", CORPUS_CASES, ids=[case["name"] for case in CORPUS_CASES])
def test_pdf_regression_corpus(case: dict) -> None:
    metadata = pdf_extractor.parse_financial_statements_with_metadata(
        case.get("tables", []),
        case.get("text", ""),
    )

    for key, expected_value in case.get("expected_values", {}).items():
        assert metadata[key].value == expected_value, (
            f"{case['name']}: expected {key}={expected_value}, got {metadata[key].value}"
        )

    for key, expected_source in case.get("expected_sources", {}).items():
        assert metadata[key].source == expected_source, (
            f"{case['name']}: expected source {key}={expected_source}, got {metadata[key].source}"
        )


def test_extract_first_numeric_cell_skips_year_markers() -> None:
    value = pdf_extractor._extract_first_numeric_cell(
        ["2023", "2 300 000", "2022", "2 100 000"]
    )

    assert value == 2300000.0
