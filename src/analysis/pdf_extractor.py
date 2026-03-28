import logging
import os
import re
from dataclasses import dataclass
from typing import Any, Literal

import camelot
from pdf2image import convert_from_path
import PyPDF2
import pytesseract

logger = logging.getLogger(__name__)

# Configure Tesseract via env variable (optional); falls back to system PATH
_tesseract_cmd = os.getenv("TESSERACT_CMD")
if _tesseract_cmd:
    pytesseract.pytesseract.tesseract_cmd = _tesseract_cmd


def _check_tesseract_available() -> bool:
    try:
        pytesseract.get_tesseract_version()
        return True
    except Exception:
        return False


TESSERACT_AVAILABLE = _check_tesseract_available()

# Maximum number of pages to process via OCR to prevent hangs on large scanned PDFs
MAX_OCR_PAGES = 50

_RAW_THRESHOLD = os.getenv("CONFIDENCE_THRESHOLD", "0.5")
try:
    CONFIDENCE_THRESHOLD: float = float(_RAW_THRESHOLD)
    if not (0.0 <= CONFIDENCE_THRESHOLD <= 1.0):
        logger.warning(
            "CONFIDENCE_THRESHOLD=%s out of [0.0, 1.0], using default 0.5", _RAW_THRESHOLD
        )
        CONFIDENCE_THRESHOLD = 0.5
except ValueError:
    logger.warning(
        "CONFIDENCE_THRESHOLD=%r is not a valid float, using default 0.5", _RAW_THRESHOLD
    )
    CONFIDENCE_THRESHOLD = 0.5

# ---------------------------------------------------------------------------
# Extraction metadata types
# ---------------------------------------------------------------------------

ExtractionSource = Literal["table_exact", "table_partial", "text_regex", "derived"]


@dataclass
class ExtractionMetadata:
    value: float | None
    confidence: float  # always in [0.0, 1.0]
    source: ExtractionSource


def determine_source(
    match_type: str,
    is_exact: bool = False,
    is_derived: bool = False,
) -> tuple[ExtractionSource, float]:
    """Return (source, confidence) deterministically based on extraction method."""
    if is_derived:
        return ("derived", 0.3)
    if match_type == "table":
        if is_exact:
            return ("table_exact", 0.9)
        return ("table_partial", 0.7)
    if match_type == "text_regex":
        return ("text_regex", 0.5)
    return ("derived", 0.3)


def apply_confidence_filter(
    metadata: dict[str, ExtractionMetadata],
    threshold: float | None = None,
) -> tuple[dict[str, float | None], dict[str, dict]]:
    """
    Filter extraction metadata by confidence threshold.

    Args:
        metadata: Per-metric extraction results from parse_financial_statements_with_metadata.
        threshold: Minimum confidence to keep a value. Defaults to CONFIDENCE_THRESHOLD.
                   confidence >= threshold → keep value; confidence < threshold → None.
                   value=None is always preserved as None regardless of confidence.

    Returns:
        filtered_metrics: All keys preserved; low-confidence values replaced with None.
        extraction_metadata_payload: {key: {"confidence": float, "source": str}} for all keys.
    """
    if threshold is None:
        threshold = CONFIDENCE_THRESHOLD

    filtered_metrics: dict[str, float | None] = {}
    extraction_metadata_payload: dict[str, dict] = {}

    for key, meta in metadata.items():
        if meta.value is None or meta.confidence < threshold:
            filtered_metrics[key] = None
        else:
            filtered_metrics[key] = meta.value

        extraction_metadata_payload[key] = {
            "confidence": meta.confidence,
            "source": meta.source,
        }

    return filtered_metrics, extraction_metadata_payload


# ---------------------------------------------------------------------------

# Matches numbers with Russian-style grouping (spaces/dots between digit groups)
# Uses [ \t\xa0] instead of \s to avoid matching newlines (which causes OCR number merging)
_NUMBER_PATTERN = re.compile(r"[-(]?\d{1,3}(?:[ \t\xa0]\d{3})+(?:[.,]\d+)?|[-(]?\d+(?:[.,]\d+)?")

_METRIC_KEYWORDS = {
    "revenue": [
        "выручка от реализации",
        "выручка",
        "revenue",
        "sales revenue",
        "net sales",
        "доходы от реализации",
        "совокупный доход",
    ],
    "net_profit": [
        "чистая прибыль (убыток)",
        "чистая прибыль",
        "net profit",
        "profit for the year",
        "profit (loss)",
        "прибыль после налогообложения",
    ],
    "total_assets": [
        "итого активов",
        "итого активы",
        "активы всего",
        "total assets",
        "активов всего",
        "баланс",
    ],
    "equity": [
        "итого по разделу iii",
        "итого капитала",
        "капитал и резервы",
        "total equity",
        "собственный капитал",
    ],
    "liabilities": [
        "итого обязательств",
        "total liabilities",
        "liabilities",
    ],
    "current_assets": [
        "итого оборотных активов",
        "оборотные активы всего",
        "current assets",
        "итого по разделу ii",
    ],
    "short_term_liabilities": [
        "итого краткосрочных обязательств",
        "краткосрочные обязательства всего",
        "short-term liabilities",
        "current liabilities",
        "итого по разделу v",
    ],
    "accounts_receivable": [
        "дебиторская задолженность",
        "accounts receivable",
        "trade receivables",
    ],
    # ===== NEW FIELDS FOR EXTENDED RATIOS =====
    "inventory": [
        "запасы",
        "товарно-материальные ценности",
        "inventory",
        "stock",
        "merchandise",
    ],
    "cash_and_equivalents": [
        "денежные средства",
        "наличные",
        "cash and equivalents",
        "cash and cash equivalents",
        "cash",
    ],
    "ebitda": [
        "ebitda",
        "ebit до амортизации",
        "прибыль до налогов",
    ],
    "ebit": [
        "ebit",
        "операционная прибыль",
        "operating profit",
        "прибыль от операций",
    ],
    "interest_expense": [
        "процентные расходы",
        "interest expense",
        "interest paid",
        "процентные платежи",
    ],
    "cost_of_goods_sold": [
        "себестоимость продаж",
        "cost of goods sold",
        "cogs",
        "себестоимость",
    ],
    "average_inventory": [
        "средний запас",
        "average inventory",
        "средний остаток запасов",
    ],
}


def extract_text(pdf_path: str) -> str:
    """
    Extract text from PDF using PyPDF2.

    Args:
        pdf_path: Path to PDF file

    Returns:
        str: Extracted text content
    """
    try:
        reader = PyPDF2.PdfReader(pdf_path)
        texts: list[str] = []
        for page_index, page in enumerate(reader.pages, start=1):
            try:
                texts.append(page.extract_text() or "")
            except Exception as exc:
                logger.warning("Failed to extract text from page %s: %s", page_index, exc)
        return "\n".join(texts).strip()
    except Exception as exc:
        logger.error("Failed to read PDF for text extraction: %s", exc)
        return ""


def _is_glyph_encoded(text: str) -> bool:
    """Detect if extracted text contains undecodable glyph references like /0 /1 /23.

    Some PDFs use custom embedded fonts without ToUnicode tables.
    PyPDF2 extracts them as /N tokens instead of real characters.
    When more than 30% of 'words' are glyph tokens, the text is unusable.
    """
    if not text or len(text) < 20:
        return False
    import re as _re
    tokens = text.split()
    if not tokens:
        return False
    glyph_tokens = sum(1 for t in tokens if _re.fullmatch(r'/\d+', t))
    return (glyph_tokens / len(tokens)) > 0.3


def is_scanned_pdf(pdf_path: str) -> bool:
    """
    Check if PDF is scanned or has a searchable text layer.
    
    Checks first 3 pages for text. If very little text is found,
    also checks for image presence to confirm it's likely a scan.
    """
    try:
        reader = PyPDF2.PdfReader(pdf_path)
        num_pages = len(reader.pages)
        check_pages = reader.pages[: min(3, num_pages)]
        
        text_parts = []
        has_images = False
        
        for page in check_pages:
            try:
                # 1. Try to extract text
                page_text = (page.extract_text() or "").strip()
                text_parts.append(page_text)
                
                # 2. Check for images/xobjects
                if '/XObject' in page['/Resources']:
                    xobjs = page['/Resources']['/XObject'].get_object()
                    for obj_name in xobjs:
                        if xobjs[obj_name]['/Subtype'] == '/Image':
                            has_images = True
                            break
            except Exception as exc:
                logger.debug("Page check failed: %s", exc)
                
        text = "".join(text_parts).strip()
        
        # If we have significant text, check if it's actually readable
        if len(text) > 200:
            if _is_glyph_encoded(text):
                logger.warning(
                    "PDF text layer contains undecodable glyph tokens — forcing OCR"
                )
                return True
            return False
            
        # If very little text but has images, it's likely a scan
        if has_images and len(text) < 50:
            return True
            
        # Fallback to old simple check for robustness
        return len(text) < 50
        
    except Exception as exc:
        logger.exception("Failed to check PDF for text: %s", exc)
        return True


def _get_poppler_path() -> str | None:
    """Return poppler bin path on Windows if not in PATH, else None."""
    import shutil
    if shutil.which("pdftoppm"):
        return None  # already in PATH
    # Common Windows install locations
    candidates = [
        r"C:\Program Files\poppler\Library\bin",
        r"C:\Program Files\poppler\bin",
        r"C:\poppler\bin",
        r"C:\poppler\Library\bin",
    ]
    for path in candidates:
        import os
        if os.path.isfile(os.path.join(path, "pdftoppm.exe")):
            return path
    return None


def extract_text_from_scanned(pdf_path: str) -> str:
    if not TESSERACT_AVAILABLE:
        logger.warning(
            "OCR недоступен: установите tesseract-ocr или задайте TESSERACT_CMD"
        )

    import gc

    poppler_path = _get_poppler_path()

    # Process one page at a time to avoid OOM on large scanned PDFs
    # (100-page scan at 300 DPI can be 300MB–2GB if loaded all at once)
    texts: list[str] = []
    page_num = 1
    while True:
        if page_num > MAX_OCR_PAGES:
            logger.warning("OCR page limit reached (%d pages), stopping", MAX_OCR_PAGES)
            break
        try:
            images = convert_from_path(
                pdf_path,
                first_page=page_num,
                last_page=page_num,
                poppler_path=poppler_path,
            )
            single_page_batch = True
        except TypeError:
            images = convert_from_path(pdf_path)
            single_page_batch = False
        except Exception as exc:
            # No more pages or conversion error — stop
            logger.debug("Page %d conversion stopped: %s", page_num, exc)
            break

        if not images:
            break

        for offset, image in enumerate(images):
            current_page = page_num + offset
            try:
                try:
                    page_text = pytesseract.image_to_string(image, lang="rus+eng")
                except pytesseract.TesseractError:
                    page_text = pytesseract.image_to_string(image)
                texts.append(page_text)
            except Exception as exc:
                logger.warning("OCR failed on page %d: %s", current_page, exc)

        del images
        gc.collect()

        if not single_page_batch:
            break

        page_num += 1

    return "\n".join(texts).strip()


def _is_financial_table(rows: list) -> bool:
    """Check if table rows contain financial data (not just headers/TOC).

    Uses two strategies:
    1. Keyword matching (works for properly encoded PDFs)
    2. Structural heuristic: table has multiple rows with large numbers (works for
       PDFs with encoding issues where Cyrillic appears as pseudographics)
    """
    financial_keywords = [
        "выручка", "прибыль", "актив", "обязательств", "капитал",
        "revenue", "profit", "assets", "liabilities", "equity",
        "баланс", "отчёт", "финансов", "оборотн", "внеоборотн",
    ]

    text = " ".join(str(cell).lower() for row in rows for cell in row if cell)

    # Strategy 1: keyword hits
    keyword_hits = sum(1 for kw in financial_keywords if kw in text)
    if keyword_hits >= 2:
        return True

    # Strategy 2: structural heuristic for encoding-broken PDFs
    # A financial table typically has: many rows, each with at least one large number (>1000)
    rows_with_large_numbers = 0
    for row in rows:
        for cell in row:
            if cell is None:
                continue
            cell_str = str(cell).replace(" ", "").replace("\xa0", "").replace(",", "")
            # Remove parentheses (negative numbers) and currency symbols
            cell_str = cell_str.strip("()₽$€")
            # Remove spaces from grouped numbers like "361 751 315"
            digits_only = "".join(c for c in cell_str if c.isdigit())
            if len(digits_only) >= 6:  # >= 6 digits = >= 100,000
                rows_with_large_numbers += 1
                break

    rows_with_any_numbers = 0
    for row in rows:
        for cell in row:
            if cell is None:
                continue
            cell_str = str(cell)
            if any(ch.isdigit() for ch in cell_str):
                rows_with_any_numbers += 1
                break

    if keyword_hits >= 1 and rows_with_any_numbers >= 1:
        return True

    # If 5+ rows have large numbers, it's likely a financial table
    return rows_with_large_numbers >= 5


def _is_year(v: float) -> bool:
    """Check if a value looks like a year (1900–2100) using safe float comparison."""
    if isinstance(v, int):
        return 1900 <= v <= 2100
    if isinstance(v, float) and v.is_integer():
        return 1900 <= int(v) <= 2100
    return False


def _is_valid_financial_value(value: float | None) -> bool:
    """Sanity check for financial values.

    Accepts any numeric value except:
    - None
    - Integers in year range 1900–2100 (likely a reporting year, not a metric)
    - Absolute value > 1e14 (likely a parsing error, 100 trillion is a safe upper bound)
    - Values that are exactly 0 (often noise or OCR errors for labels)
    """
    if value is None:
        return False

    # Likely a year label, not a financial metric
    if _is_year(value):
        return False

    # Too large — likely parsing error or joined columns
    # 1e13 = 10 trillion rubles. Safe upper bound for any real Russian company financial value.
    if abs(value) > 1e13:
        return False

    # Skip exactly zero values if they come from text/ocr as they are often false positives
    if value == 0:
        return False

    return True


def _detect_scale_factor(text: str) -> float:
    """
    Detect the scale factor from PDF text (thousands, millions, billions).
    Returns multiplier: 1000 if values are in thousands, 1_000_000 if millions, etc.
    """
    text_lower = text.lower()
    # Common Russian financial report scale indicators
    patterns_millions = [
        "в миллионах рублей", "млн руб", "млн. руб", "в млн.", "тыс. млн",
        "in millions", "millions of rubles",
    ]
    patterns_thousands = [
        "в тысячах рублей", "тыс. руб", "тыс.руб", "в тыс.", "в тысячах",
        "in thousands", "thousands of rubles",
    ]
    patterns_billions = [
        "в миллиардах рублей", "млрд руб", "млрд. руб", "в млрд.",
        "in billions",
    ]

    for p in patterns_billions:
        if p in text_lower:
            logger.info("Scale detected: billions (×1,000,000,000)")
            return 1_000_000_000.0
    for p in patterns_millions:
        if p in text_lower:
            logger.info("Scale detected: millions (×1,000,000)")
            return 1_000_000.0
    for p in patterns_thousands:
        if p in text_lower:
            logger.info("Scale detected: thousands (×1,000)")
            return 1_000.0

    return 1.0  # no scale indicator found


def extract_tables(pdf_path: str, force_ocr: bool = False) -> list[dict[str, Any]]:
    """
    Extract tables from PDF using camelot.
    For image-based pages, use OCR via pdf2image + pytesseract.
    
    Args:
        pdf_path: Path to PDF file
        force_ocr: If True, skip camelot and use OCR directly (for complex scanned PDFs)
    """
    import concurrent.futures

    tables_data: list[dict[str, Any]] = []
    
    # If force_ocr, skip camelot entirely
    if force_ocr:
        logger.info("Force OCR mode, skipping camelot...")
        try:
            ocr_text = extract_text_from_scanned(pdf_path)
            if ocr_text:
                tables_data.append({
                    "flavor": "ocr",
                    "rows": [["OCR_TEXT", ocr_text]],
                })
                logger.info("OCR extracted %d characters", len(ocr_text))
        except Exception as ocr_exc:
            logger.warning("OCR extraction failed: %s", ocr_exc)
        return tables_data
    
    financial_tables_found = False

    # Try lattice first (works better with Ghostscript)
    # Limit to first 30 pages to avoid hanging on large annual reports
    # Financial statements are almost always in the first half of the document
    _CAMELOT_TIMEOUT = 45
    _CAMELOT_MAX_PAGES = "1-30"

    for flavor in ("lattice", "stream"):
        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(
                    camelot.read_pdf, pdf_path, pages=_CAMELOT_MAX_PAGES, flavor=flavor
                )
                try:
                    tables = future.result(timeout=_CAMELOT_TIMEOUT)
                except concurrent.futures.TimeoutError:
                    logger.warning("Camelot timed out after %ds (flavor=%s), skipping", _CAMELOT_TIMEOUT, flavor)
                    continue
        except Exception as exc:
            logger.warning("Camelot failed with flavor=%s: %s", flavor, exc)
            continue

        if tables and tables.n > 0:
            for table in tables:
                df = table.df
                if df is None or df.empty:
                    continue
                
                rows = df.values.tolist()
                
                # Check if this is a real financial table
                if _is_financial_table(rows):
                    financial_tables_found = True
                    tables_data.append({
                        "flavor": flavor,
                        "rows": rows,
                    })
                    logger.debug("Found financial table with %d rows", len(rows))

        if financial_tables_found:
            break
    
    # If too many tables found, keep only the most data-rich ones (not OCR fallback)
    if len(tables_data) > 20:
        logger.info("Many tables found (%d), keeping top 10 by row count", len(tables_data))
        tables_data = sorted(tables_data, key=lambda t: len(t.get("rows", [])), reverse=True)[:10]
        financial_tables_found = True
    
    if not financial_tables_found:
        logger.info("No financial tables found via camelot, trying OCR extraction...")
        try:
            ocr_text = extract_text_from_scanned(pdf_path)
            if ocr_text:
                tables_data.append({
                    "flavor": "ocr",
                    "rows": [["OCR_TEXT", ocr_text]],
                })
                logger.info("OCR extracted %d characters", len(ocr_text))
        except Exception as ocr_exc:
            logger.warning("OCR extraction failed: %s", ocr_exc)

    return tables_data


def _source_priority(match_type: str, is_exact: bool) -> int:
    """Return numeric priority for a raw extraction entry.

    Higher number = higher priority. Used to keep the best source when
    the same metric appears in multiple tables or text sections.
    """
    if match_type == "table" and is_exact:
        return 3  # table_exact
    if match_type == "table":
        return 2  # table_partial
    if match_type == "text_regex":
        return 1
    return 0  # derived


def _raw_set(
    raw: dict,
    key: str,
    value: float,
    match_type: str,
    is_exact: bool,
) -> None:
    """Set raw[key] only if new entry has strictly higher priority than existing."""
    new_priority = _source_priority(match_type, is_exact)
    if key in raw:
        existing_priority = _source_priority(raw[key][1], raw[key][2])
        if new_priority <= existing_priority:
            return
    raw[key] = (value, match_type, is_exact)


def parse_financial_statements_with_metadata(
    tables: list, text: str
) -> dict[str, ExtractionMetadata]:
    """
    Returns ExtractionMetadata per metric for all keys in _METRIC_KEYWORDS.
    Missing metrics: ExtractionMetadata(value=None, confidence=0.0, source="derived").
    Always returns exactly len(_METRIC_KEYWORDS) keys.
    """
    # raw[key] = (value, match_type, is_exact)
    # match_type: "table" | "text_regex" | "derived"
    raw: dict[str, tuple[float, str, bool]] = {}

    # Detect scale factor ONCE at the start — apply to all extracted values
    # This fixes the root cause of ROA=2290329% (values in thousands treated as absolute)
    scale_factor = _detect_scale_factor(text)
    if scale_factor != 1.0:
        logger.info("Scale factor %.0f detected in parse_financial_statements_with_metadata", scale_factor)

    # Metrics that are ratios/percentages — must NOT be scaled
    _RATIO_KEYS = frozenset({
        "roa", "roe", "current_ratio", "equity_ratio", "debt_to_revenue",
    })

    # Pass 0: positional parsing for tables with garbled encoding
    # Works for IFRS/RSBU reports where Cyrillic is broken but numbers are intact.
    # Strategy A: match by RSBU 4-digit line codes (e.g. 2110, 1600)
    # Strategy B: structural parsing — col0=label(garbled), col1=note(1-2 digits), col2=value
    _LINE_CODE_MAP: dict[str, str] = {
        "2110": "revenue", "2400": "net_profit", "2300": "net_profit",
        "1600": "total_assets", "1700": "total_assets",
        "1300": "equity", "1200": "current_assets",
        "1500": "short_term_liabilities", "1400": "liabilities",
        "1230": "accounts_receivable", "1210": "inventory",
        "1250": "cash_and_equivalents", "2120": "cost_of_goods_sold",
        "2200": "ebit",
    }
    # Garbled-text keyword map: maps garbled pseudographic patterns to metric keys
    # Uses short substrings that appear in both garbled variants and normal Cyrillic.
    # Key insight: use substrings from the MIDDLE of words to avoid first-char encoding issues.
    _GARBLED_KEYWORDS: dict[str, str] = {
        # Normal Cyrillic (standard PDFs)
        "выручка": "revenue",
        "чистая прибыль": "net_profit",
        "прибыль за год": "net_profit",
        "итого активов": "total_assets",
        "итого активы": "total_assets",
        "итого капитала": "equity",
        "итого капитал": "equity",
        "собственный капитал": "equity",
        "денежные средства": "cash_and_equivalents",
        "запасы": "inventory",
        "дебиторская задолженность": "accounts_receivable",
        "краткосрочные обязательства": "short_term_liabilities",
        "оборотные активы": "current_assets",
        "операционная прибыль": "ebit",
        "финансовые расходы": "interest_expense",
        "себестоимость": "cost_of_goods_sold",
        # Garbled substrings (middle-of-word, encoding-agnostic)
        "т√Ёєўър": "revenue",           # Выручка
        "шс√ы№ чр уюф": "net_profit",   # прибыль за год
        "шёЄр  яЁшс√ы№": "net_profit",  # Чистая прибыль
        "Єюую ръЄшт√": "total_assets",  # Итого активы
        "шЄюую ъряшЄры": "equity",      # Итого капитал (variant 1)
        "Єюую ъряшЄры": "equity",       # Итого капитал (variant 2)
        "хэхцэ√х ёЁхфёЄтр": "cash_and_equivalents",
        "рярё√": "inventory",
        "хсшЄюЁёър  чрфюыцхээюёЄ№": "accounts_receivable",
        "ЁрЄъюёЁюўэ√х юс чрЄхы№ёЄтр": "short_term_liabilities",
        "сюЁюЄэ√х ръЄшт√": "current_assets",
        "юяхЁрЎшюээр  яЁшс√ы№": "ebit",
        "Їшэрэёют√х Ёрёїюф√": "interest_expense",
        "хсхёЄюшьюёЄ№": "cost_of_goods_sold",
    }

    for table in tables or []:
        rows = _table_to_rows(table)
        if table.get("flavor") == "ocr":
            continue
        for row in rows:
            if len(row) < 3:
                continue

            # Strategy A: 4-digit RSBU line code in any cell
            for ci, cell in enumerate(row):
                if cell is None:
                    continue
                cs = str(cell).strip().replace("\xa0", "").replace(" ", "")
                if cs.isdigit() and len(cs) == 4 and cs in _LINE_CODE_MAP:
                    metric_key = _LINE_CODE_MAP[cs]
                    value = _extract_first_numeric_cell(row[ci + 1:])
                    if value is not None and _is_valid_financial_value(value):
                        _raw_set(raw, metric_key, value, "table", True)
                        logger.debug("[EXTRACT] %s = %s (source=line_code, code=%s)", metric_key, value, cs)

            # Strategy B: garbled keyword in col0, note number in col1, value in col2+
            if len(row) >= 3:
                label_cell = str(row[0]).lower() if row[0] else ""
                for garbled_kw, metric_key in _GARBLED_KEYWORDS.items():
                    if garbled_kw in label_cell:
                        value = _extract_first_numeric_cell(row[1:])
                        if value is not None and _is_valid_financial_value(value):
                            # Reject suspiciously small values for monetary metrics
                            # (likely page numbers from TOC, not financial values)
                            _MONETARY_METRICS = {
                                "revenue", "net_profit", "total_assets", "equity",
                                "liabilities", "current_assets", "short_term_liabilities",
                                "accounts_receivable", "inventory", "cash_and_equivalents",
                                "ebitda", "ebit", "interest_expense", "cost_of_goods_sold",
                            }
                            if metric_key in _MONETARY_METRICS and abs(value) < 1000:
                                logger.debug("Skipping small value %s for %s (likely TOC page number)", value, metric_key)
                                break
                            _raw_set(raw, metric_key, value, "table", True)
                            logger.debug("[EXTRACT] %s = %s (source=garbled_kw, kw=%s)", metric_key, value, garbled_kw)
                        break


    for table in tables or []:
        rows = _table_to_rows(table)
        
        # Check if this is an OCR pseudo-table
        if table.get("flavor") == "ocr":
            # Extract metrics directly from OCR text using regex
            for row in rows:
                if len(row) >= 2 and row[0] == "OCR_TEXT":
                    ocr_text = row[1]
                    ocr_text_lower = ocr_text.lower()
                    for metric_key, keywords in _METRIC_KEYWORDS.items():
                        # _raw_set handles priority; no early-exit needed here
                        # Search for keyword + number pattern in OCR text (context window 50 chars)
                        # Use [ \t\xa0] instead of \s to avoid merging numbers across newlines
                        for keyword in keywords:
                            pattern = rf"{keyword}[^0-9]{{0,50}}(\d{{1,3}}(?:[ \t\xa0]\d{{3}})+(?:[.,]\d+)?|\d+(?:[.,]\d+)?)"
                            match = re.search(pattern, ocr_text_lower, re.IGNORECASE)
                            if match:
                                value = _normalize_number(match.group(1))
                                if _is_valid_financial_value(value):
                                    _raw_set(raw, metric_key, value, "text_regex", False)
                                    logger.debug("[EXTRACT] %s = %s (source=ocr, keyword=%s)", metric_key, value, keyword)
                                    break
            continue
        
        # Regular table processing
        for row in rows:
            row_text = " ".join(str(cell) for cell in row if cell is not None)
            row_text_lower = row_text.lower()
            for metric_key, keywords in _METRIC_KEYWORDS.items():
                if not any(kw in row_text_lower for kw in keywords):
                    continue

                label_idx = 0
                for i, cell in enumerate(row):
                    if cell is not None and any(kw in str(cell).lower() for kw in keywords):
                        label_idx = i
                        break

                value = _extract_first_numeric_cell(row[label_idx + 1:])
                if value is None:
                    value = _extract_number_from_text(row_text)
                if value is None:
                    continue

                # Sanity check for financial values
                if not _is_valid_financial_value(value):
                    logger.debug("Skipping invalid value for %s: %s", metric_key, value)
                    continue

                # is_exact: the label cell itself matches a keyword fully
                label_cell = str(row[label_idx]).lower().strip() if row[label_idx] is not None else ""
                is_exact = any(label_cell == kw for kw in keywords)
                _raw_set(raw, metric_key, value, "table", is_exact)
                logger.debug("[EXTRACT] %s = %s (source=table, exact=%s)", metric_key, value, is_exact)

    # Pass 2: free text keyword proximity (with context window)
    text_lower = (text or "").lower()
    # Strict number pattern: groups of 1-3 digits separated by non-newline spaces
    # Prevents merging numbers from adjacent lines (OCR artifact)
    num_pattern = r"(\d{1,3}(?:[ \t\xa0]\d{3})+(?:[.,]\d+)?|\d+(?:[.,]\d+)?)"
    
    for metric_key, keywords in _METRIC_KEYWORDS.items():
        if metric_key in raw:
            continue

        # Try each keyword with context window (50 chars before number)
        for keyword in keywords:
            # Pattern: keyword followed by number within 50 chars
            pattern = rf"{keyword}[^0-9]{{0,50}}{num_pattern}"
            match = re.search(pattern, text_lower, re.IGNORECASE)
            if match:
                value = _normalize_number(match.group(1))
                if _is_valid_financial_value(value):
                    _raw_set(raw, metric_key, value, "text_regex", False)
                    logger.debug("[EXTRACT] %s = %s (source=text_regex, keyword=%s)", metric_key, value, keyword)
                    break

    # Pass 3: broad regex patterns
    broad_patterns: dict[str, list[str]] = {
        "revenue": [
            r"выручка от реализации\s*\|\s*" + num_pattern,
            r"выручка[^\d]{0,80}" + num_pattern,
        ],
        "net_profit": [
            r"чистая прибыль\s*\|\s*" + num_pattern,
            r"чистая прибыль[^\d]{0,60}" + num_pattern,
            r"прибыль после налогообложения[^\d]{0,80}" + num_pattern,
        ],
        "total_assets": [
            r"итого активов\s*\|\s*" + num_pattern,
            r"итого активов[^\d]{0,60}" + num_pattern,
            r"баланс\s*\|\s*" + num_pattern,
        ],
        "equity": [
            r"итого капитала\s*\|\s*" + num_pattern,
            r"итого капитала[^\d]{0,60}" + num_pattern,
            r"собственный капитал\s*\|\s*" + num_pattern,
            r"капитал и резервы\s*\|\s*" + num_pattern,
        ],
        "current_assets": [
            r"итого оборотных активов\s*\|\s*" + num_pattern,
            r"итого оборотных активов[^\d]{0,60}" + num_pattern,
        ],
        "short_term_liabilities": [
            r"итого краткосрочных обязательств\s*\|\s*" + num_pattern,
            r"итого краткосрочных обязательств[^\d]{0,80}" + num_pattern,
        ],
        "cost_of_goods_sold": [
            r"себестоимость продаж\s*\|\s*" + num_pattern,
            r"себестоимость продаж[^\d]{0,80}" + num_pattern,
        ],
    }
    for metric_key, pattern_list in broad_patterns.items():
        if metric_key in raw:
            continue
        for pattern in pattern_list:
            match = re.search(pattern, text_lower)
            if match:
                value = _normalize_number(match.group(1))
                if value is not None:
                    _raw_set(raw, metric_key, value, "text_regex", False)
                    break

    # Pass 4: derive missing metrics
    if "liabilities" not in raw:
        long_term = _extract_section_total(tables, text_lower, [
            "итого по разделу iv", "итого долгосрочных обязательств"
        ])
        short_term = raw["short_term_liabilities"][0] if "short_term_liabilities" in raw else None
        total_assets = raw["total_assets"][0] if "total_assets" in raw else None
        equity = raw["equity"][0] if "equity" in raw else None

        if long_term is not None and short_term is not None:
            derived = long_term + short_term
            logger.debug("Derived liabilities = IV(%s) + V(%s) = %s", long_term, short_term, derived)
            raw["liabilities"] = (derived, "derived", False)
        elif total_assets is not None and equity is not None:
            derived = total_assets - equity
            logger.debug("Derived liabilities = assets - equity = %s", derived)
            raw["liabilities"] = (derived, "derived", False)

    # Derive current_assets from known components if still missing
    if "current_assets" not in raw:
        cash = raw["cash_and_equivalents"][0] if "cash_and_equivalents" in raw else None
        inventory = raw["inventory"][0] if "inventory" in raw else None
        ar = raw["accounts_receivable"][0] if "accounts_receivable" in raw else None
        total_assets = raw["total_assets"][0] if "total_assets" in raw else None
        equity = raw["equity"][0] if "equity" in raw else None
        liabilities = raw["liabilities"][0] if "liabilities" in raw else None

        # Method 1: sum of known current components (lower bound)
        components = [v for v in [cash, inventory, ar] if v is not None]
        if len(components) >= 2:
            derived = sum(components)
            logger.debug("Derived current_assets from components = %s", derived)
            raw["current_assets"] = (derived, "derived", False)
        # Method 2: total_assets - equity - liabilities (if all known)
        elif total_assets is not None and equity is not None and liabilities is not None:
            derived = total_assets - equity - liabilities
            if derived > 0:
                logger.debug("Derived current_assets = assets - equity - liabilities = %s", derived)
                raw["current_assets"] = (derived, "derived", False)

    # Derive short_term_liabilities from liabilities if still missing
    if "short_term_liabilities" not in raw:
        liabilities = raw["liabilities"][0] if "liabilities" in raw else None
        # Try to find long-term liabilities subtotal from tables
        long_term = _extract_section_total(tables, text_lower, [
            "итого по разделу iv", "итого долгосрочных обязательств",
            "долгосрочные обязательства всего",
        ])
        if liabilities is not None and long_term is not None:
            derived = liabilities - long_term
            if derived > 0:
                logger.debug("Derived short_term_liabilities = liabilities - long_term = %s", derived)
                raw["short_term_liabilities"] = (derived, "derived", False)

    # Build final result — all keys guaranteed present
    # Apply scale_factor to monetary metrics (not ratios)
    result: dict[str, ExtractionMetadata] = {}
    for key in _METRIC_KEYWORDS:
        if key in raw:
            value, match_type, is_exact = raw[key]
            # Scale monetary values; skip ratio keys
            if scale_factor != 1.0 and key not in _RATIO_KEYS:
                value = value * scale_factor
            source, confidence = determine_source(
                match_type, is_exact=is_exact, is_derived=(match_type == "derived")
            )
            result[key] = ExtractionMetadata(value=value, confidence=confidence, source=source)
        else:
            result[key] = ExtractionMetadata(value=None, confidence=0.0, source="derived")

    return result


def parse_financial_statements(tables: list, text: str) -> dict[str, float | None]:
    metadata = parse_financial_statements_with_metadata(tables, text)
    return {k: v.value for k, v in metadata.items()}


def extract_metrics_regex(text: str) -> dict[str, float | None]:
    """
    Extract financial metrics from text using regex patterns.
    
    Fallback method when table extraction fails.
    
    Args:
        text: PDF text content
        
    Returns:
        Dictionary with metric keys and extracted values
    """
    # Strict number pattern: groups of 1-3 digits separated by non-newline spaces
    # Prevents merging numbers from adjacent lines (OCR artifact)
    num_group = r"(\d{1,3}(?:[ \t\xa0]\d{3})+(?:[.,]\d+)?|\d+(?:[.,]\d+)?)"
    
    patterns = {
        "revenue": [
            r"Выручка от реализации\s*\|\s*" + num_group,
            r"Выручка\s*\|\s*" + num_group,
            r"Выручка от реализации[^\d]{0,80}" + num_group,
            r"Выручка[^\d]{0,60}" + num_group,
            r"Доходы от реализации\s*\|\s*" + num_group,
            r"Совокупный доход\s*\|\s*" + num_group,
            r"выручка.*?(\d+(?:[\s\xa0]?\d+)*(?:[.,]\d+)?)",
        ],
        "net_profit": [
            r"Чистая прибыль\s*\|\s*" + num_group,
            r"Чистая прибыль[^\d]{0,60}" + num_group,
            r"Прибыль после налогообложения\s*\|\s*" + num_group,
            r"Нераспределенная прибыль\s*\|\s*" + num_group,
            r"чистая прибыль.*?(\d+(?:[\s\xa0]?\d+)*(?:[.,]\d+)?)",
        ],
        "total_assets": [
            r"Итого активов\s*\|\s*" + num_group,
            r"Итого активов[^\d]{0,60}" + num_group,
            r"БАЛАНС\s*\|\s*" + num_group,
            r"БАЛАНС[^\d]{0,60}" + num_group,
            r"актив[аыо].*?(\d+(?:[\s\xa0]?\d+)*(?:[.,]\d+)?)",
        ],
        "equity": [
            r"Итого капитала\s*\|\s*" + num_group,
            r"Итого капитала[^\d]{0,60}" + num_group,
            r"Собственный капитал\s*\|\s*" + num_group,
            r"Капитал и резервы\s*\|\s*" + num_group,
            r"Итого по разделу III\s*\|\s*" + num_group,
            r"капитал[ауоы].*?(\d+(?:[\s\xa0]?\d+)*(?:[.,]\d+)?)",
        ],
        "liabilities": [
            r"Итого обязательств\s*\|\s*" + num_group,
            r"Итого обязательств[^\d]{0,60}" + num_group,
            r"Итого долгосрочных обязательств\s*\|\s*" + num_group,
            r"Итого краткосрочных обязательств\s*\|\s*" + num_group,
            r"обязательств[ауы].*?(\d+(?:[\s\xa0]?\d+)*(?:[.,]\d+)?)",
        ],
        "current_assets": [
            r"Итого оборотных активов\s*\|\s*" + num_group,
            r"Итого оборотных активов[^\d]{0,60}" + num_group,
            r"Оборотные активы\s*\|\s*" + num_group,
            r"Итого по разделу II\s*\|\s*" + num_group,
            r"оборотн[ыыхи].*?(\d+(?:[\s\xa0]?\d+)*(?:[.,]\d+)?)",
        ],
        "short_term_liabilities": [
            r"Итого краткосрочных обязательств\s*\|\s*" + num_group,
            r"Итого краткосрочных обязательств[^\d]{0,80}" + num_group,
            r"Краткосрочные обязательства\s*\|\s*" + num_group,
            r"Итого по разделу V\s*\|\s*" + num_group,
            r"краткосрочн[ыыхи].*?(\d+(?:[\s\xa0]?\d+)*(?:[.,]\d+)?)",
        ],
        "accounts_receivable": [
            r"Дебиторская задолженность\s*\|\s*" + num_group,
            r"Дебиторская задолженность[^\d]{0,60}" + num_group,
            r"задолженност[ьи].*?(\d+(?:[\s\xa0]?\d+)*(?:[.,]\d+)?)",
        ],
        "inventory": [
            r"Запасы\s*\|\s*" + num_group,
            r"Запасы[^\d]{0,60}" + num_group,
            r"Товарно-материальные ценности\s*\|\s*" + num_group,
            r"запас[аыов].*?(\d+(?:[\s\xa0]?\d+)*(?:[.,]\d+)?)",
        ],
        "cash_and_equivalents": [
            r"Денежные средства\s*\|\s*" + num_group,
            r"Денежные средства[^\d]{0,60}" + num_group,
            r"Наличные\s*\|\s*" + num_group,
            r"денежн[ыыхи].*?(\d+(?:[\s\xa0]?\d+)*(?:[.,]\d+)?)",
        ],
        "ebitda": [
            r"EBITDA\s*\|\s*" + num_group,
            r"EBITDA[^\d]{0,60}" + num_group,
            r"ebitda.*?(\d+(?:[\s\xa0]?\d+)*(?:[.,]\d+)?)",
        ],
        "ebit": [
            r"EBIT\s*\|\s*" + num_group,
            r"EBIT[^\d]{0,60}" + num_group,
            r"Операционная прибыль\s*\|\s*" + num_group,
            r"операционн[аыя].*?(\d+(?:[\s\xa0]?\d+)*(?:[.,]\d+)?)",
        ],
        "interest_expense": [
            r"Процентные расходы\s*\|\s*" + num_group,
            r"Процентные расходы[^\d]{0,60}" + num_group,
            r"процентн[ыыхи].*?(\d+(?:[\s\xa0]?\d+)*(?:[.,]\d+)?)",
        ],
        "cost_of_goods_sold": [
            r"Себестоимость продаж\s*\|\s*" + num_group,
            r"Себестоимость продаж[^\d]{0,80}" + num_group,
            r"Себестоимость реализованной продукции\s*\|\s*" + num_group,
            r"себестоимост[ьи].*?(\d+(?:[\s\xa0]?\d+)*(?:[.,]\d+)?)",
        ],
        "average_inventory": [
            r"Средний запас\s*\|\s*" + num_group,
            r"Средний запас[^\d]{0,60}" + num_group,
            r"средн.*?запас[аы].*?(\d+(?:[\s\xa0]?\d+)*(?:[.,]\d+)?)",
        ],
    }
    
    metrics: dict[str, float | None] = {}
    text_lower = text.lower()
    
    for field, pattern_list in patterns.items():
        for pattern in pattern_list:
            match = re.search(pattern, text_lower, re.IGNORECASE)
            if match:
                value = _normalize_number(match.group(1))
                if _is_valid_financial_value(value):
                    metrics[field] = value
                    break
    
    return metrics


def _extract_first_numeric_cell(cells: list) -> float | None:
    """Return the first parseable numeric value from a list of cells.

    Skips cells that look like row/line codes in financial statements:
    - Pure digit strings of 1–4 characters (e.g. "66", "110", "2110")
    - Values < 1 that are likely percentages or ratios stored as row metadata
    """
    for cell in cells:
        if cell is None:
            continue
        cell_str = str(cell).strip()
        if not cell_str or not any(c.isdigit() for c in cell_str):
            continue
        digits_only = cell_str.replace(" ", "").replace("\xa0", "")
        # Skip pure digit strings of 1–3 chars — these are row codes (e.g. 66, 110)
        # 4-digit strings (e.g. 1000, 9999) are valid financial values in thousands of rubles
        if digits_only.isdigit() and len(digits_only) <= 3:
            continue
        value = _normalize_number(cell_str)
        if value is not None:
            return value
    return None


def _extract_section_total(tables: list, text_lower: str, keywords: list[str]) -> float | None:
    """Extract a section total value by keywords from tables or text."""
    for table in tables or []:
        rows = _table_to_rows(table)
        for row in rows:
            row_text_lower = " ".join(str(c) for c in row if c is not None).lower()
            if any(kw in row_text_lower for kw in keywords):
                val = _extract_first_numeric_cell(row[1:])
                if val is not None:
                    return val
    for kw in keywords:
        pattern = re.compile(rf"{re.escape(kw)}[^0-9\-]{{0,40}}([-]?\(?\d[\d\s.,]*\d\)?)")
        m = pattern.search(text_lower)
        if m:
            val = _normalize_number(m.group(1))
            if val is not None:
                return val
    return None


def _table_to_rows(table: Any) -> list[list[Any]]:
    # Check if it's a pandas DataFrame (camelot table)
    try:
        import pandas as pd

        if isinstance(table, pd.DataFrame):
            return table.values.tolist()
    except (ImportError, AttributeError):
        pass

    # Handle dict with "rows" key
    if isinstance(table, dict) and "rows" in table:
        rows = table.get("rows")
        if isinstance(rows, list):
            return rows

    # Handle plain list structures
    if isinstance(table, list):
        if not table:
            return []
        if isinstance(table[0], dict):
            return [list(row.values()) for row in table]
        if isinstance(table[0], list):
            return table

    return []


def _extract_number_from_text(text: str) -> float | None:
    matches = _NUMBER_PATTERN.findall(text)
    if not matches:
        return None
    return _normalize_number(matches[-1])


def _extract_number_near_keywords(text: str, keywords: list[str]) -> float | None:
    for keyword in keywords:
        pattern = re.compile(
            rf"{re.escape(keyword)}[^0-9\-]{{0,40}}([-]?\(?\d[\d\s.,]*\d\)?)"
        )
        match = pattern.search(text)
        if match:
            return _normalize_number(match.group(1))
    return None


def _normalize_number(raw_value: str) -> float | None:
    if raw_value is None:
        return None

    # Handle all negative number formats used in Russian financial reports:
    # (123) — accounting parentheses, −123 — Unicode minus U+2212, -123 — ASCII minus
    negative = (
        ("(" in raw_value and ")" in raw_value)
        or raw_value.strip().startswith(("\u2212", "-"))
        or raw_value.strip().endswith("\u2212")
    )
    # Strip only non-newline whitespace to avoid merging numbers from different lines
    cleaned = raw_value.replace("\u00a0", "").replace(" ", "").replace("\t", "")
    # Replace Unicode minus with ASCII minus before stripping non-numeric chars
    cleaned = cleaned.replace("\u2212", "-")
    cleaned = cleaned.replace(",", ".")
    cleaned = re.sub(r"[^0-9.\-]", "", cleaned)
    cleaned = cleaned.strip()

    if cleaned in {"", "-", "."}:
        return None

    # Guard: if cleaned string has more than 16 digits it's almost certainly a parsing artifact
    # (largest real financial value ~1e13 has at most 14 digits for Russian companies)
    digit_count = sum(c.isdigit() for c in cleaned)
    if digit_count > 16:
        return None

    try:
        value = float(cleaned)
    except ValueError:
        return None

    if negative:
        return -abs(value)

    return value
