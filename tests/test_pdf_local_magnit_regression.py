from __future__ import annotations

import os
from pathlib import Path

import pytest

from src.analysis import pdf_extractor


FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "PDFforTests"
_TRUTHY_VALUES = {"1", "true", "yes", "on"}


def _should_run_local_regression() -> bool:
    return os.getenv("RUN_LOCAL_PDF_REGRESSION", "").strip().lower() in _TRUTHY_VALUES


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

    cases = [
        {
            "id": "magnit_2025_q1_scanned",
            "filename": "Бухгалтерская отчетность ПАО «Магнит» за 1 квартал 2025 года.pdf",
            "scanned": True,
            "expected": {
                "revenue": 103015000.0,
                "net_profit": 1348503000.0,
                "total_assets": 435659511000.0,
                "current_assets": 174989150000.0,
                "cash_and_equivalents": 1448897000.0,
                "equity": 209475516000.0,
                "liabilities": 226183995000.0,
                "short_term_liabilities": 192460146000.0,
            },
            "expected_none": [
                "inventory",
                "accounts_receivable",
            ],
        },
        {
            "id": "magnit_2022_ifrs",
            "filename": "Консолидированная финансовая отчетность ПАО «Магнит» за 2022 год.pdf",
            "scanned": False,
            "expected": {
                "revenue": 2351996423000.0,
                "net_profit": 27932517000.0,
                "total_assets": 1395998440000.0,
                "liabilities": 1188616136000.0,
            },
        },
        {
            "id": "magnit_2023_ifrs",
            "filename": "Консолидированная финансовая отчетность ПАО «Магнит» за 2023 год.pdf",
            "scanned": False,
            "expected": {
                "revenue": 2544688774000.0,
                "net_profit": 58677601000.0,
                "total_assets": 1429543267000.0,
                "liabilities": 1271075935000.0,
            },
        },
        {
            "id": "magnit_2025_h1_ifrs",
            "filename": "Консолидированная финансовая отчетность ПАО «Магнит» по МСФО за 1 полугодие 2025 год.pdf",
            "scanned": False,
            "expected": {
                "revenue": 1673223617000.0,
                "net_profit": 154479000.0,
                "total_assets": 1670048135000.0,
                "liabilities": 1486023626000.0,
            },
        },
    ]

    params: list[pytest.ParameterSet] = []
    for case in cases:
        pdf_path = FIXTURE_ROOT / case["filename"]
        if not pdf_path.exists():
            params.append(
                pytest.param(
                    None,
                    id=f"{case['id']}-missing",
                    marks=pytest.mark.skip(reason=f"Local PDF fixture missing: {pdf_path.name}"),
                )
            )
            continue
        params.append(pytest.param(case, id=case["id"]))

    return params


def pytest_generate_tests(metafunc: pytest.Metafunc) -> None:
    if "case" in metafunc.fixturenames:
        metafunc.parametrize("case", _load_case_params())


def test_local_magnit_regression(case: dict | None) -> None:
    if case is None:
        pytest.skip("Local Magnit regression is disabled or fixture is unavailable.")

    pdf_path = FIXTURE_ROOT / case["filename"]
    if case.get("scanned"):
        text = pdf_extractor.extract_text_from_scanned(str(pdf_path))
        tables = []
    else:
        text = pdf_extractor.extract_text(str(pdf_path))
        tables = pdf_extractor.extract_tables(str(pdf_path))
    metadata = pdf_extractor.parse_financial_statements_with_metadata(tables, text)

    for key, expected_value in case["expected"].items():
        assert metadata[key].value == expected_value, (
            f"{case['id']}: expected {key}={expected_value}, got {metadata[key].value}"
        )

    for key in case.get("expected_none", []):
        assert metadata[key].value is None, (
            f"{case['id']}: expected {key}=None, got {metadata[key].value}"
        )
