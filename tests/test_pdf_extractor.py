from __future__ import annotations

import tempfile
import warnings
from pathlib import Path

from cryptography.utils import CryptographyDeprecationWarning
from src.analysis import pdf_extractor

warnings.filterwarnings(
    "ignore",
    message=r"ARC4 has been moved.*",
    category=CryptographyDeprecationWarning,
)


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


def test_extract_text_from_scanned_stops_early_on_financial_signal(monkeypatch):
    pages = [f"img{i}" for i in range(1, 8)]
    seen_pages: list[str] = []

    def fake_convert(path, first_page=None, last_page=None, poppler_path=None):
        assert path == "dummy.pdf"
        assert first_page == last_page
        index = first_page - 1
        if index >= len(pages):
            raise RuntimeError("done")
        return [pages[index]]

    def fake_ocr(image, lang=None):
        seen_pages.append(image)
        if image == "img1":
            return "Бухгалтерский баланс"
        if image == "img2":
            return "Отчет о финансовых результатах"
        if image == "img3":
            return "код 1600 435 659 511 код 1200 174 989 150"
        if image == "img4":
            return "код 1250 1 448 897 выручка 2110 103 015 чистая прибыль 2400 1 348 503"
        return f"noise-{image}"

    monkeypatch.setattr(pdf_extractor, "convert_from_path", fake_convert)
    monkeypatch.setattr(pdf_extractor.pytesseract, "image_to_string", fake_ocr)

    text = pdf_extractor.extract_text_from_scanned("dummy.pdf")

    assert "Бухгалтерский баланс" in text
    assert "Отчет о финансовых результатах" in text
    assert seen_pages == ["img1", "img2", "img3", "img4", "img5"]


def test_extract_layout_section_total_lines_from_ocr_layout(monkeypatch):
    fake_data = {
        "text": ["Итого", "по", "разделу", "Ш", "209", "475", "516", "foo"],
        "block_num": [1, 1, 1, 1, 2, 2, 2, 3],
        "par_num": [1, 1, 1, 1, 1, 1, 1, 1],
        "line_num": [1, 1, 1, 1, 1, 1, 1, 1],
        "top": [100, 100, 100, 100, 102, 102, 102, 160],
        "left": [10, 70, 100, 160, 600, 650, 700, 30],
    }

    def fake_image_to_data(_image, lang=None, output_type=None):
        return fake_data

    monkeypatch.setattr(pdf_extractor.pytesseract, "image_to_data", fake_image_to_data)

    lines = pdf_extractor._extract_layout_section_total_lines(object(), "Итого по разделу Ш")

    assert lines == ["Итого по разделу Ш 209 475 516"]


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


def test_extract_tables_prefers_stream_before_lattice(monkeypatch):
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

    calls: list[str] = []

    def fake_read_pdf(_path, pages, flavor):
        calls.append(flavor)
        if flavor == "stream":
            return FakeTables([FakeTable([["Выручка", "1000"], ["Итого активы", "2000"]])])
        return FakeTables([FakeTable([["Should not be reached", "1"]])])

    monkeypatch.setattr(pdf_extractor.camelot, "read_pdf", fake_read_pdf)

    tables = pdf_extractor.extract_tables("dummy.pdf")

    assert calls == ["stream"]
    assert tables[0]["flavor"] == "stream"


def test_extract_tables_keeps_statement_tables_when_many_tables_found(monkeypatch):
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

    narrative_row = [
        "Выручка по договорам с покупателями",
        "65",
        "Описание учетной политики и раскрытия информации",
    ]
    noisy_tables = [
        FakeTable([narrative_row for _ in range(40)])
        for _ in range(24)
    ]
    statement_table = FakeTable(
        [
            ["Выручка", "24", "2 351 996 423", "1 856 078 950"],
            ["Прибыль за год", "", "27 932 517", "48 118 154"],
            ["Итого активы", "", "1 395 998 440", "1 209 760 255"],
            ["Итого обязательства", "", "1 188 616 136", "1 030 762 784"],
        ]
    )

    def fake_read_pdf(_path, pages, flavor):
        if flavor == "stream":
            return FakeTables(noisy_tables + [statement_table])
        return FakeTables([])

    monkeypatch.setattr(pdf_extractor.camelot, "read_pdf", fake_read_pdf)

    tables = pdf_extractor.extract_tables("dummy.pdf")

    assert len(tables) == 10
    assert any(
        any("2 351 996 423" in str(cell) for cell in row)
        for table in tables
        for row in table["rows"]
    )


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


def test_normalize_number_supports_grouped_english_and_negative_values():
    assert pdf_extractor._normalize_number("1,296,745") == 1296745.0
    assert pdf_extractor._normalize_number("(183,949)") == -183949.0


def test_extract_preferred_numeric_match_skips_note_references():
    assert pdf_extractor._extract_preferred_numeric_match(" 24 2 351 996 423 1 856 078 950") == 2351996423.0
    assert pdf_extractor._extract_preferred_numeric_match(" 23 1 673 223 617 1 460 058 332") == 1673223617.0


def test_extract_value_near_text_codes_supports_scanned_russian_forms():
    text = (
        "Бухгалтерский баланс 1600 435 659 511 307 785 500\n"
        "Итого по разделу П 1200 174 989 150 141 877 788\n"
        "Выручка от реализации, без НДС (стр. 2110) 103 015 103 015\n"
        "Прибыль (убыток) (стр. 2300, 2400) "
        "Чистая прибыль Общества за отчетный период составила 1 348 503 тыс. руб.\n"
    )

    assert pdf_extractor._extract_value_near_text_codes(text, ("1600",), None) == 435659511.0
    assert pdf_extractor._extract_value_near_text_codes(
        text, ("2110",), ("выручка от реализации, без ндс", "выручка")
    ) == 103015.0
    assert pdf_extractor._extract_value_near_text_codes(
        text, ("2400",), ("чистая прибыль", "прибыль за период", "прибыль за год")
    ) == 1348503.0


def test_extract_preferred_ocr_numeric_match_supports_four_digit_group_prefix():
    assert pdf_extractor._extract_preferred_ocr_numeric_match("1348 503 1339 235") == 1348503.0


def test_extract_form_section_total_prefers_same_line_number():
    text = "\n".join(
        [
            "Итого по разделу Ш 209 475 516 208 127 013",
            "ТУ. ДОЛГОСРОЧНЫЕ ОБЯЗАТЕЛЬСТВА",
        ]
    )

    value = pdf_extractor._extract_form_section_total(
        text,
        ("итого по разделу ш", "итого по разделу iii"),
    )

    assert value == 209475516.0


def test_extract_form_section_total_supports_section_v_marker():
    text = "\n".join(
        [
            "Итого по разделу V 226 183 995 197 916 480",
            "Краткосрочные обязательства",
        ]
    )

    value = pdf_extractor._extract_form_section_total(
        text,
        ("итого по разделу v", "итого по разделу у"),
    )

    assert value == 226183995.0


def test_scanned_form_extracts_short_term_liabilities_from_section_v_total():
    text = "\n".join(
        [
            "Бухгалтерский баланс",
            "код 1600 435 659 511 307 785 500",
            "Итого по разделу V 226 183 995 197 916 480",
            "Итого по разделу Ш 209 475 516 208 127 013",
        ]
    )

    metadata = pdf_extractor.parse_financial_statements_with_metadata([], text)

    assert metadata["short_term_liabilities"].value == 226183995.0
    assert metadata["short_term_liabilities"].source == "text_regex"


def test_text_statement_row_overrides_partial_table_noise():
    tables = [
        {"rows": [["Revenue growth", "10,000"]]},
    ]
    text = "\n".join(
        [
            "CONSOLIDATED STATEMENTS OF OPERATIONS",
            "Revenues $718,562,000 $646,230,000 $552,644,000",
            "Net income $66,365,000 $66,410,000 $46,356,000",
            "Total stockholders' equity 202,176,000 212,395,000",
            "Total assets $ 393,923,000 $ 415,246,000",
            "Total liabilities 191,747,000 202,851,000",
            "Total current assets 243,770,000 264,994,000",
            "Total current liabilities 167,887,000 171,370,000",
        ]
    )

    metadata = pdf_extractor.parse_financial_statements_with_metadata(tables, text)

    assert metadata["revenue"].value == 718562000.0
    assert metadata["revenue"].source == "text_regex"
    assert metadata["net_profit"].value == 66365000.0
    assert metadata["equity"].value == 202176000.0


def test_russian_statement_rows_with_note_numbers_prefer_actual_values():
    tables = [
        {
            "rows": [
                ["Выручка", "24", "2 351 996 423", "1 856 078 950"],
                ["Прибыль за год", "", "27 932 517", "48 118 154"],
                ["Итого активы", "", "1 395 998 440", "1 209 760 255"],
                ["Итого обязательства", "", "1 188 616 136", "1 030 762 784"],
            ]
        }
    ]
    text = "\n".join(
        [
            "(в тысячах рублей)",
            "Выручка 24 2 351 996 423 1 856 078 950",
            "Прибыль за год 27 932 517 48 118 154",
            "Итого активы 1 395 998 440 1 209 760 255",
            "Итого обязательства 1 188 616 136 1 030 762 784",
        ]
    )

    metadata = pdf_extractor.parse_financial_statements_with_metadata(tables, text)

    assert metadata["revenue"].value == 2351996423000.0
    assert metadata["revenue"].source == "table_exact"
    assert metadata["net_profit"].value == 27932517000.0
    assert metadata["net_profit"].source == "table_exact"


def test_scanned_russian_multiline_statement_value_is_extracted():
    text = "\n".join(
        [
            "Отчет о финансовых результатах",
            "Выручка",
            "За январь - март",
            "2025 г.",
            "103 015",
            "Прибыль (убыток) от продаж",
            "129 258",
            "Чистая прибыль (убыток)",
            "Форма 0710002 с. 2",
            "Совокупный финансовый результат периода",
            "1 348 503",
        ]
    )

    metadata = pdf_extractor.parse_financial_statements_with_metadata([], text)

    assert metadata["revenue"].value == 103015.0
    assert metadata["net_profit"].value == 1348503.0
