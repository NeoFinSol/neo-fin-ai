from __future__ import annotations

import tempfile
from pathlib import Path

from src.analysis import pdf_extractor


def _build_pdf_bytes(text: str) -> bytes:
    escaped = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    content = f"BT /F1 24 Tf 100 100 Td ({escaped}) Tj ET"
    objects = [
        "1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj",
        "2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj",
        "3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 300 144] /Contents 4 0 R "
        "/Resources << /Font << /F1 5 0 R >> >> >> endobj",
        f"4 0 obj << /Length {len(content)} >> stream\n{content}\nendstream\nendobj",
        "5 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj",
    ]

    pdf = "%PDF-1.4\n"
    offsets = [0]
    for obj in objects:
        offsets.append(len(pdf))
        pdf += obj + "\n"

    xref_offset = len(pdf)
    pdf += f"xref\n0 {len(objects) + 1}\n"
    pdf += "0000000000 65535 f \n"
    for offset in offsets[1:]:
        pdf += f"{offset:010d} 00000 n \n"
    pdf += f"trailer << /Root 1 0 R /Size {len(objects) + 1} >>\n"
    pdf += f"startxref\n{xref_offset}\n%%EOF\n"
    return pdf.encode("latin-1")


def _write_temp_pdf(content: bytes) -> Path:
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    tmp.write(content)
    tmp.flush()
    tmp.close()
    return Path(tmp.name)


def test_is_scanned_pdf_detects_text():
    pdf_path = _write_temp_pdf(_build_pdf_bytes("Hello World " * 10))

    try:
        assert pdf_extractor.is_scanned_pdf(str(pdf_path)) is False
    finally:
        pdf_path.unlink(missing_ok=True)


def test_is_scanned_pdf_detects_scanned():
    pdf_path = _write_temp_pdf(_build_pdf_bytes(""))

    try:
        assert pdf_extractor.is_scanned_pdf(str(pdf_path)) is True
    finally:
        pdf_path.unlink(missing_ok=True)


def test_extract_text_from_scanned(monkeypatch):
    def fake_convert(_path):
        return ["img1", "img2"]

    def fake_ocr(image, lang=None):
        return "page1" if image == "img1" else "page2"

    monkeypatch.setattr(pdf_extractor, "convert_from_path", fake_convert)
    monkeypatch.setattr(pdf_extractor.pytesseract, "image_to_string", fake_ocr)

    text = pdf_extractor.extract_text_from_scanned("dummy.pdf")

    assert text == "page1\npage2"


def test_extract_text_from_scanned_typeerror_fallback_respects_page_limit(monkeypatch):
    monkeypatch.setattr(pdf_extractor, "MAX_OCR_PAGES", 2)

    def fake_convert(path):
        assert path == "dummy.pdf"
        return ["img1", "img2", "img3"]

    def fake_ocr(image, lang=None):
        return f"text-{image}"

    monkeypatch.setattr(pdf_extractor, "convert_from_path", fake_convert)
    monkeypatch.setattr(pdf_extractor.pytesseract, "image_to_string", fake_ocr)

    text = pdf_extractor.extract_text_from_scanned("dummy.pdf")

    assert text == "text-img1\ntext-img2"


def test_extract_tables(monkeypatch):
    class FakeValues:
        def __init__(self, rows):
            self._rows = rows

        def tolist(self):
            return self._rows

    class FakeDF:
        def __init__(self, rows):
            self.values = FakeValues(rows)
            self.empty = False

    class FakeTable:
        def __init__(self, rows):
            self.df = FakeDF(rows)

    class FakeTables(list):
        @property
        def n(self):
            return len(self)

    def fake_read_pdf(_path, pages, flavor):
        if flavor == "lattice":
            return FakeTables([FakeTable([["Выручка", "1000"]])])
        return FakeTables([])

    monkeypatch.setattr(pdf_extractor.camelot, "read_pdf", fake_read_pdf)

    tables = pdf_extractor.extract_tables("dummy.pdf")

    assert tables
    assert tables[0]["rows"][0] == ["Выручка", "1000"]


def test_parse_financial_statements():
    tables = [
        {"rows": [["Выручка", "1000"], ["Чистая прибыль", "50"]]},
    ]
    # Use keyword that matches _METRIC_KEYWORDS for short_term_liabilities
    text = "Итого краткосрочных обязательств 200"

    metrics = pdf_extractor.parse_financial_statements(tables, text)

    assert metrics["revenue"] == 1000.0
    assert metrics["net_profit"] == 50.0
    assert metrics["short_term_liabilities"] == 200.0
    assert metrics["equity"] is None


def test_extract_number_near_keywords_does_not_merge_multiline_numbers():
    text = "итого обязательств 123 456\n789 012"

    value = pdf_extractor._extract_number_near_keywords(
        text,
        ["итого обязательств"],
    )

    assert value == 123456.0


def test_extract_section_total_uses_safe_keyword_window():
    text = "итого по разделу iv 361 751\n315"

    value = pdf_extractor._extract_section_total(
        [],
        text,
        ["итого по разделу iv"],
    )

    assert value == 361751.0
