import logging
import os
import re
from dataclasses import dataclass
from typing import Any, Literal

import camelot
from pdf2image import convert_from_path
import PyPDF2
import pytesseract

# Configure Tesseract path for Windows
_tesseract_path = os.path.expandvars(r"C:\Program Files\Tesseract-OCR\tesseract.exe")
if os.path.exists(_tesseract_path):
    pytesseract.pytesseract.tesseract_cmd = _tesseract_path
    os.environ["TESSDATA_PREFIX"] = os.path.expandvars(
        r"C:\Program Files\Tesseract-OCR\tessdata"
    )

logger = logging.getLogger(__name__)

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


# ---------------------------------------------------------------------------

_NUMBER_PATTERN = re.compile(r"[-(]?\d[\d\s.,]*\d|\d")

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


def is_scanned_pdf(pdf_path: str) -> bool:
    try:
        reader = PyPDF2.PdfReader(pdf_path)
        pages = reader.pages[: min(3, len(reader.pages))]
        text_parts = []
        for page in pages:
            try:
                text_parts.append(page.extract_text() or "")
            except Exception as exc:
                logger.warning("Failed to extract text from page: %s", exc)
        text = "".join(text_parts).strip()
        return len(text) < 50
    except Exception as exc:
        logger.exception("Failed to check PDF for text: %s", exc)
        return True


def extract_text_from_scanned(pdf_path: str) -> str:
    try:
        images = convert_from_path(pdf_path)
    except Exception as exc:
        logger.exception("Failed to convert PDF to images: %s", exc)
        raise

    texts: list[str] = []
    for page_index, image in enumerate(images, start=1):
        try:
            try:
                page_text = pytesseract.image_to_string(image, lang="rus+eng")
            except pytesseract.TesseractError:
                page_text = pytesseract.image_to_string(image)
            texts.append(page_text)
        except Exception as exc:
            logger.warning("OCR failed on page %s: %s", page_index, exc)

    return "\n".join(texts).strip()


def extract_tables(pdf_path: str) -> list[dict[str, Any]]:
    tables_data: list[dict[str, Any]] = []

    for flavor in ("lattice", "stream"):
        try:
            tables = camelot.read_pdf(pdf_path, pages="all", flavor=flavor)
        except Exception as exc:
            logger.warning("Camelot failed with flavor=%s: %s", flavor, exc)
            continue

        if tables and tables.n > 0:
            for table in tables:
                df = table.df
                if df is None or df.empty:
                    continue
                tables_data.append(
                    {
                        "flavor": flavor,
                        "rows": df.values.tolist(),
                    }
                )

        if tables_data:
            break

    return tables_data


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

    # Pass 1: tables
    for table in tables or []:
        rows = _table_to_rows(table)
        for row in rows:
            row_text = " ".join(str(cell) for cell in row if cell is not None)
            row_text_lower = row_text.lower()
            for metric_key, keywords in _METRIC_KEYWORDS.items():
                if metric_key in raw:
                    continue
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

                # is_exact: the label cell itself matches a keyword fully
                label_cell = str(row[label_idx]).lower().strip() if row[label_idx] is not None else ""
                is_exact = any(label_cell == kw for kw in keywords)
                raw[metric_key] = (value, "table", is_exact)

    # Pass 2: free text keyword proximity
    text_lower = (text or "").lower()
    for metric_key, keywords in _METRIC_KEYWORDS.items():
        if metric_key in raw:
            continue
        value = _extract_number_near_keywords(text_lower, keywords)
        if value is not None:
            raw[metric_key] = (value, "text_regex", False)

    # Pass 3: broad regex patterns
    num_group = r"([-]?\(?\d[\d\s.,]*\d\)?)"
    broad_patterns: dict[str, list[str]] = {
        "revenue": [
            r"выручка от реализации\s*\|\s*" + num_group,
            r"выручка[^\d]{0,80}" + num_group,
        ],
        "net_profit": [
            r"чистая прибыль\s*\|\s*" + num_group,
            r"чистая прибыль[^\d]{0,60}" + num_group,
            r"прибыль после налогообложения[^\d]{0,80}" + num_group,
        ],
        "total_assets": [
            r"итого активов\s*\|\s*" + num_group,
            r"итого активов[^\d]{0,60}" + num_group,
            r"баланс\s*\|\s*" + num_group,
        ],
        "equity": [
            r"итого капитала\s*\|\s*" + num_group,
            r"итого капитала[^\d]{0,60}" + num_group,
            r"собственный капитал\s*\|\s*" + num_group,
            r"капитал и резервы\s*\|\s*" + num_group,
        ],
        "current_assets": [
            r"итого оборотных активов\s*\|\s*" + num_group,
            r"итого оборотных активов[^\d]{0,60}" + num_group,
        ],
        "short_term_liabilities": [
            r"итого краткосрочных обязательств\s*\|\s*" + num_group,
            r"итого краткосрочных обязательств[^\d]{0,80}" + num_group,
        ],
        "cost_of_goods_sold": [
            r"себестоимость продаж\s*\|\s*" + num_group,
            r"себестоимость продаж[^\d]{0,80}" + num_group,
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
                    raw[metric_key] = (value, "text_regex", False)
                    break

    # Pass 4: derive liabilities if still missing
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

    # Build final result — all keys guaranteed present
    result: dict[str, ExtractionMetadata] = {}
    for key in _METRIC_KEYWORDS:
        if key in raw:
            value, match_type, is_exact = raw[key]
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


def _extract_first_numeric_cell(cells: list) -> float | None:
    """Return the first parseable numeric value from a list of cells, skipping 4-digit row codes."""
    for cell in cells:
        if cell is None:
            continue
        cell_str = str(cell).strip()
        if not cell_str or not any(c.isdigit() for c in cell_str):
            continue
        digits_only = cell_str.replace(" ", "").replace("\xa0", "")
        if digits_only.isdigit() and len(digits_only) == 4:
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

    negative = "(" in raw_value and ")" in raw_value
    cleaned = raw_value.replace("\u00a0", "").replace(" ", "").replace("\t", "")
    cleaned = cleaned.replace(",", ".")
    cleaned = re.sub(r"[^0-9.\-]", "", cleaned)

    if cleaned in {"", "-", "."}:
        return None

    try:
        value = float(cleaned)
    except ValueError:
        return None

    if negative:
        return -abs(value)

    return value
