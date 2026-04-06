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
            return (
                "код 1250 1 448 897 выручка 2110 103 015 чистая прибыль 2400 1 348 503"
            )
        if image == "img5":
            return "код 1400 33 723 849 код 1500 192 460 146"
        return f"noise-{image}"

    monkeypatch.setattr(pdf_extractor, "convert_from_path", fake_convert)
    monkeypatch.setattr(pdf_extractor.pytesseract, "image_to_string", fake_ocr)

    text = pdf_extractor.extract_text_from_scanned("dummy.pdf")

    assert "Бухгалтерский баланс" in text
    assert "Отчет о финансовых результатах" in text
    assert seen_pages == ["img1", "img2", "img3", "img4", "img5"]


def test_extract_text_from_scanned_does_not_stop_before_liabilities_signal(monkeypatch):
    pages = [f"img{i}" for i in range(1, 9)]
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
            return (
                "код 1250 1 448 897 выручка 2110 103 015 чистая прибыль 2400 1 348 503"
            )
        if image == "img6":
            return "код 1500 226 183 995"
        if image == "img7":
            return "код 1400 33 723 849"
        return f"noise-{image}"

    monkeypatch.setattr(pdf_extractor, "convert_from_path", fake_convert)
    monkeypatch.setattr(pdf_extractor.pytesseract, "image_to_string", fake_ocr)

    _ = pdf_extractor.extract_text_from_scanned("dummy.pdf")

    assert seen_pages == ["img1", "img2", "img3", "img4", "img5", "img6", "img7"]


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

    lines = pdf_extractor._extract_layout_section_total_lines(
        object(), "Итого по разделу Ш"
    )

    assert lines == ["Итого по разделу Ш 209 475 516"]


def test_extract_layout_metric_value_lines_recovers_inventory(monkeypatch):
    class FakeImage:
        size = (1653, 2339)

        def crop(self, _box):
            return self

    fake_data = {
        "text": ["Бухгалтерский", "баланс", "Запасы"],
        "block_num": [1, 1, 2],
        "par_num": [1, 1, 1],
        "line_num": [1, 1, 1],
        "top": [120, 120, 1044],
        "left": [100, 220, 292],
        "width": [90, 80, 61],
        "height": [20, 20, 14],
    }

    def fake_image_to_data(_image, lang=None, output_type=None):
        return fake_data

    def fake_image_to_string(_image, lang=None, config=None):
        assert "whitelist" in (config or "")
        return "1210 21 42 153"

    monkeypatch.setattr(pdf_extractor.pytesseract, "image_to_data", fake_image_to_data)
    monkeypatch.setattr(
        pdf_extractor.pytesseract, "image_to_string", fake_image_to_string
    )

    lines = pdf_extractor._extract_layout_metric_value_lines(
        FakeImage(),
        "Бухгалтерский баланс\nЗапасы",
    )

    assert lines == ["Запасы 21 42 153"]


def test_extract_layout_metric_value_lines_supports_balance_code_set(monkeypatch):
    class FakeImage:
        size = (1653, 2339)

    fake_data = {
        "text": [
            "Бухгалтерский",
            "баланс",
            "Итого",
            "по",
            "разделу",
            "П",
            "Запасы",
            "Дебиторская",
            "задолженность",
            "Денежные",
            "средства",
            "Итого",
            "по",
            "разделу",
            "IV",
            "1400",
            "Итого",
            "по",
            "разделу",
            "V",
            "1500",
        ],
        "block_num": [
            1,
            1,
            2,
            2,
            2,
            2,
            3,
            4,
            4,
            5,
            5,
            6,
            6,
            6,
            6,
            6,
            7,
            7,
            7,
            7,
            7,
        ],
        "par_num": [
            1,
            1,
            1,
            1,
            1,
            1,
            1,
            1,
            1,
            1,
            1,
            1,
            1,
            1,
            1,
            1,
            1,
            1,
            1,
            1,
            1,
        ],
        "line_num": [
            1,
            1,
            1,
            1,
            1,
            1,
            1,
            1,
            1,
            1,
            1,
            1,
            1,
            1,
            1,
            1,
            1,
            1,
            1,
            1,
            1,
        ],
        "top": [
            120,
            120,
            220,
            220,
            220,
            220,
            260,
            300,
            300,
            340,
            340,
            380,
            380,
            380,
            380,
            380,
            420,
            420,
            420,
            420,
            420,
        ],
        "left": [
            80,
            190,
            100,
            150,
            190,
            250,
            100,
            100,
            180,
            100,
            180,
            100,
            150,
            190,
            250,
            320,
            100,
            150,
            190,
            250,
            320,
        ],
        "width": [
            90,
            90,
            40,
            30,
            70,
            20,
            80,
            80,
            130,
            80,
            90,
            40,
            30,
            70,
            30,
            40,
            40,
            30,
            70,
            20,
            40,
        ],
        "height": [
            20,
            20,
            18,
            18,
            18,
            18,
            18,
            18,
            18,
            18,
            18,
            18,
            18,
            18,
            18,
            18,
            18,
            18,
            18,
            18,
            18,
        ],
    }

    def fake_image_to_data(_image, lang=None, output_type=None):
        return fake_data

    code_to_tail = {
        "1200": "174 989 150",
        "1210": "21 42 153",
        "1230": "26 998 240",
        "1250": "1 448 897",
        "1400": "33 723 849",
        "1500": "192 460 146",
    }

    def fake_extract_tail(
        _image,
        row_left,
        row_top,
        row_right,
        row_bottom,
        expected_code=None,
        require_code_match=False,
    ):
        return code_to_tail.get(expected_code)

    monkeypatch.setattr(pdf_extractor.pytesseract, "image_to_data", fake_image_to_data)
    monkeypatch.setattr(
        pdf_extractor,
        "_extract_ocr_row_value_tail",
        fake_extract_tail,
    )

    lines = pdf_extractor._extract_layout_metric_value_lines(
        FakeImage(),
        "Бухгалтерский баланс",
    )

    assert set(lines) == {
        "Итого по разделу П 174 989 150",
        "Запасы 21 42 153",
        "Дебиторская задолженность 26 998 240",
        "Денежные средства 1 448 897",
        "Итого по разделу IV 33 723 849",
        "Итого по разделу V 192 460 146",
    }


def test_extract_layout_metric_value_lines_skips_short_section_noise(monkeypatch):
    class FakeImage:
        size = (1653, 2339)

    fake_data = {
        "text": ["Бухгалтерский", "баланс", "Итого", "по", "разделу", "V"],
        "block_num": [1, 1, 2, 2, 2, 2],
        "par_num": [1, 1, 1, 1, 1, 1],
        "line_num": [1, 1, 1, 1, 1, 1],
        "top": [120, 120, 320, 320, 320, 320],
        "left": [80, 180, 100, 150, 190, 250],
        "width": [90, 90, 40, 30, 70, 20],
        "height": [20, 20, 18, 18, 18, 18],
    }

    def fake_image_to_data(_image, lang=None, output_type=None):
        return fake_data

    def fake_extract_tail(
        _image,
        row_left,
        row_top,
        row_right,
        row_bottom,
        expected_code=None,
        require_code_match=False,
    ):
        assert expected_code == "1500"
        assert require_code_match is True
        return "8 609"

    monkeypatch.setattr(pdf_extractor.pytesseract, "image_to_data", fake_image_to_data)
    monkeypatch.setattr(pdf_extractor, "_extract_ocr_row_value_tail", fake_extract_tail)

    lines = pdf_extractor._extract_layout_metric_value_lines(
        FakeImage(),
        "Бухгалтерский баланс",
    )

    assert lines == []


def test_should_run_layout_metric_row_crop_uses_balance_signal():
    assert (
        pdf_extractor._should_run_layout_metric_row_crop("Произвольный текст отчета")
        is False
    )
    assert (
        pdf_extractor._should_run_layout_metric_row_crop(
            "Бухгалтерский баланс\nкод 1210 21 42 153"
        )
        is True
    )


def test_extract_layout_metric_value_lines_limits_row_crop_attempts_per_spec(
    monkeypatch,
):
    class FakeImage:
        size = (1653, 2339)

    fake_data = {
        "text": [
            "Бухгалтерский",
            "баланс",
            "Запасы",
            "Запасы",
            "Запасы",
            "Запасы",
            "Запасы",
        ],
        "block_num": [1, 1, 2, 3, 4, 5, 6],
        "par_num": [1, 1, 1, 1, 1, 1, 1],
        "line_num": [1, 1, 1, 1, 1, 1, 1],
        "top": [120, 120, 220, 260, 300, 340, 380],
        "left": [80, 180, 100, 100, 100, 100, 100],
        "width": [90, 90, 80, 80, 80, 80, 80],
        "height": [20, 20, 18, 18, 18, 18, 18],
    }

    attempts = {"count": 0}

    def fake_image_to_data(_image, lang=None, output_type=None):
        return fake_data

    def fake_extract_tail(
        _image,
        row_left,
        row_top,
        row_right,
        row_bottom,
        expected_code=None,
        require_code_match=False,
    ):
        attempts["count"] += 1
        return None

    monkeypatch.setattr(pdf_extractor.pytesseract, "image_to_data", fake_image_to_data)
    monkeypatch.setattr(pdf_extractor, "_extract_ocr_row_value_tail", fake_extract_tail)

    lines = pdf_extractor._extract_layout_metric_value_lines(
        FakeImage(),
        "Бухгалтерский баланс\nЗапасы",
    )

    assert lines == []
    assert attempts["count"] == 4


def test_extract_layout_metric_value_lines_extracts_value_after_second_candidate(
    monkeypatch,
):
    class FakeImage:
        size = (1653, 2339)

    fake_data = {
        "text": ["Бухгалтерский", "баланс", "Запасы", "Запасы", "Запасы", "Запасы"],
        "block_num": [1, 1, 2, 3, 4, 5],
        "par_num": [1, 1, 1, 1, 1, 1],
        "line_num": [1, 1, 1, 1, 1, 1],
        "top": [120, 120, 220, 260, 300, 340],
        "left": [80, 180, 100, 100, 100, 100],
        "width": [90, 90, 80, 80, 80, 80],
        "height": [20, 20, 18, 18, 18, 18],
    }

    attempts = {"count": 0}

    def fake_image_to_data(_image, lang=None, output_type=None):
        return fake_data

    def fake_extract_tail(
        _image,
        row_left,
        row_top,
        row_right,
        row_bottom,
        expected_code=None,
        require_code_match=False,
    ):
        attempts["count"] += 1
        if attempts["count"] < 3:
            return None
        return "21 42 153"

    monkeypatch.setattr(pdf_extractor.pytesseract, "image_to_data", fake_image_to_data)
    monkeypatch.setattr(pdf_extractor, "_extract_ocr_row_value_tail", fake_extract_tail)

    lines = pdf_extractor._extract_layout_metric_value_lines(
        FakeImage(),
        "Бухгалтерский баланс\nЗапасы",
    )

    assert lines == ["Запасы 21 42 153"]
    assert attempts["count"] == 3


def test_extract_layout_metric_value_lines_applies_page_level_attempt_budget(
    monkeypatch,
):
    class FakeImage:
        size = (1653, 2339)

    marker_rows = [
        "m1",
        "m1",
        "m1",
        "m1",
        "m1",
        "m2",
        "m2",
        "m2",
        "m2",
        "m2",
        "m3",
        "m3",
        "m3",
        "m3",
        "m3",
        "m4",
        "m4",
        "m4",
        "m4",
        "m4",
    ]
    texts = ["Бухгалтерский", "баланс", *marker_rows]
    fake_data = {
        "text": texts,
        "block_num": [1, 1, *range(2, 2 + len(marker_rows))],
        "par_num": [1] * len(texts),
        "line_num": [1] * len(texts),
        "top": [120, 120, *[200 + idx * 20 for idx in range(len(marker_rows))]],
        "left": [80, 180, *([100] * len(marker_rows))],
        "width": [90, 90, *([80] * len(marker_rows))],
        "height": [20, 20, *([18] * len(marker_rows))],
    }

    attempts = {"count": 0}

    def fake_image_to_data(_image, lang=None, output_type=None):
        return fake_data

    def fake_extract_tail(
        _image,
        row_left,
        row_top,
        row_right,
        row_bottom,
        expected_code=None,
        require_code_match=False,
    ):
        attempts["count"] += 1
        return None

    monkeypatch.setattr(
        pdf_extractor,
        "_LAYOUT_BALANCE_ROW_SPECS",
        (
            ("code1", ("m1",), "L1", 2, False),
            ("code2", ("m2",), "L2", 2, False),
            ("code3", ("m3",), "L3", 2, False),
            ("code4", ("m4",), "L4", 2, False),
        ),
    )
    monkeypatch.setattr(pdf_extractor.pytesseract, "image_to_data", fake_image_to_data)
    monkeypatch.setattr(pdf_extractor, "_extract_ocr_row_value_tail", fake_extract_tail)

    lines = pdf_extractor._extract_layout_metric_value_lines(
        FakeImage(),
        "Бухгалтерский баланс",
    )

    assert lines == []
    assert attempts["count"] == 14


def test_extract_text_from_scanned_runs_layout_row_crop_only_for_signal_pages(
    monkeypatch,
):
    def fake_convert(path, first_page=None, last_page=None, poppler_path=None):
        assert path == "dummy.pdf"
        if first_page == 1 and last_page == 1:
            return ["img1"]
        if first_page == 2 and last_page == 2:
            return ["img2"]
        raise RuntimeError("done")

    def fake_ocr(image, lang=None):
        if image == "img1":
            return "Narrative page without balance signal"
        return "Бухгалтерский баланс\nЗапасы"

    calls = {"count": 0}

    def fake_layout_metric(_image, _page_text):
        calls["count"] += 1
        return []

    monkeypatch.setattr(pdf_extractor, "convert_from_path", fake_convert)
    monkeypatch.setattr(pdf_extractor.pytesseract, "image_to_string", fake_ocr)
    monkeypatch.setattr(
        pdf_extractor,
        "_extract_layout_section_total_lines",
        lambda *_args, **_kwargs: [],
    )
    monkeypatch.setattr(
        pdf_extractor, "_extract_layout_metric_value_lines", fake_layout_metric
    )
    monkeypatch.setattr(
        pdf_extractor, "_should_stop_scanned_ocr", lambda *_args, **_kwargs: False
    )

    text = pdf_extractor.extract_text_from_scanned("dummy.pdf")

    assert "Narrative page without balance signal" in text
    assert "Бухгалтерский баланс" in text
    assert calls["count"] == 1


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
            return FakeTables(
                [FakeTable([["Выручка", "1000"], ["Итого активы", "2000"]])]
            )
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
    noisy_tables = [FakeTable([narrative_row for _ in range(40)]) for _ in range(24)]
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


def test_extract_tables_falls_back_to_non_recursive_ocr_adapter(monkeypatch):
    class FakeTables(list):
        @property
        def n(self):
            return len(self)

    calls: list[tuple[str, object | None, object | None]] = []

    def fake_read_pdf(_path, pages, flavor):
        calls.append(("camelot", flavor, None))
        return FakeTables([])

    def fake_convert(path, first_page=None, last_page=None, poppler_path=None):
        assert path == "dummy.pdf"
        calls.append(("convert", first_page, last_page))
        if first_page == 1 and last_page == 1:
            return ["img1"]
        return []

    def fake_ocr(image, lang=None):
        calls.append(("ocr", image, lang))
        return "Бухгалтерский баланс"

    monkeypatch.setattr(pdf_extractor.camelot, "read_pdf", fake_read_pdf)
    monkeypatch.setattr(pdf_extractor, "convert_from_path", fake_convert)
    monkeypatch.setattr(pdf_extractor.pytesseract, "image_to_string", fake_ocr)

    tables = pdf_extractor.extract_tables("dummy.pdf")

    assert calls[:2] == [("camelot", "stream", None), ("camelot", "lattice", None)]
    assert ("convert", 1, 1) in calls
    assert ("ocr", "img1", "rus+eng") in calls
    assert tables == [{"flavor": "ocr", "rows": [["OCR_TEXT", "Бухгалтерский баланс"]]}]


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
    assert (
        pdf_extractor._extract_preferred_numeric_match(
            " 24 2 351 996 423 1 856 078 950"
        )
        == 2351996423.0
    )
    assert (
        pdf_extractor._extract_preferred_numeric_match(
            " 23 1 673 223 617 1 460 058 332"
        )
        == 1673223617.0
    )


def test_extract_value_near_text_codes_supports_scanned_russian_forms():
    text = (
        "Бухгалтерский баланс 1600 435 659 511 307 785 500\n"
        "Итого по разделу П 1200 174 989 150 141 877 788\n"
        "Выручка от реализации, без НДС (стр. 2110) 103 015 103 015\n"
        "Прибыль (убыток) (стр. 2300, 2400) "
        "Чистая прибыль Общества за отчетный период составила 1 348 503 тыс. руб.\n"
    )

    assert (
        pdf_extractor._extract_value_near_text_codes(text, ("1600",), None)
        == 435659511.0
    )
    assert (
        pdf_extractor._extract_value_near_text_codes(
            text, ("2110",), ("выручка от реализации, без ндс", "выручка")
        )
        == 103015.0
    )
    assert (
        pdf_extractor._extract_value_near_text_codes(
            text, ("2400",), ("чистая прибыль", "прибыль за период", "прибыль за год")
        )
        == 1348503.0
    )


def test_extract_value_near_text_codes_prefers_same_line_cash_over_later_note_section():
    text = "\n".join(
        [
            "п.12.1.6 Денежные средства и денежные эквиваленты 1250 1448 897 216 2601771",
            "Итого по разделу П 1200 174 989 150 141 877 788 138 420 826",
            "Денежные средства 199290299 7",
        ]
    )

    assert (
        pdf_extractor._extract_value_near_text_codes(
            text,
            ("1250",),
            ("денежные средства", "cash and cash equivalents"),
        )
        == 1448897.0
    )


def test_extract_value_near_text_codes_ignores_note_heading_without_same_line_value():
    text = "\n".join(
        [
            "12.1.5. Дебиторская задолженность (стр. 1230)",
            "Дебиторская задолженность представлена в таблице 7.1 Пояснений",
            "В обороты по процентам к получению включена дебиторская задолженность",
        ]
    )

    assert (
        pdf_extractor._extract_value_near_text_codes(
            text,
            ("1230",),
            ("дебиторская задолженность", "accounts receivable", "trade receivables"),
        )
        is None
    )


def test_extract_preferred_ocr_numeric_match_supports_four_digit_group_prefix():
    assert (
        pdf_extractor._extract_preferred_ocr_numeric_match("1348 503 1339 235")
        == 1348503.0
    )


def test_extract_preferred_ocr_numeric_match_skips_four_digit_row_code_artifact():
    assert (
        pdf_extractor._extract_preferred_ocr_numeric_match(
            "3211 - - - - - 1339 235 1339 235"
        )
        == 1339235.0
    )


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


def test_extract_form_long_term_liabilities_prefers_smaller_candidate_on_conflict():
    text = "\n".join(
        [
            "Итого по разделу IV 226 183 995 197 916 480",
            "код 1400 33 723 849 43 960 253",
        ]
    )

    value = pdf_extractor._extract_form_long_term_liabilities(
        text,
        short_term_value=192460146.0,
    )

    assert value == 33723849.0


def test_extract_form_long_term_liabilities_keeps_near_short_term_values():
    text = "\n".join(
        [
            "Итого по разделу IV 50 005 49 000",
            "Краткосрочные обязательства",
        ]
    )

    value = pdf_extractor._extract_form_long_term_liabilities(
        text,
        short_term_value=50000.0,
    )

    assert value == 50005.0


def test_scanned_note_column_codes_do_not_override_section_totals():
    text = "\n".join(
        [
            "Бухгалтерский баланс",
            "КАПИТАЛ И РЕЗЕРВЫ",
            "Уставный капитал",
            "2025",
            "7",
            "Итого по разделу Ш 209 475 516 208 127 013",
            "КРАТКОСРОЧНЫЕ ОБЯЗАТЕЛЬСТВА",
            "5",
            "Итого по разделу V 192 460 146 153 956 227",
            "код 1600 435 659 511 307 785 500",
        ]
    )

    metadata = pdf_extractor.parse_financial_statements_with_metadata([], text)

    assert metadata["equity"].value == 209475516.0
    assert metadata["short_term_liabilities"].value == 192460146.0
    assert metadata["liabilities"].value == 226183995.0


def test_ifrs_table_note_numbers_do_not_become_total_metrics():
    tables = [
        {
            "rows": [
                ["Гудвил", "11", "67 029 310", "92 541 134"],
                ["Долгосрочная дебиторская задолженность", "14", "353 774", "–"],
                ["Авансы выданные", "15", "12 728 588", "9 198 907"],
                ["Итого активы", "", "1 395 998 440", "1 209 760 255"],
                ["Итого обязательства", "", "1 188 616 136", "1 030 762 784"],
            ]
        }
    ]

    metadata = pdf_extractor.parse_financial_statements_with_metadata(tables, "")

    assert metadata["total_assets"].value == 1395998440.0
    assert metadata["liabilities"].value == 1188616136.0
    assert metadata["equity"].value is None


def test_extract_best_line_value_prefers_statement_row_over_title_page_number():
    text = "\n".join(
        [
            "Consolidated Statements of Stockholders' Equity 98",
            "Stockholders' Equity",
            "Total stockholders' equity 763,047 623,964",
        ]
    )

    value, quality = pdf_extractor._extract_best_line_value(
        text,
        pdf_extractor._METRIC_KEYWORDS["equity"],
        metric_key="equity",
    )

    assert value == 763047.0
    assert quality is not None


def test_parse_text_prefers_curly_apostrophe_equity_row_over_ascii_title_number():
    text = "\n".join(
        [
            "Consolidated Statements of Stockholders' Equity 98",
            "Stockholders’ Equity",
            "Total stockholders’ equity 763,047 623,964",
        ]
    )

    metadata = pdf_extractor.parse_financial_statements_with_metadata([], text)

    assert metadata["equity"].value == 763047.0


def test_extract_best_line_value_prefers_more_specific_cash_keyword_match():
    text = "\n".join(
        [
            "Cash, cash equivalents, and restricted cash, end of period $ 91,224 $ 215,204 $ 320,958",
            "Cash and cash equivalents $ 86,864 $ 204,178",
        ]
    )

    value, quality = pdf_extractor._extract_best_line_value(
        text,
        pdf_extractor._METRIC_KEYWORDS["cash_and_equivalents"],
        metric_key="cash_and_equivalents",
    )

    assert value == 86864.0
    assert quality is not None


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
    assert metadata["short_term_liabilities"].source == "text"


def test_scanned_balance_header_without_codes_still_runs_section_path():
    text = "\n".join(
        [
            "Бухгалтерский баланс",
            "Итого по разделу III 100 000 97 000",
            "Итого по разделу IV 50 005 49 000",
            "Итого по разделу V 50 000 48 000",
        ]
    )

    metadata = pdf_extractor.parse_financial_statements_with_metadata([], text)

    assert metadata["short_term_liabilities"].value == 50000.0
    assert metadata["equity"].value == 100000.0
    assert metadata["liabilities"].value == 100005.0


def test_form_text_code_1400_is_treated_as_long_term_component():
    text = "\n".join(
        [
            "Бухгалтерский баланс",
            "код 1600 435 659 511 307 785 500",
            "код 1400 33 723 849 43 960 253",
            "код 1500 192 460 146 153 956 227",
        ]
    )

    metadata = pdf_extractor.parse_financial_statements_with_metadata([], text)

    assert metadata["liabilities"].value == 226183995.0
    assert metadata["short_term_liabilities"].value == 192460146.0


def test_form_liabilities_derived_from_components_has_strong_confidence():
    text = "\n".join(
        [
            "Бухгалтерский баланс",
            "код 1600 435 659 511 307 785 500",
            "код 1400 33 723 849 43 960 253",
            "код 1500 192 460 146 153 956 227",
        ]
    )

    metadata = pdf_extractor.parse_financial_statements_with_metadata([], text)

    assert metadata["liabilities"].value == 226183995.0
    assert metadata["liabilities"].source == "derived"
    assert metadata["liabilities"].confidence == 0.29


def test_tables_and_text_can_derive_short_term_liabilities_from_section_iv_total():
    tables = [{"flavor": "lattice", "rows": [["Итого обязательств", "1 000 000"]]}]
    text = "\n".join(
        [
            "Бухгалтерский баланс",
            "Итого по разделу IV 361 751",
        ]
    )

    metadata = pdf_extractor.parse_financial_statements_with_metadata(tables, text)

    assert metadata["liabilities"].value == 1000000.0
    assert metadata["short_term_liabilities"].value == 638249.0


def test_parse_text_prefers_total_liabilities_row_over_lease_component():
    text = "\n".join(
        [
            "Долгосрочные и краткосрочные обязательства по аренде (Прим. 9) 15 422",
            "Итого обязательства 1 188 616 136 1 030 762 784",
        ]
    )

    metadata = pdf_extractor.parse_financial_statements_with_metadata([], text)

    assert metadata["liabilities"].value == 1188616136.0


def test_section_based_liabilities_derive_falls_back_when_components_conflict():
    text = "\n".join(
        [
            "Бухгалтерский баланс",
            "код 1600 435 659 511 307 785 500",
            "Итого по разделу Ш 209 475 516 208 127 013",
            "Итого по разделу IV 226 183 995 197 916 480",
            "Итого по разделу V 192 460 146 153 956 227",
        ]
    )

    metadata = pdf_extractor.parse_financial_statements_with_metadata([], text)

    assert metadata["liabilities"].value == 226183995.0


def test_derive_liabilities_from_components_allows_high_leverage():
    derived = pdf_extractor._derive_liabilities_from_components(
        long_term=980.0,
        short_term=10.0,
        total_assets=1000.0,
        equity=10.0,
    )

    assert derived == 990.0


def test_form_like_guardrails_soft_null_liabilities_above_total_assets():
    tables = [
        {
            "rows": [
                ["Итого активов", "100 000"],
                ["Итого обязательств", "120 000"],
                ["Итого краткосрочных обязательств", "80 000"],
            ]
        }
    ]
    text = "Бухгалтерский баланс\nФорма 0710001"

    metadata = pdf_extractor.parse_financial_statements_with_metadata(tables, text)

    assert metadata["total_assets"].value == 100000.0
    assert metadata["liabilities"].value is None
    assert metadata["short_term_liabilities"].value == 80000.0


def test_form_like_guardrails_soft_null_short_term_above_total_assets():
    text = "\n".join(
        [
            "Бухгалтерский баланс",
            "код 1600 100 000 90 000",
            "Итого по разделу V 120 000 110 000",
        ]
    )

    metadata = pdf_extractor.parse_financial_statements_with_metadata([], text)

    assert metadata["total_assets"].value == 100000.0
    assert metadata["liabilities"].value is None
    assert metadata["short_term_liabilities"].value is None


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
    assert metadata["revenue"].source == "text"
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
    assert metadata["revenue"].source == "table"
    assert metadata["net_profit"].value == 27932517000.0
    assert metadata["net_profit"].source == "table"


def test_scanned_russian_multiline_statement_value_avoids_comprehensive_income_substitution():
    text = "\n".join(
        [
            "Отчет о финансовых результатах",
            "Выручка",
            "За январь - март",
            "2025 г.",
            "103 015",
            "Прибыль (убыток) от продаж",
            "129 258",
            "Форма 0710002 с. 2",
            "Совокупный финансовый результат периода",
            "1 348 503",
        ]
    )

    metadata = pdf_extractor.parse_financial_statements_with_metadata([], text)

    assert metadata["revenue"].value == 103015.0
    assert metadata["net_profit"].value is None


def test_scanned_russian_multiline_statement_uses_comprehensive_when_direct_signal_exists():
    text = "\n".join(
        [
            "Отчет о финансовых результатах",
            "Выручка",
            "За январь - март",
            "2025 г.",
            "103 015",
            "Чистая прибыль (убыток)",
            "Форма 0710002 с. 2",
            "Совокупный финансовый результат периода",
            "1 348 503",
            "1 339 235",
        ]
    )

    metadata = pdf_extractor.parse_financial_statements_with_metadata([], text)

    assert metadata["revenue"].value == 103015.0
    assert metadata["net_profit"].value == 1348503.0


def test_scanned_form_pnl_code_pair_is_preferred_for_revenue_and_net_profit():
    text = "\n".join(
        [
            "Отчет о финансовых результатах",
            "Выручка от реализации, без НДС (стр. 2110) 1 030 150",
            "Чистая прибыль (стр. 2400) 134 850",
            "Совокупный финансовый результат периода",
            "1 348 503",
        ]
    )

    metadata = pdf_extractor.parse_financial_statements_with_metadata([], text)

    assert metadata["revenue"].value == 1030150.0
    assert metadata["net_profit"].value == 134850.0


def test_scanned_russian_same_line_receivables_is_extracted():
    text = "\n".join(
        [
            "Бухгалтерский баланс",
            "Запасы",
            "Дебиторская задолженность 26 998 240 18 602 153 105 529 995",
            "Итого по разделу П 1200 174 989 150 141 877 788 138 420 826",
        ]
    )

    metadata = pdf_extractor.parse_financial_statements_with_metadata([], text)

    assert metadata["accounts_receivable"].value == 26998240.0
    assert metadata["accounts_receivable"].source == "text"
    assert metadata["inventory"].value is None


def test_scanned_magnit_q1_ocr_fragment_prefers_statement_rows_over_note_noise():
    text = "\n".join(
        [
            "Бухгалтерский баланс",
            "Единица измерения: тыс. руб.",
            "П. ОБОРОТНЫЕ АКТИВЫ",
            "Запасы",
            "Дебиторская задолженность 26 998 240 18 602 153 105 529 995",
            "п.12.1.6 Денежные средства и денежные эквиваленты 1250 1448 897 216 2601771",
            "Итого по разделу П 1200 174 989 150 141 877 788 138 420 826",
            "БАЛАНС 1600 435 659 511 307 785 500 299 128 606",
            "Запасы 21 42 153",
            "Денежные средства 199290299 7",
            "Итого по разделу Ш 209 475 516 208 127 013 186 349 571",
            "Итого по разделу V 192 460 146 73 567 578 50 070 703",
            "12.1.5. Дебиторская задолженность (стр. 1230)",
            "Дебиторская задолженность представлена в таблице 7.1 Пояснений",
            "12.1.6. Денежные средства и денежные эквиваленты (стр. 1250)",
            "По состоянию на 31 марта 2025 г. денежные средства и денежные эквиваленты включают:",
            "Денежные средства в рублях на счетах в банках 1448 1416 1771",
            "Денежные эквиваленты (депозиты) - 895 800 2600 000",
            "12.2. Отчет о финансовых результатах",
            "12.2.1. Доходы и расходы по обычным видам деятельности (стр. 2110, 2120, 2100)",
            "Выручка от реализации, в том числе НДС 123 618 123 618",
            "Выручка от реализации, без НДС (стр. 2110) 103 015 103 015",
            "12.2.4. Прибыль (убыток) (стр. 2300, 2400)",
            "Чистая прибыль Общества за отчетный период составила 1 348 503 тыс. руб.",
            "Чистая прибыль, тыс. руб. 2400 1348 503 1 339 235",
        ]
    )

    metadata = pdf_extractor.parse_financial_statements_with_metadata([], text)

    assert metadata["revenue"].value == 103015000.0
    assert metadata["net_profit"].value == 1348503000.0
    assert metadata["total_assets"].value == 435659511000.0
    assert metadata["current_assets"].value == 174989150000.0
    assert metadata["equity"].value == 209475516000.0
    assert metadata["liabilities"].value == 226183995000.0
    assert metadata["short_term_liabilities"].value == 192460146000.0
    assert metadata["accounts_receivable"].value == 26998240000.0
    assert metadata["inventory"].value == 2142153000.0
    assert metadata["cash_and_equivalents"].value == 1448897000.0


def test_magnit_h1_extracts_borrowings_and_lease_liabilities_as_separate_components():
    text = "\n".join(
        [
            "Консолидированная финансовая отчетность ПАО Магнит",
            "в миллионах рублей",
            "Долгосрочные кредиты и займы 220 922 260 868",
            "Краткосрочные кредиты и займы 281 924 221 554",
            "Долгосрочные обязательства по аренде 431 637 445 907",
            "Краткосрочные обязательства по аренде 211 182 190 091",
            "Итого обязательства 1 486 024 1 388 187",
        ]
    )

    metadata = pdf_extractor.parse_financial_statements_with_metadata([], text)

    assert metadata["long_term_borrowings"].value == 220922000000.0
    assert metadata["short_term_borrowings"].value == 281924000000.0
    assert metadata["long_term_lease_liabilities"].value == 431637000000.0
    assert metadata["short_term_lease_liabilities"].value == 211182000000.0
    assert metadata["liabilities"].value == 1486024000000.0


def test_magnit_h1_prefers_true_ebitda_over_pre_tax_profit_row():
    text = "\n".join(
        [
            "Консолидированная финансовая отчетность ПАО Магнит",
            "в миллионах рублей",
            "EBITDA 85 628 75 981",
            "Финансовые расходы 29 095 21 736",
            "Прибыль до налогообложения 1 846 23 470",
            "Чистая прибыль за период 6 544 17 008",
        ]
    )

    metadata = pdf_extractor.parse_financial_statements_with_metadata([], text)

    assert metadata["ebitda"].value == 85628000000.0
    assert metadata["interest_expense"].value == 29095000000.0
    assert metadata["net_profit"].value == 6544000000.0


def test_current_assets_rejects_component_rows_and_uses_total_line():
    tables = [
        {
            "rows": [
                ["Прочие внеоборотные активы", "400 000"],
                ["Итого оборотных активов", "120 000"],
            ]
        }
    ]

    metadata = pdf_extractor.parse_financial_statements_with_metadata(tables, "")

    assert metadata["current_assets"].value == 120000.0


def test_accounts_receivable_excludes_long_term_and_prefers_trade_receivables():
    tables = [
        {
            "rows": [
                ["Долгосрочная дебиторская задолженность", "50 000"],
                ["Торговая и прочая дебиторская задолженность", "120 000"],
            ]
        }
    ]

    metadata = pdf_extractor.parse_financial_statements_with_metadata(tables, "")

    assert metadata["accounts_receivable"].value == 120000.0


def test_short_term_liabilities_strict_null_when_only_component_row_present():
    tables = [
        {
            "rows": [
                ["Краткосрочные обязательства по аренде", "70 000"],
            ]
        }
    ]

    metadata = pdf_extractor.parse_financial_statements_with_metadata(tables, "")

    assert metadata["short_term_liabilities"].value is None


def test_short_term_liabilities_accepts_nominative_total_label():
    tables = [
        {
            "rows": [
                ["Итого краткосрочные обязательства", "120 000"],
            ]
        }
    ]

    metadata = pdf_extractor.parse_financial_statements_with_metadata(tables, "")

    assert metadata["short_term_liabilities"].value == 120000.0


def test_ifrs_section_heading_unlabeled_totals_are_inferred():
    tables = [
        {
            "rows": [
                ["Оборотные активы", "", "", ""],
                ["Запасы", "12", "302 102 443", "270 417 243"],
                [
                    "Торговая и прочая дебиторская задолженность",
                    "13",
                    "20 060 895",
                    "21 000 746",
                ],
                ["", "", "533 367 626", "523 471 409"],
                ["Итого активы", "", "1 670 048 135", "1 563 913 815"],
                ["Краткосрочные обязательства", "", "", ""],
                [
                    "Краткосрочные обязательства по аренде",
                    "8",
                    "60 914 519",
                    "62 192 392",
                ],
                ["", "", "670 066 479", "731 132 037"],
                ["Итого обязательства", "", "1 486 023 626", "1 382 600 197"],
            ]
        }
    ]

    metadata = pdf_extractor.parse_financial_statements_with_metadata(tables, "")

    assert metadata["current_assets"].value == 533367626.0
    assert metadata["short_term_liabilities"].value == 670066479.0


def test_current_assets_guardrail_nulls_invalid_total_and_derives_from_components():
    tables = [
        {
            "rows": [
                ["Итого оборотных активов", "90 000"],
                ["Запасы", "40 000"],
                ["Дебиторская задолженность", "120 000"],
            ]
        }
    ]
    text = "Бухгалтерский баланс\nФорма 0710001"

    metadata = pdf_extractor.parse_financial_statements_with_metadata(tables, text)

    assert metadata["current_assets"].value == 160000.0
    assert metadata["current_assets"].source == "derived"
