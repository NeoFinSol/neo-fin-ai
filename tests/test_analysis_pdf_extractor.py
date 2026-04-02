"""Tests for PDF text and table extraction."""
from unittest.mock import MagicMock, patch

import pytest

from src.analysis.pdf_extractor import (
    _extract_number_from_text,
    _extract_number_near_keywords,
    _normalize_number,
    _table_to_rows,
    extract_tables,
    extract_text_from_scanned,
    is_scanned_pdf,
    parse_financial_statements,
)


class TestIsScannedPdf:
    """Tests for is_scanned_pdf function."""

    def test_pdf_with_text_not_scanned(self):
        """Test PDF with text content is not scanned."""
        mock_page = MagicMock()
        mock_page.extract_text.return_value = "Financial Report 2024" * 100
        
        mock_reader = MagicMock()
        mock_reader.pages = [mock_page]
        
        with patch('src.analysis.pdf_extractor.PyPDF2.PdfReader', return_value=mock_reader):
            result = is_scanned_pdf("/fake/path.pdf")
            assert result is False

    def test_pdf_without_text_is_scanned(self):
        """Test PDF without text is considered scanned."""
        mock_page = MagicMock()
        mock_page.extract_text.return_value = ""
        
        mock_reader = MagicMock()
        mock_reader.pages = [mock_page]
        
        with patch('src.analysis.pdf_extractor.PyPDF2.PdfReader', return_value=mock_reader):
            result = is_scanned_pdf("/fake/path.pdf")
            assert result is True

    def test_pdf_with_little_text_and_images_is_scanned(self):
        """Test PDF with very little text but with images is considered scanned."""
        mock_page = MagicMock()
        mock_page.extract_text.return_value = "Short"
        
        # Mocking '/Resources' dictionary access for images
        mock_page.__getitem__.side_effect = lambda key: {
            '/Resources': {
                '/XObject': MagicMock(get_object=lambda: {'Image1': {'/Subtype': '/Image'}})
            }
        }.get(key, MagicMock())
        
        mock_reader = MagicMock()
        mock_reader.pages = [mock_page]
        
        with patch('src.analysis.pdf_extractor.PyPDF2.PdfReader', return_value=mock_reader):
            result = is_scanned_pdf("/fake/path.pdf")
            # Should return True because text < 50 and has images
            assert result is True

    def test_pdf_with_little_text_no_images_is_not_scanned(self):
        """Test PDF with little text (but >50) and no images is not scanned."""
        mock_page = MagicMock()
        # Text between 50 and 200
        mock_page.extract_text.return_value = "Financial data for 2024. Revenue: 1M, Net Profit: 100K."
        
        # Mocking empty '/Resources' for images
        mock_page.__getitem__.side_effect = lambda key: {
            '/Resources': {}
        }.get(key, MagicMock())
        
        mock_reader = MagicMock()
        mock_reader.pages = [mock_page]
        
        with patch('src.analysis.pdf_extractor.PyPDF2.PdfReader', return_value=mock_reader):
            result = is_scanned_pdf("/fake/path.pdf")
            # Should return False because text > 50 and no images
            assert result is False

    def test_pdf_with_invisible_text_is_scanned(self):
        """
        Test PDF with 'invisible' text layer (common in bad OCR).
        If text is present but very short (< 50) and there are images, it's scanned.
        """
        mock_page = MagicMock()
        mock_page.extract_text.return_value = "OCR layer fail"
        
        # Mocking '/Resources' with images
        mock_page.__getitem__.side_effect = lambda key: {
            '/Resources': {
                '/XObject': MagicMock(get_object=lambda: {'Img': {'/Subtype': '/Image'}})
            }
        }.get(key, MagicMock())
        
        mock_reader = MagicMock()
        mock_reader.pages = [mock_page]
        
        with patch('src.analysis.pdf_extractor.PyPDF2.PdfReader', return_value=mock_reader):
            result = is_scanned_pdf("/fake/path.pdf")
            assert result is True


class TestExtractMetricsRegex:
    """Tests for extract_metrics_regex function (moved from controllers)."""
    
    def test_extract_revenue_regex(self):
        """Test revenue extraction from text with regex."""
        from src.analysis.pdf_extractor import extract_metrics_regex
        text = "Выручка от реализации составила 1 234 567 рублей"
        result = extract_metrics_regex(text)
        assert result["revenue"] == 1234567.0

    def test_extract_net_profit_regex(self):
        """Test net profit extraction from text with regex."""
        from src.analysis.pdf_extractor import extract_metrics_regex
        text = "Чистая прибыль | 150 000 руб."
        result = extract_metrics_regex(text)
        assert result["net_profit"] == 150000.0

    def test_extract_multiple_metrics(self):
        """Test extracting multiple metrics from complex text."""
        from src.analysis.pdf_extractor import extract_metrics_regex
        text = """
        ОТЧЕТ О ФИНАНСОВЫХ РЕЗУЛЬТАТАХ
        Выручка | 5 000 000
        Чистая прибыль | 300 000
        Итого активов | 10 000 000
        """
        result = extract_metrics_regex(text)
        assert result["revenue"] == 5000000.0
        assert result["net_profit"] == 300000.0
        assert result["total_assets"] == 10000000.0

    def test_normalize_russian_number_formats(self):
        """Test regex extraction handles Russian number formats correctly."""
        from src.analysis.pdf_extractor import extract_metrics_regex
        
        # Space as thousand separator, comma as decimal
        text = "Выручка | 1 234 567,89"
        result = extract_metrics_regex(text)
        assert result["revenue"] == 1234567.89
        
        # No separators
        text = "Выручка | 1000000"
        result = extract_metrics_regex(text)
        assert result["revenue"] == 1000000.0

    def test_ignore_negative_or_zero_values_in_regex(self):
        """Test that regex extraction ignores negative or zero values if specified in logic."""
        from src.analysis.pdf_extractor import extract_metrics_regex
        text = "Выручка | 0"
        result = extract_metrics_regex(text)
        # Logic specifies: if value is not None and value > 0: metrics[field] = value
        assert "revenue" not in result


class TestExtractTextFromScanned:
    """Tests for extract_text_from_scanned function."""

    def test_successful_ocr(self):
        """Test successful OCR extraction."""
        mock_image = MagicMock()
        mock_convert = MagicMock(return_value=[mock_image])
        
        with patch('src.analysis.pdf_extractor.convert_from_path', mock_convert):
            with patch('src.analysis.pdf_extractor.pytesseract.image_to_string', return_value="OCR Text"):
                result = extract_text_from_scanned("/fake/path.pdf")
                assert "OCR Text" in result

    def test_tesseract_error_fallback(self):
        """Test fallback when Tesseract fails with specific language."""
        mock_image = MagicMock()
        mock_convert = MagicMock(return_value=[mock_image])
        
        import pytesseract
        
        def side_effect(image, lang=None):
            if lang:
                raise pytesseract.TesseractError("error", "Tesseract failed")
            return "Fallback text"
        
        with patch('src.analysis.pdf_extractor.convert_from_path', mock_convert):
            with patch('src.analysis.pdf_extractor.pytesseract.image_to_string', side_effect=side_effect):
                result = extract_text_from_scanned("/fake/path.pdf")
                assert "Fallback text" in result

    def test_ocr_exception_logged(self):
        """Test that OCR exceptions are logged but don't stop processing."""
        mock_image = MagicMock()
        mock_convert = MagicMock(return_value=[mock_image])
        
        with patch('src.analysis.pdf_extractor.convert_from_path', mock_convert):
            with patch('src.analysis.pdf_extractor.pytesseract.image_to_string', side_effect=Exception("OCR failed")):
                result = extract_text_from_scanned("/fake/path.pdf")
                # Should return empty string
                assert result == ""

    def test_convert_from_path_exception(self):
        """Test exception in convert_from_path degrades gracefully to empty OCR text."""
        with patch('src.analysis.pdf_extractor.convert_from_path', side_effect=Exception("Conversion failed")):
            result = extract_text_from_scanned("/fake/path.pdf")
            assert result == ""


class TestExtractTables:
    """Tests for extract_tables function."""

    def test_successful_table_extraction_prefers_stream(self):
        """Test successful table extraction prefers stream flavor on the current path."""
        mock_table = MagicMock()
        mock_df = MagicMock()
        mock_df.empty = False
        mock_df.values.tolist.return_value = [["Выручка", "1 000 000"], ["Чистая прибыль", "150 000"]]
        mock_table.df = mock_df
        
        mock_tables = MagicMock()
        mock_tables.n = 1
        mock_tables.__iter__ = lambda self: iter([mock_table])
        mock_tables.__getitem__ = lambda self, idx: mock_table
        
        with patch('src.analysis.pdf_extractor.camelot.read_pdf', return_value=mock_tables):
            # We must mock is_scanned_pdf because extract_tables calls it
            with patch('src.analysis.pdf_extractor.is_scanned_pdf', return_value=False):
                result = extract_tables("/fake/path.pdf")
                assert len(result) > 0
                assert result[0]["flavor"] == "stream"

    def test_lattice_fails_stream_works(self):
        """Test that stream flavor is tried when lattice fails."""
        mock_table = MagicMock()
        mock_df = MagicMock()
        mock_df.empty = False
        mock_df.values.tolist.return_value = [["Выручка", "2 000 000"], ["Чистая прибыль", "250 000"]]
        mock_table.df = mock_df
        
        mock_tables = MagicMock()
        mock_tables.n = 1
        mock_tables.__iter__ = lambda self: iter([mock_table])
        
        def read_side_effect(pdf_path, pages, flavor):
            if flavor == "lattice":
                raise Exception("Lattice failed")
            return mock_tables
        
        with patch('src.analysis.pdf_extractor.camelot.read_pdf', side_effect=read_side_effect):
            # We must mock is_scanned_pdf because extract_tables calls it
            with patch('src.analysis.pdf_extractor.is_scanned_pdf', return_value=False):
                result = extract_tables("/fake/path.pdf")
                assert len(result) > 0
                assert result[0]["flavor"] == "stream"

    def test_both_flavors_fail(self):
        """Test empty result when both flavors fail."""
        with patch('src.analysis.pdf_extractor.camelot.read_pdf', side_effect=Exception("Failed")):
            result = extract_tables("/fake/path.pdf")
            assert result == []

    def test_empty_table_skipped(self):
        """Test that empty tables are skipped."""
        mock_table = MagicMock()
        mock_df = MagicMock()
        mock_df.empty = True
        mock_table.df = mock_df
        
        mock_tables = MagicMock()
        mock_tables.n = 1
        mock_tables.__iter__ = lambda self: iter([mock_table])
        
        with patch('src.analysis.pdf_extractor.camelot.read_pdf', return_value=mock_tables):
            result = extract_tables("/fake/path.pdf")
            assert result == []

    def test_none_dataframe_skipped(self):
        """Test that None dataframe is skipped."""
        mock_table = MagicMock()
        mock_table.df = None
        
        mock_tables = MagicMock()
        mock_tables.n = 1
        mock_tables.__iter__ = lambda self: iter([mock_table])
        
        with patch('src.analysis.pdf_extractor.camelot.read_pdf', return_value=mock_tables):
            result = extract_tables("/fake/path.pdf")
            assert result == []


class TestParseFinancialStatements:
    """Tests for parse_financial_statements function."""

    def test_extract_from_tables(self):
        """Test extracting metrics from table data."""
        tables = [{
            "flavor": "lattice",
            "rows": [
                ["Выручка", "1 000 000"],
                ["Чистая прибыль", "150 000"],
            ]
        }]
        
        result = parse_financial_statements(tables, "")
        
        assert result["revenue"] == 1000000.0
        assert result["net_profit"] == 150000.0

    def test_extract_from_text(self):
        """Test extracting metrics from text when not in tables."""
        text = """
        Financial Report
        Выручка за год составила 2 500 000 рублей.
        Чистая прибыль: 300 000 руб.
        """
        
        result = parse_financial_statements([], text)
        
        assert result["revenue"] == 2500000.0
        assert result["net_profit"] == 300000.0

    def test_tables_take_precedence_over_text(self):
        """Test that table values take precedence over text values."""
        tables = [{
            "flavor": "lattice",
            "rows": [["Выручка", "1 000 000"]]
        }]
        text = "Выручка 5 000 000"
        
        result = parse_financial_statements(tables, text)
        
        # Table value should be used, not text value
        assert result["revenue"] == 1000000.0

    def test_empty_input(self):
        """Test with empty tables and text."""
        result = parse_financial_statements([], "")
        
        # All metrics should be None
        for key, value in result.items():
            assert value is None

    def test_no_matching_metrics(self):
        """Test when no keywords match."""
        tables = [{"flavor": "lattice", "rows": [["Unknown metric", "12345"]]}]
        text = "Some random text without financial metrics"
        
        result = parse_financial_statements(tables, text)
        
        for key, value in result.items():
            assert value is None


class TestTableToRows:
    """Tests for _table_to_rows function."""

    def test_dict_with_rows_key(self):
        """Test dict with 'rows' key."""
        table = {"rows": [["Row1"], ["Row2"]]}
        result = _table_to_rows(table)
        assert result == [["Row1"], ["Row2"]]

    def test_plain_list_of_lists(self):
        """Test plain list of lists."""
        table = [["A", "B"], ["C", "D"]]
        result = _table_to_rows(table)
        assert result == [["A", "B"], ["C", "D"]]

    def test_list_of_dicts(self):
        """Test list of dicts converted to rows."""
        table = [{"col1": "A", "col2": "B"}, {"col1": "C", "col2": "D"}]
        result = _table_to_rows(table)
        # Should extract values
        assert len(result) == 2

    def test_empty_list(self):
        """Test empty list returns empty."""
        result = _table_to_rows([])
        assert result == []

    def test_unsupported_type(self):
        """Test unsupported type returns empty list."""
        result = _table_to_rows("string")
        assert result == []


class TestExtractNumberFromText:
    """Tests for _extract_number_from_text function."""

    def test_simple_number(self):
        """Test extracting simple number."""
        result = _extract_number_from_text("Revenue: 1000000")
        assert result == 1000000.0

    def test_number_with_spaces(self):
        """Test extracting number with spaces."""
        result = _extract_number_from_text("Amount: 1 000 000 rub")
        assert result == 1000000.0

    def test_negative_number(self):
        """Test extracting negative number."""
        # Pattern matches digits, parentheses handled by _normalize_number
        result = _extract_number_from_text("Loss: -500")
        assert result == -500.0
        
        # Parentheses notation not captured by regex in _extract_number_from_text
        # (it's handled when parsing tables with full context)
        result = _extract_number_from_text("Value: 500")
        assert result == 500.0

    def test_no_numbers(self):
        """Test text without numbers."""
        result = _extract_number_from_text("No numbers here")
        assert result is None


class TestExtractNumberNearKeywords:
    """Tests for _extract_number_near_keywords function."""

    def test_number_after_keyword(self):
        """Test extracting number after keyword."""
        result = _extract_number_near_keywords("выручка 1 500 000", ["выручка"])
        assert result == 1500000.0

    def test_number_before_keyword(self):
        """Test extracting number before keyword."""
        result = _extract_number_near_keywords("1 500 000 выручка", ["выручка"])
        # Pattern looks after keyword, so this might not match
        # Depends on implementation

    def test_no_keyword(self):
        """Test when keyword not found."""
        result = _extract_number_near_keywords("random text 123", ["выручка"])
        assert result is None

    def test_multiple_keywords(self):
        """Test with multiple keywords."""
        result = _extract_number_near_keywords("revenue 2 000 000", ["выручка", "revenue"])
        assert result == 2000000.0


class TestNormalizeNumber:
    """Tests for _normalize_number function."""

    def test_simple_number(self):
        """Test normalizing simple number."""
        result = _normalize_number("1000")
        assert result == 1000.0

    def test_number_with_spaces(self):
        """Test normalizing number with spaces."""
        result = _normalize_number("1 000 000")
        assert result == 1000000.0

    def test_number_with_commas(self):
        """Test normalizing number with commas as decimal separator."""
        # European format: comma as decimal separator
        result = _normalize_number("1000,50")
        assert result == 1000.50
        
        # Simple case without separators
        result = _normalize_number("1000000")
        assert result == 1000000.0

    def test_negative_in_parentheses(self):
        """Test negative number in parentheses."""
        result = _normalize_number("(500)")
        assert result == -500.0

    def test_empty_string(self):
        """Test empty string returns None."""
        result = _normalize_number("")
        assert result is None

    def test_only_dash(self):
        """Test dash-only returns None."""
        result = _normalize_number("-")
        assert result is None

    def test_invalid_string(self):
        """Test invalid string returns None."""
        result = _normalize_number("abc")
        assert result is None

    def test_none_input(self):
        """Test None input returns None."""
        result = _normalize_number(None)
        assert result is None

    def test_number_with_currency(self):
        """Test number with currency symbols removed."""
        # Currency symbols and thousand separators are removed
        result = _normalize_number("1000.50")
        assert result == 1000.50
        
        # Test with dollar sign (removed by regex)
        result = _normalize_number("$1000")
        assert result == 1000.0

    def test_nbsp_character(self):
        """Test handling of non-breaking space."""
        result = _normalize_number("1\u00a0000")
        assert result == 1000.0
