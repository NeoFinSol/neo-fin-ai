import logging
import re
from typing import Any

import camelot
from pdf2image import convert_from_path
import PyPDF2
import pytesseract

logger = logging.getLogger(__name__)

_NUMBER_PATTERN = re.compile(r"[-(]?\d[\d\s.,]*\d|\d")

_METRIC_KEYWORDS = {
    "revenue": [
        "выручка",
        "выручка от реализации",
        "revenue",
        "sales revenue",
        "net sales",
    ],
    "net_profit": [
        "чистая прибыль",
        "net profit",
        "profit for the year",
        "profit (loss)",
    ],
    "total_assets": [
        "итого активы",
        "активы всего",
        "total assets",
    ],
    "equity": [
        "капитал",
        "собственный капитал",
        "total equity",
        "equity",
    ],
    "liabilities": [
        "обязательства",
        "итого обязательства",
        "total liabilities",
        "liabilities",
    ],
    "current_assets": [
        "оборотные активы",
        "current assets",
    ],
    "short_term_liabilities": [
        "краткосрочные обязательства",
        "short-term liabilities",
        "current liabilities",
    ],
    "accounts_receivable": [
        "дебиторская задолженность",
        "accounts receivable",
        "trade receivables",
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
                tables_data.append({
                    "flavor": flavor,
                    "rows": df.values.tolist(),
                })

        if tables_data:
            break

    return tables_data


def parse_financial_statements(tables: list, text: str) -> dict[str, float | None]:
    metrics: dict[str, float | None] = {key: None for key in _METRIC_KEYWORDS}

    for table in tables or []:
        rows = _table_to_rows(table)
        for row in rows:
            row_text = " ".join(str(cell) for cell in row if cell is not None)
            row_text_lower = row_text.lower()
            for metric_key, keywords in _METRIC_KEYWORDS.items():
                if metrics[metric_key] is not None:
                    continue
                if any(keyword in row_text_lower for keyword in keywords):
                    value = _extract_number_from_text(row_text)
                    if value is not None:
                        metrics[metric_key] = value

    text_lower = (text or "").lower()
    for metric_key, keywords in _METRIC_KEYWORDS.items():
        if metrics[metric_key] is not None:
            continue
        value = _extract_number_near_keywords(text_lower, keywords)
        if value is not None:
            metrics[metric_key] = value

    return metrics


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
        pattern = re.compile(rf"{re.escape(keyword)}[^0-9\-]{{0,40}}([-]?\(?\d[\d\s.,]*\d\)?)")
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
