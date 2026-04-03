from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterator

from . import legacy_helpers


@contextmanager
def _patched_legacy(**overrides: Any) -> Iterator[None]:
    original: dict[str, Any] = {}
    for key, value in overrides.items():
        original[key] = getattr(legacy_helpers, key)
        setattr(legacy_helpers, key, value)
    try:
        yield
    finally:
        for key, value in original.items():
            setattr(legacy_helpers, key, value)


def extract_text(pdf_path: str) -> str:
    return legacy_helpers.extract_text(pdf_path)


def is_scanned_pdf(pdf_path: str) -> bool:
    return legacy_helpers.is_scanned_pdf(pdf_path)


def extract_text_from_scanned(pdf_path: str) -> str:
    from src.analysis import pdf_extractor as facade

    with _patched_legacy(
        pytesseract=facade.pytesseract,
        convert_from_path=facade.convert_from_path,
        TESSERACT_AVAILABLE=facade.TESSERACT_AVAILABLE,
        MAX_OCR_PAGES=facade.MAX_OCR_PAGES,
        _get_poppler_path=facade._get_poppler_path,
        _extract_layout_section_total_lines=facade._extract_layout_section_total_lines,
        _should_run_layout_metric_row_crop=facade._should_run_layout_metric_row_crop,
        _extract_layout_metric_value_lines=facade._extract_layout_metric_value_lines,
        _should_stop_scanned_ocr=facade._should_stop_scanned_ocr,
    ):
        return legacy_helpers.extract_text_from_scanned(pdf_path)
