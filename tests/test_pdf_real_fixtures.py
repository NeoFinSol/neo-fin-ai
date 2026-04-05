from __future__ import annotations

import hashlib
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


FIXTURE_ROOT = Path(__file__).parent / "data" / "pdf_real_fixtures"
MANIFEST_PATH = FIXTURE_ROOT / "manifest.json"
LEGACY_SOURCE_COMPAT = {
    "table_exact": "table",
    "table_partial": "table",
    "text_regex": "text",
    "derived": "derived",
    "issuer_fallback": "issuer_fallback",
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_cases() -> list[dict]:
    with MANIFEST_PATH.open(encoding="utf-8") as fh:
        return json.load(fh)


REAL_PDF_CASES = _load_cases()


@pytest.mark.pdf_real
@pytest.mark.parametrize(
    "case", REAL_PDF_CASES, ids=[case["id"] for case in REAL_PDF_CASES]
)
def test_pdf_real_smoke_fixtures(case: dict) -> None:
    pdf_path = FIXTURE_ROOT / case["filename"]

    assert pdf_path.exists(), f"Fixture file is missing: {pdf_path.name}"
    assert pdf_path.stat().st_size == case["size_bytes"]
    assert _sha256(pdf_path) == case["sha256"]

    scanned = pdf_extractor.is_scanned_pdf(str(pdf_path))
    assert scanned is case["expected_scanned"]

    text = pdf_extractor.extract_text(str(pdf_path))
    assert len(text) >= case["min_text_length"]

    pipeline = case.get("pipeline", "text_only")
    if pipeline == "text_only":
        tables: list[dict] = []
    else:
        tables = pdf_extractor.extract_tables(str(pdf_path))

    metadata = pdf_extractor.parse_financial_statements_with_metadata(tables, text)

    for key, expected_value in case.get("expected_values", {}).items():
        assert (
            metadata[key].value == expected_value
        ), f"{case['id']}: expected {key}={expected_value}, got {metadata[key].value}"

    for key, expected_sources in case.get("expected_sources", {}).items():
        actual_source = metadata[key].source
        if isinstance(expected_sources, str):
            expected_sources = [expected_sources]
        accepted_sources = {
            LEGACY_SOURCE_COMPAT.get(source, source) for source in expected_sources
        } | set(expected_sources)
        assert actual_source in accepted_sources, (
            f"{case['id']}: expected source for {key} in {expected_sources}, "
            f"got {actual_source}"
        )
