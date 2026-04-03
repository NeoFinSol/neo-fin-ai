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


def extract_tables(
    pdf_path: str,
    force_ocr: bool = False,
) -> list[dict[str, Any]]:
    from src.analysis import pdf_extractor as facade

    with _patched_legacy(
        camelot=facade.camelot,
        extract_text_from_scanned=facade.extract_text_from_scanned,
    ):
        return legacy_helpers.extract_tables(pdf_path, force_ocr=force_ocr)
