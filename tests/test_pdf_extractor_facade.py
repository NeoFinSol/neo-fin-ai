from __future__ import annotations

import inspect

from src.analysis import pdf_extractor
from src.analysis.extractor import ocr, pipeline, ranking, rules, text_extraction, types


def _module_filename(obj: object) -> str:
    source_path = inspect.getsourcefile(obj)
    assert source_path is not None
    return source_path.replace("\\", "/")


def test_pdf_extractor_facade_reexports_stable_public_contract() -> None:
    assert pdf_extractor.ExtractionMetadata is types.ExtractionMetadata
    assert pdf_extractor.ExtractionSource == types.ExtractionSource
    assert pdf_extractor.determine_source is ranking.determine_source
    assert pdf_extractor.apply_confidence_filter is ranking.apply_confidence_filter
    assert pdf_extractor._METRIC_KEYWORDS is rules._METRIC_KEYWORDS
    assert pdf_extractor.extract_metrics_regex is text_extraction.extract_metrics_regex
    assert (
        pdf_extractor.parse_financial_statements_with_metadata
        is pipeline.parse_financial_statements_with_metadata
    )
    assert (
        pdf_extractor.parse_financial_statements is pipeline.parse_financial_statements
    )


def test_pdf_extractor_public_entrypoints_live_in_internal_extractor_modules() -> None:
    assert _module_filename(pdf_extractor.determine_source).endswith(
        "/src/analysis/extractor/ranking.py"
    )
    assert _module_filename(pdf_extractor.is_scanned_pdf).endswith(
        "/src/analysis/extractor/ocr.py"
    )
    assert _module_filename(pdf_extractor.extract_text_from_scanned).endswith(
        "/src/analysis/extractor/ocr.py"
    )
    assert _module_filename(pdf_extractor.extract_tables).endswith(
        "/src/analysis/extractor/tables.py"
    )
    assert _module_filename(pdf_extractor.extract_metrics_regex).endswith(
        "/src/analysis/extractor/text_extraction.py"
    )
    assert _module_filename(
        pdf_extractor.parse_financial_statements_with_metadata
    ).endswith("/src/analysis/extractor/pipeline.py")
