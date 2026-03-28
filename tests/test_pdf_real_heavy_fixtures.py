from __future__ import annotations

import hashlib
import json
import os
import warnings
from pathlib import Path

import pytest
from cryptography.utils import CryptographyDeprecationWarning

warnings.filterwarnings(
    "ignore",
    message=r"ARC4 has been moved.*",
    category=CryptographyDeprecationWarning,
)
from src.analysis import pdf_extractor


FIXTURE_ROOT = Path(__file__).parent / "data" / "pdf_real_fixtures"
MANIFEST_PATH = FIXTURE_ROOT / "manifest_heavy.json"
RUN_HEAVY_REAL_PDF = os.getenv("RUN_PDF_REAL_HEAVY") == "1"

pytestmark = [
    pytest.mark.pdf_real_heavy,
    pytest.mark.skipif(
        not RUN_HEAVY_REAL_PDF,
        reason="Set RUN_PDF_REAL_HEAVY=1 to run the heavy real-PDF regression tier.",
    ),
    pytest.mark.filterwarnings(
        "ignore:.*camelot only works on text-based pages.*:UserWarning"
    ),
    pytest.mark.filterwarnings("ignore:No tables found.*:UserWarning"),
]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_cases() -> list[dict]:
    with MANIFEST_PATH.open(encoding="utf-8") as fh:
        return json.load(fh)


def _extract_pipeline(case: dict, pdf_path: Path) -> tuple[str, list[dict]]:
    pipeline = case.get("pipeline", "full_tables")
    if pipeline == "full_tables":
        return pdf_extractor.extract_text(str(pdf_path)), pdf_extractor.extract_tables(str(pdf_path))
    if pipeline == "force_ocr":
        return (
            pdf_extractor.extract_text_from_scanned(str(pdf_path)),
            pdf_extractor.extract_tables(str(pdf_path), force_ocr=True),
        )
    raise AssertionError(f"Unsupported heavy real-PDF pipeline: {pipeline}")


REAL_PDF_HEAVY_CASES = _load_cases()


@pytest.mark.parametrize(
    "case",
    REAL_PDF_HEAVY_CASES,
    ids=[case["id"] for case in REAL_PDF_HEAVY_CASES],
)
def test_pdf_real_heavy_fixtures(case: dict) -> None:
    pdf_path = FIXTURE_ROOT / case["filename"]

    assert pdf_path.exists(), f"Fixture file is missing: {pdf_path.name}"
    assert pdf_path.stat().st_size == case["size_bytes"]
    assert _sha256(pdf_path) == case["sha256"]

    scanned = pdf_extractor.is_scanned_pdf(str(pdf_path))
    assert scanned is case["expected_scanned"]

    text, tables = _extract_pipeline(case, pdf_path)
    assert len(text) >= case["min_text_length"]
    assert len(tables) >= case.get("min_table_count", 0)

    if "allowed_flavors" in case:
        actual_flavors = {table.get("flavor") for table in tables}
        assert actual_flavors.issubset(set(case["allowed_flavors"])), (
            f"{case['id']}: unexpected table flavors {sorted(actual_flavors)}"
        )

    metadata = pdf_extractor.parse_financial_statements_with_metadata(tables, text)

    for key, expected_value in case.get("expected_values", {}).items():
        assert metadata[key].value == expected_value, (
            f"{case['id']}: expected {key}={expected_value}, got {metadata[key].value}"
        )

    for key, expected_sources in case.get("expected_sources", {}).items():
        actual_source = metadata[key].source
        if isinstance(expected_sources, str):
            expected_sources = [expected_sources]
        assert actual_source in expected_sources, (
            f"{case['id']}: expected source for {key} in {expected_sources}, "
            f"got {actual_source}"
        )
