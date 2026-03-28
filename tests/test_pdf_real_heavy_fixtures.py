"""Optional heavy real-PDF regression tier.

Enable explicitly via `--run-pdf-real-heavy` or `RUN_PDF_REAL_HEAVY=1`.
"""
from __future__ import annotations

import hashlib
import json
import os
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
MANIFEST_PATH = FIXTURE_ROOT / "manifest_heavy.json"
_TRUTHY_VALUES = {"1", "true", "yes", "on"}

pytestmark = [
    pytest.mark.pdf_real_heavy,
    pytest.mark.filterwarnings(
        "ignore:.*camelot only works on text-based pages.*:UserWarning"
    ),
    pytest.mark.filterwarnings("ignore:No tables found.*:UserWarning"),
]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _should_run_heavy(pytestconfig: pytest.Config) -> bool:
    if pytestconfig.getoption("--run-pdf-real-heavy"):
        return True
    return os.getenv("RUN_PDF_REAL_HEAVY", "").strip().lower() in _TRUTHY_VALUES


def _load_case_params(pytestconfig: pytest.Config) -> list[pytest.ParameterSet]:
    if not _should_run_heavy(pytestconfig):
        return [
            pytest.param(
                None,
                id="heavy-tier-disabled",
                marks=pytest.mark.skip(
                    reason=(
                        "Set RUN_PDF_REAL_HEAVY=1 or pass --run-pdf-real-heavy "
                        "to run the heavy real-PDF regression tier."
                    )
                ),
            )
        ]

    if not MANIFEST_PATH.exists():
        return [
            pytest.param(
                None,
                id="heavy-manifest-missing",
                marks=pytest.mark.skip(
                    reason=f"Heavy real-PDF manifest is missing: {MANIFEST_PATH}"
                ),
            )
        ]

    try:
        with MANIFEST_PATH.open(encoding="utf-8") as fh:
            cases = json.load(fh)
    except json.JSONDecodeError as exc:
        return [
            pytest.param(
                None,
                id="heavy-manifest-invalid",
                marks=pytest.mark.skip(
                    reason=(
                        f"Heavy real-PDF manifest is invalid: {MANIFEST_PATH} "
                        f"({exc})"
                    )
                ),
            )
        ]

    return [pytest.param(case, id=case["id"]) for case in cases]


def pytest_generate_tests(metafunc: pytest.Metafunc) -> None:
    if "case" in metafunc.fixturenames:
        metafunc.parametrize("case", _load_case_params(metafunc.config))


def _extract_pipeline(case: dict, pdf_path: Path) -> tuple[str, list[dict]]:
    pipeline = case.get("pipeline", "full_tables")
    if pipeline == "full_tables":
        text = pdf_extractor.extract_text(str(pdf_path))
        tables = pdf_extractor.extract_tables(str(pdf_path))
    elif pipeline == "force_ocr":
        text = pdf_extractor.extract_text_from_scanned(str(pdf_path))
        tables = pdf_extractor.extract_tables(str(pdf_path), force_ocr=True)
    else:
        raise AssertionError(f"Unsupported heavy real-PDF pipeline: {pipeline}")

    assert isinstance(text, str), f"Expected text pipeline to return str, got {type(text)!r}"
    assert isinstance(tables, list), f"Expected table pipeline to return list, got {type(tables)!r}"
    return text, tables


def test_pdf_real_heavy_fixtures(case: dict | None) -> None:
    if case is None:
        pytest.skip("Heavy real-PDF tier is disabled or unavailable.")

    pdf_path = FIXTURE_ROOT / case["filename"]

    assert pdf_path.exists(), f"Fixture file is missing: {pdf_path.name}"
    assert pdf_path.stat().st_size == case["size_bytes"]
    assert _sha256(pdf_path) == case["sha256"]

    scanned = pdf_extractor.is_scanned_pdf(str(pdf_path))
    assert bool(scanned) == bool(case["expected_scanned"])

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
