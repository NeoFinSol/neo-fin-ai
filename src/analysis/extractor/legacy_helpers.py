import logging
import os
import re
from dataclasses import dataclass
from typing import Any, Literal

import camelot
import PyPDF2
import pytesseract
from pdf2image import convert_from_path
from pytesseract import Output

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
            "CONFIDENCE_THRESHOLD=%s out of [0.0, 1.0], using default 0.5",
            _RAW_THRESHOLD,
        )
        CONFIDENCE_THRESHOLD = 0.5
except ValueError:
    logger.warning(
        "CONFIDENCE_THRESHOLD=%r is not a valid float, using default 0.5",
        _RAW_THRESHOLD,
    )
    CONFIDENCE_THRESHOLD = 0.5

# ---------------------------------------------------------------------------
# Extraction metadata types
# ---------------------------------------------------------------------------

ExtractionSource = Literal[
    "table_exact", "table_partial", "text_regex", "derived", "issuer_fallback"
]


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
    if match_type == "derived_strong":
        return ("derived", 0.6)
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

# Matches financial numbers with non-newline thousand separators.
# Supports spaces/NBSP, commas and dots as grouping chars while still avoiding
# cross-line OCR merges.
_NUMBER_PATTERN = re.compile(
    r"[-(]?\$?\d{1,3}(?:,\d{3})+(?:\.\d+)?\)?"
    r"|[-(]?\$?\d{1,3}(?:[ \t\xa0]\d{3})+(?:[.,]\d+)?\)?"
    r"|[-(]?\$?\d{1,3}(?:\.\d{3})+(?:,\d+)?\)?"
    r"|[-(]?\$?\d+(?:[.,]\d+)?\)?"
)
_OCR_NUMBER_PATTERN = re.compile(
    r"[-(]?\$?\d{1,4}(?:[ \t\xa0]\d{3})+(?:[.,]\d+)?\)?"
    r"|[-(]?\$?\d{1,3}(?:,\d{3})+(?:\.\d+)?\)?"
    r"|[-(]?\$?\d{1,3}(?:\.\d{3})+(?:,\d+)?\)?"
    r"|[-(]?\$?\d+(?:[.,]\d+)?\)?"
)
_NUMBER_REGEX_FRAGMENT = (
    r"[-(]?\$?\d{1,3}(?:,\d{3})+(?:\.\d+)?\)?"
    r"|[-(]?\$?\d{1,3}(?:[ \t\xa0]\d{3})+(?:[.,]\d+)?\)?"
    r"|[-(]?\$?\d{1,3}(?:\.\d{3})+(?:,\d+)?\)?"
    r"|[-(]?\$?\d+(?:[.,]\d+)?\)?"
)

_METRIC_KEYWORDS = {
    "revenue": [
        # RSBU/IFRS Russian
        "выручка от реализации",
        "выручка",
        "доходы от реализации",
        "доход от продаж",
        "совокупный доход",
        "выручка от продаж",
        # IFRS English
        "revenues",
        "revenue",
        "total revenues",
        "total revenue",
        "sales revenue",
        "net sales",
        "turnover",
        # IFRS consolidated
        "консолидированная выручка",
        "consolidated revenue",
    ],
    "net_profit": [
        # RSBU/IFRS Russian
        "чистая прибыль (убыток)",
        "чистая прибыль",
        "чистый убыток",
        "прибыль за период",
        "прибыль за год",
        "прибыль после налогообложения",
        "чистая прибыль за год",
        "чистая прибыль за период",
        "совокупный финансовый результат",
        # IFRS English
        "net profit",
        "net income",
        "net loss",
        "profit for the year",
        "profit for the period",
        "profit (loss)",
        "profit for the year attributable to",
        "net profit attributable to",
        # IFRS consolidated
        "чистая прибыль, относящаяся к акционерам",
        "net profit attributable to owners",
    ],
    "total_assets": [
        # RSBU/IFRS Russian
        "итого активов",
        "итого активы",
        "активы всего",
        "активов всего",
        "баланс",
        "внеоборотные и оборотные активы",
        # IFRS English
        "total assets",
        "assets total",
        "total non-current and current assets",
        # IFRS consolidated
        "консолидированные активы",
        "consolidated total assets",
    ],
    "equity": [
        # RSBU/IFRS Russian
        "итого по разделу iii",
        "итого капитала",
        "капитал и резервы",
        "собственный капитал",
        "капитал",
        "итого капитал",
        "капитала всего",
        # IFRS English
        "total stockholders' equity",
        "stockholders' equity",
        "total stockholders' equity",
        "stockholders' equity",
        "total shareholders' equity",
        "shareholders' equity",
        "total shareholders' equity",
        "shareholders' equity",
        "total equity",
        "equity total",
        "equity attributable to owners",
        "капитал, относящийся к акционерам",
        # IFRS consolidated
        "капитал и резервы, относящиеся к акционерам",
        "total equity attributable to",
    ],
    "liabilities": [
        # RSBU/IFRS Russian
        "итого обязательств",
        "обязательства всего",
        "долгосрочные и краткосрочные обязательства",
        # IFRS English
        "total liabilities",
        "liabilities total",
        "total non-current and current liabilities",
        # IFRS consolidated
        "консолидированные обязательства",
    ],
    "current_assets": [
        # RSBU/IFRS Russian
        "итого оборотных активов",
        "итого оборотные активы",
        "оборотные активы всего",
        "итого по разделу ii",
        "оборотные активы",
        # IFRS English
        "total current assets",
        "current assets total",
        # IFRS consolidated
        "консолидированные оборотные активы",
    ],
    "short_term_liabilities": [
        # RSBU/IFRS Russian
        "итого краткосрочных обязательств",
        "итого краткосрочные обязательства",
        "краткосрочные обязательства всего",
        "итого по разделу v",
        "итого по разделу у",
        "краткосрочные обязательства",
        # IFRS English
        "total current liabilities",
        "current liabilities total",
        "short-term liabilities",
        # IFRS consolidated
        "консолидированные краткосрочные обязательства",
    ],
    "accounts_receivable": [
        # RSBU/IFRS Russian
        "дебиторская задолженность",
        "торговая дебиторская задолженность",
        "краткосрочная дебиторская задолженность",
        # IFRS English
        "accounts receivable",
        "trade receivables",
        "trade and other receivables",
        "current receivables",
        # IFRS consolidated
        "торговая и прочая дебиторская задолженность",
    ],
    # ===== NEW FIELDS FOR EXTENDED RATIOS =====
    "inventory": [
        # RSBU/IFRS Russian
        "запасы",
        "товарно-материальные ценности",
        "запасы и затраты",
        "производственные запасы",
        # IFRS English
        "inventory",
        "merchandise",
        "stocks",
        "inventories",
    ],
    "cash_and_equivalents": [
        # RSBU/IFRS Russian
        "денежные средства",
        "наличные",
        "денежные средства и эквиваленты",
        # IFRS English
        "cash and equivalents",
        "cash and cash equivalents",
        "cash",
        "cash at bank and in hand",
    ],
    "ebitda": [
        # RSBU/IFRS Russian
        "ebitda",
        "ebit до амортизации",
        "показатель ebitda",
        # IFRS English
        "ebitda",
        "earnings before interest, taxes, depreciation and amortization",
    ],
    "ebit": [
        # RSBU/IFRS Russian
        "ebit",
        "операционная прибыль",
        "прибыль от операций",
        "прибыль от операционной деятельности",
        # IFRS English
        "ebit",
        "operating profit",
        "profit from operations",
        "operating income",
    ],
    "interest_expense": [
        # RSBU/IFRS Russian
        "финансовые расходы",
        "процентные расходы",
        "процентные платежи",
        "расходы по процентам",
        # IFRS English
        "interest expense",
        "interest paid",
        "finance costs",
        "finance expenses",
        "interest and similar charges",
    ],
    "cost_of_goods_sold": [
        # RSBU/IFRS Russian
        "себестоимость продаж",
        "себестоимость",
        "коммерческие расходы",
        # IFRS English
        "cost of goods sold",
        "cogs",
        "cost of sales",
        "direct costs",
    ],
    "average_inventory": [
        # RSBU/IFRS Russian
        "средний запас",
        "средний остаток запасов",
        # IFRS English
        "average inventory",
        "average stocks",
    ],
    "short_term_borrowings": [
        "краткосрочные кредиты и займы",
        "краткосрочные заемные средства",
        "short-term borrowings",
        "current borrowings",
    ],
    "long_term_borrowings": [
        "долгосрочные кредиты и займы",
        "долгосрочные заемные средства",
        "long-term borrowings",
        "non-current borrowings",
    ],
    "short_term_lease_liabilities": [
        "краткосрочные обязательства по аренде",
        "краткосрочная аренда",
        "short-term lease liabilities",
        "current lease liabilities",
    ],
    "long_term_lease_liabilities": [
        "долгосрочные обязательства по аренде",
        "долгосрочная аренда",
        "long-term lease liabilities",
        "non-current lease liabilities",
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
                logger.warning(
                    "Failed to extract text from page %s: %s", page_index, exc
                )
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
    glyph_tokens = sum(1 for t in tokens if _re.fullmatch(r"/\d+", t))
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
                if "/XObject" in page["/Resources"]:
                    xobjs = page["/Resources"]["/XObject"].get_object()
                    for obj_name in xobjs:
                        if xobjs[obj_name]["/Subtype"] == "/Image":
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

        if not single_page_batch and len(images) > MAX_OCR_PAGES:
            logger.warning(
                "OCR fallback batch exceeded page limit (%d > %d), truncating",
                len(images),
                MAX_OCR_PAGES,
            )
            images = images[:MAX_OCR_PAGES]

        for offset, image in enumerate(images):
            current_page = page_num + offset
            try:
                try:
                    page_text = pytesseract.image_to_string(image, lang="rus+eng")
                except pytesseract.TesseractError:
                    page_text = pytesseract.image_to_string(image)
                layout_totals = _extract_layout_section_total_lines(image, page_text)
                layout_metric_lines: list[str] = []
                if _should_run_layout_metric_row_crop(page_text):
                    layout_metric_lines = _extract_layout_metric_value_lines(
                        image, page_text
                    )
                synthesized_layout_lines = [*layout_totals, *layout_metric_lines]
                if synthesized_layout_lines:
                    page_text = "\n".join([page_text, *synthesized_layout_lines])
                texts.append(page_text)
            except Exception as exc:
                logger.warning("OCR failed on page %d: %s", current_page, exc)

        del images
        gc.collect()

        if single_page_batch:
            aggregated_text = "\n".join(texts)
            if _should_stop_scanned_ocr(aggregated_text, current_page):
                logger.info(
                    "OCR stopped early after %d pages due to sufficient financial signal",
                    current_page,
                )
                break

        if not single_page_batch:
            break

        page_num += 1

    return "\n".join(texts).strip()


def _extract_layout_section_total_lines(image: object, page_text: str) -> list[str]:
    text_lower = (page_text or "").lower()
    if "итого по разделу" not in text_lower:
        return []

    try:
        data = pytesseract.image_to_data(image, lang="rus+eng", output_type=Output.DICT)
    except Exception:
        return []

    row_map: dict[tuple[int, int, int], dict[str, object]] = {}
    for i, raw_text in enumerate(data.get("text", [])):
        token = (raw_text or "").strip()
        if not token:
            continue
        key = (data["block_num"][i], data["par_num"][i], data["line_num"][i])
        row = row_map.setdefault(key, {"tokens": [], "top": data["top"][i]})
        row["tokens"].append((data["left"][i], token))
        row["top"] = min(int(row["top"]), int(data["top"][i]))

    marker_rows: list[tuple[str, int]] = []
    for row in row_map.values():
        tokens = sorted(row["tokens"], key=lambda x: x[0])
        line_text = " ".join(token for _, token in tokens)
        if "итого по разделу" in line_text.lower():
            marker_rows.append((line_text, int(row["top"])))

    synthesized: list[str] = []
    seen: set[str] = set()
    for marker_text, top in marker_rows:
        near_numbers: list[tuple[int, str]] = []
        for i, raw_text in enumerate(data.get("text", [])):
            token = (raw_text or "").strip()
            if not token or not any(ch.isdigit() for ch in token):
                continue
            token_top = int(data["top"][i])
            if abs(token_top - top) > 18:
                continue
            near_numbers.append((int(data["left"][i]), token))

        if not near_numbers:
            continue

        near_numbers.sort(key=lambda x: x[0])
        synthesized_line = (
            f"{marker_text} {' '.join(token for _, token in near_numbers)}"
        )
        if synthesized_line not in seen:
            synthesized.append(synthesized_line)
            seen.add(synthesized_line)

    return synthesized


_LAYOUT_BALANCE_ROW_SPECS: tuple[tuple[str, tuple[str, ...], str, int, bool], ...] = (
    (
        "1200",
        ("итого по разделу п", "итого по разделу ii"),
        "Итого по разделу П",
        3,
        False,
    ),
    ("1210", ("запас",), "Запасы", 2, False),
    ("1230", ("дебитор",), "Дебиторская задолженность", 2, False),
    ("1250", ("денежн",), "Денежные средства", 2, False),
    ("1400", ("итого по разделу iv", "долгосрочн"), "Итого по разделу IV", 3, True),
    (
        "1500",
        ("итого по разделу v", "итого по разделу у", "краткосрочн"),
        "Итого по разделу V",
        3,
        True,
    ),
)


_LAYOUT_ROW_SIGNAL_TOKENS = (
    "1200",
    "1210",
    "1230",
    "1250",
    "1400",
    "1500",
    "итого по разделу п",
    "итого по разделу ii",
    "итого по разделу iv",
    "итого по разделу v",
    "итого по разделу у",
    "запас",
    "дебитор",
    "денежн",
    "долгосрочн",
    "краткосрочн",
)

_P_AND_L_SECTION_MARKERS = (
    "отчет о финансовых результатах",
    "отчёт о финансовых результатах",
    "statement of income",
    "statement of profit",
)

_P_AND_L_SECTION_END_MARKERS = (
    "бухгалтерский баланс",
    "отчет об изменениях капитала",
    "отчёт об изменениях капитала",
    "отчет о движении денежных средств",
    "отчёт о движении денежных средств",
    "statement of changes in equity",
    "statement of cash flows",
    "руководитель",
)


def _should_run_layout_metric_row_crop(page_text: str) -> bool:
    text_lower = (page_text or "").lower()
    if "бухгалтерский баланс" in text_lower:
        return True
    if "итого по разделу" not in text_lower:
        return False
    return any(token in text_lower for token in _LAYOUT_ROW_SIGNAL_TOKENS)


def _extract_ocr_row_value_tail(
    image: object,
    row_left: int,
    row_top: int,
    row_right: int,
    row_bottom: int,
    expected_code: str | None = None,
    require_code_match: bool = False,
) -> str | None:
    image_size = getattr(image, "size", None)
    if not image_size or len(image_size) != 2:
        return None

    width, height = image_size
    x0 = max(int(width * 0.45), int(row_right + 16), int(row_left + width * 0.05))
    x1 = min(width, int(width * 0.995))
    y0 = max(0, row_top - 10)
    y1 = min(height, row_bottom + 18)
    if x1 <= x0 or y1 <= y0:
        return None

    try:
        cropped = image.crop((x0, y0, x1, y1))
    except Exception:
        return None

    ocr_configs = (
        "--psm 6 -c tessedit_char_whitelist=0123456789,.-() ",
        "--psm 7 -c tessedit_char_whitelist=0123456789,.-() ",
        "--psm 11 -c tessedit_char_whitelist=0123456789,.-() ",
    )
    best_candidate: str | None = None
    best_score = -1
    for config in ocr_configs:
        try:
            raw = pytesseract.image_to_string(cropped, lang="rus+eng", config=config)
        except Exception:
            continue

        digit_groups = re.findall(r"\d+", raw or "")
        if expected_code:
            if digit_groups and digit_groups[0] == expected_code:
                digit_groups = digit_groups[1:]
            elif require_code_match:
                continue
        while len(digit_groups) >= 3 and len(digit_groups[-1]) == 1:
            digit_groups = digit_groups[:-1]
        if not digit_groups:
            continue

        candidate = _split_grouped_period_values(" ".join(digit_groups))
        value = _normalize_number(candidate)
        if value is None or abs(value) < 1000:
            continue
        if _is_valid_financial_value(value):
            digit_count = len("".join(ch for ch in candidate if ch.isdigit()))
            score = digit_count
            if score > best_score:
                best_candidate = candidate
                best_score = score

    return best_candidate


def _extract_layout_metric_value_lines(image: object, page_text: str) -> list[str]:
    if not _should_run_layout_metric_row_crop(page_text):
        return []

    try:
        data = pytesseract.image_to_data(image, lang="rus+eng", output_type=Output.DICT)
    except Exception:
        return []

    row_map: dict[tuple[int, int, int], dict[str, object]] = {}
    for i, raw_text in enumerate(data.get("text", [])):
        token = (raw_text or "").strip()
        if not token:
            continue
        key = (data["block_num"][i], data["par_num"][i], data["line_num"][i])
        left = int(data["left"][i])
        top = int(data["top"][i])
        width = int(data["width"][i])
        height = int(data["height"][i])

        row = row_map.setdefault(
            key,
            {
                "tokens": [],
                "left": left,
                "right": left + width,
                "top": top,
                "bottom": top + height,
            },
        )
        row["tokens"].append((left, token))
        row["left"] = min(int(row["left"]), left)
        row["right"] = max(int(row["right"]), left + width)
        row["top"] = min(int(row["top"]), top)
        row["bottom"] = max(int(row["bottom"]), top + height)

    prepared_rows: list[dict[str, int | str]] = []
    for row in row_map.values():
        tokens = sorted(row["tokens"], key=lambda x: x[0])
        line_text = " ".join(token for _, token in tokens)
        if not line_text:
            continue
        prepared_rows.append(
            {
                "line": line_text,
                "lower": line_text.lower(),
                "left": int(row["left"]),
                "right": int(row["right"]),
                "top": int(row["top"]),
                "bottom": int(row["bottom"]),
            }
        )

    synthesized: list[str] = []
    seen: set[str] = set()
    max_attempts_per_spec = 4
    max_row_crop_attempts_per_page = 14
    row_crop_attempts = 0
    for (
        expected_code,
        markers,
        label,
        min_groups,
        require_code_match,
    ) in _LAYOUT_BALANCE_ROW_SPECS:
        if row_crop_attempts >= max_row_crop_attempts_per_page:
            break
        candidate_rows = [
            row
            for row in prepared_rows
            if any(marker in str(row["lower"]) for marker in markers)
        ]
        if require_code_match:
            candidate_rows = [
                row for row in candidate_rows if expected_code in str(row["lower"])
            ]
        if not candidate_rows:
            continue

        candidate_rows.sort(
            key=lambda row: (
                0 if expected_code in str(row["lower"]) else 1,
                int(row["top"]),
            )
        )

        for row in candidate_rows[:max_attempts_per_spec]:
            if row_crop_attempts >= max_row_crop_attempts_per_page:
                break
            row_crop_attempts += 1
            numeric_tail = _extract_ocr_row_value_tail(
                image,
                row_left=int(row["left"]),
                row_top=int(row["top"]),
                row_right=int(row["right"]),
                row_bottom=int(row["bottom"]),
                expected_code=expected_code,
                require_code_match=require_code_match,
            )
            if not numeric_tail:
                continue
            if len(re.findall(r"\d+", numeric_tail)) < min_groups:
                continue

            synthesized_line = f"{label} {numeric_tail}"
            if synthesized_line in seen:
                continue
            synthesized.append(synthesized_line)
            seen.add(synthesized_line)
            break

    return synthesized


def _should_stop_scanned_ocr(text: str, processed_pages: int) -> bool:
    """Stop OCR early when core financial statements are already captured."""
    if processed_pages < 5:
        return False

    text_lower = text.lower()
    balance_markers = (
        "бухгалтерский баланс",
        "отчет о финансовом положении",
        "balance sheet",
    )
    results_markers = (
        "отчет о финансовых результатах",
        "отчет о прибыли и убытке",
        "statement of income",
        "statements of operations",
    )
    financial_tokens = (
        "1600",
        "1200",
        "1250",
        "2110",
        "2400",
        "выручка",
        "чистая прибыль",
        "итого по разделу",
    )
    has_balance = any(marker in text_lower for marker in balance_markers)
    has_results = any(marker in text_lower for marker in results_markers)
    token_hits = sum(1 for token in financial_tokens if token in text_lower)
    has_liabilities = (
        "1700" in text_lower
        or ("1400" in text_lower and "1500" in text_lower)
        or (
            "итого по разделу iv" in text_lower
            and (
                "итого по разделу v" in text_lower or "итого по разделу у" in text_lower
            )
        )
        or (
            "total liabilities" in text_lower
            and (
                "current liabilities" in text_lower
                or "non-current liabilities" in text_lower
            )
        )
    )

    # Require liability-side signal before stopping. This prevents cutting OCR
    # too early on scanned balance forms where liabilities are detected later pages.
    return has_balance and has_results and token_hits >= 5 and has_liabilities


def _is_financial_table(rows: list) -> bool:
    """Check if table rows contain financial data (not just headers/TOC).

    Uses two strategies:
    1. Keyword matching (works for properly encoded PDFs)
    2. Structural heuristic: table has multiple rows with large numbers (works for
       PDFs with encoding issues where Cyrillic appears as pseudographics)
    """
    financial_keywords = [
        "выручка",
        "прибыль",
        "актив",
        "обязательств",
        "капитал",
        "revenue",
        "profit",
        "assets",
        "liabilities",
        "equity",
        "баланс",
        "отчёт",
        "финансов",
        "оборотн",
        "внеоборотн",
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


def _table_financial_signal_score(rows: list[list[Any]]) -> tuple[int, int, int]:
    """Score how likely a parsed table is to contain statement-like financial rows."""
    strong_row_keywords = (
        "выручка",
        "прибыль за год",
        "прибыль за период",
        "чистая прибыль",
        "итого активы",
        "итого обязательства",
        "денежные средства",
        "капитал",
        "revenue",
        "net income",
        "net profit",
        "total assets",
        "total liabilities",
        "current assets",
        "stockholders' equity",
    )
    noise_hints = (
        "содержание",
        "аудиторское заключение",
        "основные принципы",
        "учетной политики",
        "table of contents",
        "independent auditor",
        "notes to",
    )

    statement_rows = 0
    keyword_hits = 0
    numeric_rows = 0

    for row in rows:
        row_cells = [
            str(cell).strip() for cell in row if cell is not None and str(cell).strip()
        ]
        if not row_cells:
            continue

        row_text_lower = " ".join(row_cells).lower()
        if any(hint in row_text_lower for hint in noise_hints):
            keyword_hits -= 1

        if any(kw in row_text_lower for kw in strong_row_keywords):
            keyword_hits += 1

        label_candidates = row_cells[:2]
        label_text_lower = " ".join(label_candidates).lower()
        values = row_cells[1:] if len(row_cells) > 1 else []

        if any(kw in label_text_lower for kw in strong_row_keywords):
            first_value = _extract_first_numeric_cell(values)
            if _is_valid_financial_value(first_value):
                statement_rows += 1

        if _extract_first_numeric_cell(values or row_cells) is not None:
            numeric_rows += 1

    return (statement_rows, keyword_hits, numeric_rows)


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
        "в миллионах рублей",
        "млн руб",
        "млн. руб",
        "в млн.",
        "тыс. млн",
        "in millions",
        "millions of rubles",
    ]
    patterns_thousands = [
        "в тысячах рублей",
        "тыс. руб",
        "тыс.руб",
        "в тыс.",
        "в тысячах",
        "in thousands",
        "thousands of rubles",
    ]
    patterns_billions = [
        "в миллиардах рублей",
        "млрд руб",
        "млрд. руб",
        "в млрд.",
        "in billions",
    ]

    statement_markers = (
        "consolidated balance sheets",
        "consolidated statements of operations",
        "consolidated statements of income",
        "consolidated statements of stockholders",
        "consolidated statements of cash flows",
        "statement of financial position",
        "balance sheet",
        "отчет о финансовом положении",
        "консолидированный отчет о финансовом положении",
        "сокращенный консолидированный отчет о финансовом положении",
        "промежуточный сокращенный консолидированный отчет о финансовом положении",
        "бухгалтерский баланс",
        "отчет о прибылях и убытках",
        "консолидированный отчет о прибыли и убытке",
        "консолидированный отчет о прибыли и убытке и прочем совокупном доходе",
        "промежуточный сокращенный консолидированный отчет о прибыли и убытке",
        "отчет о движении денежных средств",
        "консолидированный отчет о движении денежных средств",
        "консолидированный отчет об изменениях в капитале",
    )

    statement_windows: list[str] = []
    lines = [" ".join(line.split()) for line in text_lower.splitlines() if line.strip()]
    for index, line in enumerate(lines):
        for marker in statement_markers:
            if marker not in line:
                continue
            if len(line) > len(marker) + 80:
                continue
            window = "\n".join(lines[max(0, index - 1) : index + 6])
            statement_windows.append(window)
            break

    search_regions = statement_windows or [text_lower[:1500]]

    for region in search_regions:
        for p in patterns_billions:
            if p in region:
                logger.info("Scale detected: billions (×1,000,000,000)")
                return 1_000_000_000.0
        for p in patterns_millions:
            if p in region:
                logger.info("Scale detected: millions (×1,000,000)")
                return 1_000_000.0
        for p in patterns_thousands:
            if p in region:
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
                tables_data.append(
                    {
                        "flavor": "ocr",
                        "rows": [["OCR_TEXT", ocr_text]],
                    }
                )
                logger.info("OCR extracted %d characters", len(ocr_text))
        except Exception as ocr_exc:
            logger.warning("OCR extraction failed: %s", ocr_exc)
        return tables_data

    financial_tables_found = False

    # Try stream first — for product PDFs it usually finds useful statement rows
    # much faster than lattice. Lattice is kept as a bounded fallback.
    # Limit to first 30 pages to avoid hanging on large reports.
    _CAMELOT_TIMEOUT = 45
    _CAMELOT_MAX_PAGES = "1-30"

    for flavor in ("stream", "lattice"):
        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(
                    camelot.read_pdf, pdf_path, pages=_CAMELOT_MAX_PAGES, flavor=flavor
                )
                try:
                    tables = future.result(timeout=_CAMELOT_TIMEOUT)
                except concurrent.futures.TimeoutError:
                    logger.warning(
                        "Camelot timed out after %ds (flavor=%s), skipping",
                        _CAMELOT_TIMEOUT,
                        flavor,
                    )
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
                    tables_data.append(
                        {
                            "flavor": flavor,
                            "rows": rows,
                        }
                    )
                    logger.debug("Found financial table with %d rows", len(rows))

        if financial_tables_found:
            break

    # If too many tables found, keep only the most data-rich ones (not OCR fallback)
    if len(tables_data) > 20:
        logger.info(
            "Many tables found (%d), keeping top 10 by financial relevance",
            len(tables_data),
        )
        tables_data = sorted(
            tables_data,
            key=lambda t: (
                _table_financial_signal_score(t.get("rows", [])),
                len(t.get("rows", [])),
            ),
            reverse=True,
        )[:10]
        financial_tables_found = True

    if not financial_tables_found:
        logger.info("No financial tables found via camelot, trying OCR extraction...")
        try:
            ocr_text = extract_text_from_scanned(pdf_path)
            if ocr_text:
                tables_data.append(
                    {
                        "flavor": "ocr",
                        "rows": [["OCR_TEXT", ocr_text]],
                    }
                )
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
    if match_type == "text_regex":
        return 2  # text_regex
    if match_type == "table":
        return 1  # table_partial
    return 0  # derived


def _contains_any(text: str, tokens: tuple[str, ...]) -> bool:
    return any(token in text for token in tokens)


def _metric_candidate_quality(metric_key: str, candidate_text: str) -> int | None:
    """Return candidate quality for metric extraction or None when candidate must be rejected."""
    lower_text = " ".join(candidate_text.lower().split())

    if metric_key == "current_assets":
        total_tokens = (
            "итого оборотных активов",
            "итого оборотные активы",
            "оборотные активы всего",
            "итого по разделу ii",
            "итого по разделу п",
            "total current assets",
            "current assets total",
        )
        reject_tokens = (
            "внеоборотн",
            "non-current",
            "прочие",
            "прочая",
            "other",
        )
        if _contains_any(lower_text, reject_tokens):
            return None
        if _contains_any(lower_text, total_tokens):
            return 90
        return None

    if metric_key == "short_term_liabilities":
        total_tokens = (
            "итого краткосрочных обязательств",
            "итого краткосрочные обязательства",
            "краткосрочные обязательства всего",
            "итого по разделу v",
            "итого по разделу у",
            "total current liabilities",
            "current liabilities total",
        )
        component_tokens = (
            "по аренде",
            "аренд",
            "lease",
            "прочие",
            "прочая",
            "other current liabilities",
            "кредиторск",
        )
        if _contains_any(lower_text, component_tokens):
            return None
        if _contains_any(lower_text, total_tokens):
            return 90
        return None

    if metric_key == "short_term_borrowings":
        total_tokens = (
            "краткосрочные кредиты и займы",
            "краткосрочные заемные средства",
            "short-term borrowings",
            "current borrowings",
        )
        if _contains_any(lower_text, ("аренд", "lease")):
            return None
        if _contains_any(lower_text, total_tokens):
            return 88
        return None

    if metric_key == "long_term_borrowings":
        total_tokens = (
            "долгосрочные кредиты и займы",
            "долгосрочные заемные средства",
            "long-term borrowings",
            "non-current borrowings",
        )
        if _contains_any(lower_text, ("аренд", "lease")):
            return None
        if _contains_any(lower_text, total_tokens):
            return 88
        return None

    if metric_key == "short_term_lease_liabilities":
        total_tokens = (
            "краткосрочные обязательства по аренде",
            "short-term lease liabilities",
            "current lease liabilities",
        )
        if _contains_any(lower_text, total_tokens):
            return 88
        return None

    if metric_key == "long_term_lease_liabilities":
        total_tokens = (
            "долгосрочные обязательства по аренде",
            "long-term lease liabilities",
            "non-current lease liabilities",
        )
        if _contains_any(lower_text, total_tokens):
            return 88
        return None

    if metric_key == "liabilities":
        total_tokens = (
            "итого обязательств",
            "итого обязательства",
            "обязательства всего",
            "total liabilities",
            "liabilities total",
        )
        component_tokens = (
            "по аренде",
            "аренд",
            "lease",
            "краткосрочн",
            "долгосрочн",
            "non-current",
            "current liabilities",
            "other liabilities",
        )
        if _contains_any(lower_text, component_tokens) and not _contains_any(
            lower_text, total_tokens
        ):
            return None
        if _contains_any(lower_text, total_tokens):
            return 90
        return None

    if metric_key == "accounts_receivable":
        if _contains_any(lower_text, ("долгосрочн", "long-term", "non-current")):
            return None
        if _contains_any(
            lower_text,
            ("торговая и прочая дебиторская задолженность", "trade receivables"),
        ):
            return 88
        if _contains_any(lower_text, ("дебиторск", "receivable")):
            return 70
        return None

    if metric_key == "net_profit":
        if (
            "совокупный финансовый результат периода" in lower_text
            and "чистая прибыль" not in lower_text
            and "2400" not in lower_text
        ):
            return None
        if (
            "total comprehensive income" in lower_text
            and "net profit" not in lower_text
            and "net income" not in lower_text
            and "2400" not in lower_text
        ):
            return None

    return 50


def _raw_set(
    raw: dict,
    key: str,
    value: float,
    match_type: str,
    is_exact: bool,
    candidate_quality: int = 50,
) -> None:
    """Set raw[key] with source+quality precedence."""
    new_priority = _source_priority(match_type, is_exact)
    if key in raw:
        existing_priority = _source_priority(raw[key][1], raw[key][2])
        existing_quality = raw[key][3] if len(raw[key]) > 3 else 50
        if new_priority < existing_priority:
            return
        if new_priority == existing_priority:
            if candidate_quality < existing_quality:
                return
            if candidate_quality == existing_quality:
                return
    raw[key] = (value, match_type, is_exact, candidate_quality)


def _derive_current_assets_from_available(
    raw: dict[str, tuple[float, str, bool, int]]
) -> float | None:
    cash = raw["cash_and_equivalents"][0] if "cash_and_equivalents" in raw else None
    inventory = raw["inventory"][0] if "inventory" in raw else None
    receivables = (
        raw["accounts_receivable"][0] if "accounts_receivable" in raw else None
    )
    total_assets = raw["total_assets"][0] if "total_assets" in raw else None
    equity = raw["equity"][0] if "equity" in raw else None
    liabilities = raw["liabilities"][0] if "liabilities" in raw else None

    components = [v for v in (cash, inventory, receivables) if v is not None]
    if len(components) >= 2:
        return sum(components)

    if total_assets is not None and equity is not None and liabilities is not None:
        derived = total_assets - equity - liabilities
        if derived > 0:
            return derived
    return None


def _apply_form_like_pnl_sanity(
    raw: dict[str, tuple[float, str, bool, int]],
    code_candidates: dict[str, float],
    *,
    is_standalone_form: bool = False,
) -> None:
    revenue_entry = raw.get("revenue")
    net_profit_entry = raw.get("net_profit")
    if revenue_entry is None or net_profit_entry is None:
        return

    revenue = revenue_entry[0]
    net_profit = net_profit_entry[0]
    if revenue <= 0:
        return

    current_margin = abs(net_profit) / revenue
    if current_margin <= 0.6:
        return

    if is_standalone_form:
        return

    revenue_code = code_candidates.get("revenue")
    net_profit_code = code_candidates.get("net_profit")
    if revenue_code is not None and net_profit_code is not None:
        _raw_set(
            raw,
            "revenue",
            revenue_code,
            "text_regex",
            True,
            candidate_quality=120,
        )
        _raw_set(
            raw,
            "net_profit",
            net_profit_code,
            "text_regex",
            True,
            candidate_quality=120,
        )
        return

    revenue_priority = _source_priority(revenue_entry[1], revenue_entry[2])
    net_profit_priority = _source_priority(net_profit_entry[1], net_profit_entry[2])
    if revenue_priority >= 3 or net_profit_priority >= 3:
        return

    best_revenue = revenue
    best_net_profit = net_profit
    best_margin = current_margin

    candidate_pairs = [
        (revenue_code, net_profit),
        (revenue, net_profit_code),
        (revenue_code, net_profit_code),
    ]
    for candidate_revenue, candidate_net_profit in candidate_pairs:
        if (
            candidate_revenue is None
            or candidate_net_profit is None
            or candidate_revenue <= 0
        ):
            continue
        candidate_margin = abs(candidate_net_profit) / candidate_revenue
        if candidate_margin < best_margin:
            best_margin = candidate_margin
            best_revenue = candidate_revenue
            best_net_profit = candidate_net_profit

    if best_revenue != revenue:
        _raw_set(
            raw,
            "revenue",
            best_revenue,
            "text_regex",
            True,
            candidate_quality=120,
        )
        revenue_entry = raw["revenue"]
    if best_net_profit != net_profit:
        _raw_set(
            raw,
            "net_profit",
            best_net_profit,
            "text_regex",
            True,
            candidate_quality=120,
        )
        net_profit_entry = raw["net_profit"]

    revenue = revenue_entry[0]
    net_profit = net_profit_entry[0]
    if revenue <= 0:
        return

    margin_after_fallback = abs(net_profit) / revenue
    if margin_after_fallback <= 0.6:
        return

    revenue_quality = revenue_entry[3] if len(revenue_entry) > 3 else 50
    net_profit_quality = net_profit_entry[3] if len(net_profit_entry) > 3 else 50
    revenue_reliability = revenue_priority * 100 + revenue_quality
    net_profit_reliability = net_profit_priority * 100 + net_profit_quality

    if revenue_reliability < net_profit_reliability:
        conflicting_key = "revenue"
    elif net_profit_reliability < revenue_reliability:
        conflicting_key = "net_profit"
    elif "net_profit" in code_candidates and "revenue" not in code_candidates:
        conflicting_key = "revenue"
    elif "revenue" in code_candidates and "net_profit" not in code_candidates:
        conflicting_key = "net_profit"
    else:
        conflicting_key = "net_profit"

    logger.warning(
        "Dropping %s due to P&L sanity conflict: revenue=%s, net_profit=%s, margin=%s, reliability=(revenue:%s, net_profit:%s)",
        conflicting_key,
        revenue,
        net_profit,
        margin_after_fallback,
        revenue_reliability,
        net_profit_reliability,
    )
    raw.pop(conflicting_key, None)


def parse_financial_statements_with_metadata(
    tables: list, text: str
) -> dict[str, ExtractionMetadata]:
    """Compatibility entrypoint that delegates to the staged pipeline."""
    from .pipeline import (
        parse_financial_statements_with_metadata as _parse_with_metadata,
    )

    return _parse_with_metadata(tables, text)


def parse_financial_statements(tables: list, text: str) -> dict[str, float | None]:
    """Compatibility entrypoint that delegates to the staged pipeline."""
    from .pipeline import parse_financial_statements as _parse

    return _parse(tables, text)


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
    num_group = rf"({_NUMBER_REGEX_FRAGMENT})"

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
    - Year markers like 2023/2022 in multi-period tables
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
        if value is not None and not _is_year(value):
            return value
    return None


def _extract_section_total(
    tables: list, text_lower: str, keywords: list[str]
) -> float | None:
    """Extract a section total value by keywords from tables or text."""
    for table in tables or []:
        rows = _table_to_rows(table)
        for row in rows:
            row_text_lower = " ".join(str(c) for c in row if c is not None).lower()
            if any(kw in row_text_lower for kw in keywords):
                val = _extract_first_numeric_cell(row[1:])
                if val is not None:
                    return val
    return _extract_number_near_keywords(text_lower, keywords)


def _extract_section_total_from_heading_rows(
    tables: list,
    section_headings: tuple[str, ...],
    stop_markers: tuple[str, ...],
) -> float | None:
    """
    Infer section totals from unlabeled or total-like rows following a section heading.

    This helps IFRS/RSBU balance tables where subtotal rows are represented as
    numeric-only lines without an explicit "Итого ..." label in the same row.
    """
    best_value: float | None = None
    best_score: int | None = None

    for table in tables or []:
        rows = _table_to_rows(table)
        if not rows:
            continue

        table_text = " ".join(
            " ".join(str(cell) for cell in row if cell is not None).lower()
            for row in rows
        )
        table_bonus = (
            15
            if (
                ("итого активы" in table_text or "total assets" in table_text)
                and (
                    "капитал и обязательства" in table_text
                    or "total equity and liabilities" in table_text
                    or "equity and liabilities" in table_text
                )
            )
            else 0
        )
        if (
            "первоначально представлено" in table_text
            or "эффект от пересчета" in table_text
            or "как пересчитано" in table_text
        ):
            table_bonus -= 35

        for heading_idx, row in enumerate(rows):
            row_text_lower = " ".join(
                str(cell) for cell in row if cell is not None
            ).lower()
            if not any(heading in row_text_lower for heading in section_headings):
                continue
            if (
                "оборотные активы" in section_headings
                or "current assets" in section_headings
            ) and ("внеоборотн" in row_text_lower or "non-current" in row_text_lower):
                continue
            if (
                "краткосрочные обязательства" in section_headings
                or "current liabilities" in section_headings
            ) and ("долгосрочн" in row_text_lower or "non-current" in row_text_lower):
                continue

            for candidate_idx in range(
                heading_idx + 1, min(len(rows), heading_idx + 30)
            ):
                candidate_row = rows[candidate_idx]
                candidate_text_lower = " ".join(
                    str(cell) for cell in candidate_row if cell is not None
                ).lower()

                if any(marker in candidate_text_lower for marker in stop_markers):
                    break
                if any(heading in candidate_text_lower for heading in section_headings):
                    break

                value = _extract_first_numeric_cell(candidate_row[1:])
                if not _is_valid_financial_value(value):
                    continue

                first_cell = (
                    str(candidate_row[0]).strip().lower()
                    if len(candidate_row) > 0 and candidate_row[0] is not None
                    else ""
                )
                is_unlabeled = first_cell in {"", "-", "—", "–"}
                has_total_label = (
                    "итого" in candidate_text_lower or "total" in candidate_text_lower
                )
                if not (is_unlabeled or has_total_label):
                    continue

                score = 100 + table_bonus - (candidate_idx - heading_idx)
                if not has_total_label:
                    score -= 4

                if (
                    best_score is None
                    or score > best_score
                    or (
                        score == best_score
                        and abs(value or 0.0) > abs(best_value or 0.0)
                    )
                ):
                    best_score = score
                    best_value = value

    return best_value


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


def _extract_preferred_numeric_match(text: str) -> float | None:
    matches = _NUMBER_PATTERN.findall(text)
    if not matches:
        return None

    parsed_candidates: list[tuple[str, float]] = []
    for raw_match in matches:
        candidate_text = _split_non_ocr_grouped_period_values(raw_match)
        value = _normalize_number(candidate_text)
        if value is None or _is_year(value):
            continue
        parsed_candidates.append((candidate_text, value))

    if not parsed_candidates:
        return None

    for raw_match, value in parsed_candidates:
        digits_only = "".join(ch for ch in raw_match if ch.isdigit())
        if (
            digits_only.isdigit()
            and len(digits_only) <= 3
            and len(parsed_candidates) > 1
        ):
            continue
        if digits_only.startswith("07") and len(digits_only) >= 6:
            continue
        return value

    return parsed_candidates[-1][1]


def _split_grouped_period_values(raw_match: str) -> str:
    """Take the most conservative first value from OCR-collapsed multi-period runs."""
    if "\n" in raw_match:
        return raw_match

    groups = re.findall(r"\d+", raw_match)
    if len(groups) < 4:
        return raw_match

    candidate_group_counts: list[int] = []
    for period_count in (2, 3):
        if len(groups) % period_count != 0:
            continue
        groups_per_value = len(groups) // period_count
        if 2 <= groups_per_value <= 4:
            candidate_group_counts.append(groups_per_value)

    if not candidate_group_counts:
        return raw_match

    if len(candidate_group_counts) > 1 and len(groups[0]) == 4:
        first_value_groups = min(candidate_group_counts)
    else:
        first_value_groups = max(candidate_group_counts)
    prefix = " ".join(groups[:first_value_groups])

    negative = raw_match.strip().startswith(("(", "-", "\u2212"))
    if negative and not prefix.startswith("-"):
        prefix = f"-{prefix}"
    return prefix


def _split_non_ocr_grouped_period_values(raw_match: str) -> str:
    """Conservatively split two-period numeric runs from regular text extraction."""
    if "\n" in raw_match:
        return raw_match

    groups = re.findall(r"\d+", raw_match)
    if len(groups) != 4:
        return raw_match

    lengths = [len(group) for group in groups]
    if lengths == [3, 3, 3, 3]:
        return " ".join(groups[:2])
    if lengths[1] == 3 and lengths[3] == 3 and lengths[0] <= 2 and lengths[2] <= 2:
        return " ".join(groups[:2])
    return raw_match


def _extract_ocr_numeric_candidates(text: str) -> list[str]:
    candidates: list[str] = []
    seen: set[str] = set()

    for match in re.finditer(r"[-(]?\$?\d+(?:[ \t\xa0]+\d+)+(?:[.,]\d+)?\)?", text):
        candidate = match.group(0)
        if candidate not in seen:
            candidates.append(candidate)
            seen.add(candidate)

    for candidate in _OCR_NUMBER_PATTERN.findall(text):
        if candidate not in seen:
            candidates.append(candidate)
            seen.add(candidate)

    return candidates


def _extract_preferred_ocr_numeric_match(text: str) -> float | None:
    matches = _extract_ocr_numeric_candidates(text)
    if not matches:
        return None

    parsed_candidates: list[tuple[str, float]] = []
    for raw_match in matches:
        value = _normalize_number(_split_grouped_period_values(raw_match))
        if value is None or _is_year(value):
            continue
        parsed_candidates.append((raw_match, value))

    if not parsed_candidates:
        return None

    has_large_numeric_candidate = any(
        len("".join(ch for ch in raw_match if ch.isdigit())) >= 6
        for raw_match, _value in parsed_candidates
    )

    for raw_match, value in parsed_candidates:
        digits_only = "".join(ch for ch in raw_match if ch.isdigit())
        if (
            digits_only.isdigit()
            and len(digits_only) <= 3
            and len(parsed_candidates) > 1
        ):
            continue
        if (
            has_large_numeric_candidate
            and len(digits_only) == 4
            and len(parsed_candidates) > 1
            and abs(value) < 10000
        ):
            # OCR rows in scanned forms often start with 4-digit line codes
            # (for example 3211/3311) before actual period values.
            continue
        if digits_only.startswith("07") and len(digits_only) >= 6:
            continue
        return value

    return parsed_candidates[-1][1]


def _extract_substantial_code_line_value(text: str) -> float | None:
    """Extract a same-line financial value near a form code without following
    explanatory note references."""
    matches = _extract_ocr_numeric_candidates(text)
    if not matches:
        return None

    parsed_candidates: list[tuple[float, int]] = []
    for raw_match in matches:
        value = _normalize_number(_split_grouped_period_values(raw_match))
        if value is None or _is_year(value):
            continue
        parsed_candidates.append((value, sum(ch.isdigit() for ch in raw_match)))

    if not parsed_candidates:
        return None

    if not any(digit_count >= 5 for _value, digit_count in parsed_candidates):
        return None

    for value, digit_count in parsed_candidates:
        if digit_count < 5:
            continue
        if len(parsed_candidates) > 1 and abs(value) > 10_000_000_000:
            continue
        return value

    return None


def _extract_numeric_value_from_following_lines(lines: list[str]) -> float | None:
    for line in lines:
        normalized = " ".join(line.split())
        if not normalized:
            continue

        lower_line = normalized.lower()
        if any(
            noise in lower_line
            for noise in (
                "справочно",
                "руководитель",
                "подпись",
                "пояснение",
                "форма 07",
            )
        ):
            continue

        digit_count = sum(ch.isdigit() for ch in normalized)
        if digit_count < 5:
            continue

        if not re.fullmatch(r'["()\-−\d\s.,]+', normalized):
            continue

        value = _extract_preferred_ocr_numeric_match(normalized)
        if _is_valid_financial_value(value):
            return value

    return None


def _extract_number_near_keywords(text: str, keywords: list[str]) -> float | None:
    for keyword in keywords:
        start = 0
        while True:
            index = text.find(keyword, start)
            if index == -1:
                break

            window_start = index + len(keyword)
            window = text[window_start : window_start + 60]
            value = _extract_preferred_numeric_match(window)
            if value is not None:
                return value

            start = index + len(keyword)
    return None


def _extract_form_section_total(
    text: str,
    section_markers: tuple[str, ...],
    lookback_lines: int = 8,
    lookahead_lines: int = 1,
) -> float | None:
    lines = [" ".join(line.split()) for line in text.splitlines() if line.strip()]
    if not lines:
        return None

    lower_markers = tuple(marker.lower() for marker in section_markers)
    noise_tokens = ("поясне", "форма 07", "руководитель", "подпись", "итого по разделу")

    marker_indices: list[int] = []
    same_line_candidates: list[float] = []
    for idx, line in enumerate(lines):
        lower_line = line.lower()
        if not any(marker in lower_line for marker in lower_markers):
            continue
        marker_indices.append(idx)

        same_line_value = _extract_preferred_ocr_numeric_match(line)
        if _is_valid_financial_value(same_line_value):
            same_line_candidates.append(same_line_value)

    if same_line_candidates:
        return max(same_line_candidates)

    for idx in marker_indices:
        candidate_values: list[float] = []
        start = max(0, idx - lookback_lines)
        end = min(len(lines), idx + lookahead_lines + 1)
        for pos in range(start, end):
            if pos == idx:
                continue
            candidate_line = lines[pos]
            candidate_lower = candidate_line.lower()
            if any(token in candidate_lower for token in noise_tokens):
                continue

            value = _extract_preferred_ocr_numeric_match(candidate_line)
            if _is_valid_financial_value(value) and value is not None and value >= 1000:
                candidate_values.append(value)

        if candidate_values:
            return max(candidate_values)

    return None


def _extract_form_long_term_liabilities(
    text: str,
    short_term_value: float | None = None,
) -> float | None:
    section_value = _extract_form_section_total(
        text,
        ("итого по разделу iv", "итого долгосрочных обязательств"),
        lookback_lines=8,
        lookahead_lines=1,
    )
    code_value = _extract_value_near_text_codes(
        text,
        ("1400",),
        ("итого по разделу iv", "долгосрочн"),
        lookahead_chars=220,
    )

    candidates = [
        value
        for value in (section_value, code_value)
        if _is_valid_financial_value(value)
    ]
    if short_term_value is not None:
        # Soft deduplication only for near-identical IV/V artifacts from OCR.
        tolerance = max(1.0, abs(short_term_value) * 0.000001)
        candidates = [
            value for value in candidates if abs(value - short_term_value) > tolerance
        ]

    if not candidates:
        return None
    if len(candidates) == 1:
        return candidates[0]

    larger = max(candidates)
    smaller = min(candidates)
    if smaller > 0 and larger / smaller >= 1.5:
        return smaller
    return candidates[0]


def _extract_form_like_pnl_section_candidates(
    text: str,
) -> dict[str, tuple[float, int, bool]]:
    lines = [" ".join(line.split()) for line in text.splitlines() if line.strip()]
    if not lines:
        return {}

    start_index: int | None = None
    for idx, line in enumerate(lines):
        lower_line = line.lower()
        if any(marker in lower_line for marker in _P_AND_L_SECTION_MARKERS):
            start_index = idx
            break
    if start_index is None:
        return {}

    end_index = len(lines)
    for idx in range(start_index + 1, len(lines)):
        lower_line = lines[idx].lower()
        if any(marker in lower_line for marker in _P_AND_L_SECTION_END_MARKERS):
            end_index = idx
            break

    section_lines = lines[start_index:end_index]
    if not section_lines:
        return {}
    section_text = "\n".join(section_lines)

    def _extract_same_line_after_anchor(
        line: str, anchors: tuple[str, ...]
    ) -> float | None:
        lower_line = line.lower()
        for anchor in anchors:
            anchor_index = lower_line.find(anchor)
            if anchor_index == -1:
                continue
            value = _extract_preferred_ocr_numeric_match(
                line[anchor_index + len(anchor) :]
            )
            if _is_valid_financial_value(value):
                return value
        return None

    candidates: dict[str, tuple[float, int, bool]] = {}

    revenue_code_value = _extract_value_near_text_codes(
        section_text,
        ("2110",),
        ("выручка от реализации, без ндс", "выручка", "revenue"),
        lookahead_chars=1400,
    )
    if _is_valid_financial_value(revenue_code_value):
        candidates["revenue"] = (revenue_code_value, 110, True)
    else:
        for idx, line in enumerate(section_lines):
            lower_line = line.lower()
            if "выручка" not in lower_line and "revenue" not in lower_line:
                continue
            same_line_value = _extract_same_line_after_anchor(
                line,
                ("выручка", "revenue"),
            )
            if _is_valid_financial_value(same_line_value):
                candidates["revenue"] = (same_line_value, 108, True)
                break
            followup_value = _extract_numeric_value_from_following_lines(
                section_lines[idx + 1 : idx + 6]
            )
            if _is_valid_financial_value(followup_value):
                candidates["revenue"] = (followup_value, 104, True)
                break

    net_profit_direct_signal = False
    net_profit_code_value = _extract_value_near_text_codes(
        section_text,
        ("2400",),
        ("чистая прибыль", "net profit", "net income"),
        lookahead_chars=1400,
    )
    if _is_valid_financial_value(net_profit_code_value):
        candidates["net_profit"] = (net_profit_code_value, 120, True)
        net_profit_direct_signal = True

    net_profit_direct_tokens = ("чистая прибыль", "net profit", "net income", "2400")
    if "net_profit" not in candidates:
        for idx, line in enumerate(section_lines):
            lower_line = line.lower()
            if not any(token in lower_line for token in net_profit_direct_tokens):
                continue
            net_profit_direct_signal = True
            same_line_value = _extract_same_line_after_anchor(
                line,
                ("чистая прибыль", "net profit", "net income"),
            )
            if _is_valid_financial_value(same_line_value):
                candidates["net_profit"] = (same_line_value, 110, True)
                break

            followup_lines: list[str] = []
            for candidate_line in section_lines[idx + 1 : idx + 7]:
                candidate_lower = candidate_line.lower()
                if (
                    "совокупный финансовый результат периода" in candidate_lower
                    or "total comprehensive income" in candidate_lower
                ):
                    break
                followup_lines.append(candidate_line)

            followup_value = _extract_numeric_value_from_following_lines(followup_lines)
            if _is_valid_financial_value(followup_value):
                candidates["net_profit"] = (followup_value, 106, True)
                break

    if "net_profit" not in candidates and net_profit_direct_signal:
        for idx, line in enumerate(section_lines):
            lower_line = line.lower()
            if (
                "совокупный финансовый результат периода" not in lower_line
                and "total comprehensive income" not in lower_line
            ):
                continue
            fallback_value = _extract_preferred_ocr_numeric_match(line)
            if not _is_valid_financial_value(fallback_value):
                fallback_value = _extract_numeric_value_from_following_lines(
                    section_lines[idx + 1 : idx + 4]
                )
            if _is_valid_financial_value(fallback_value):
                candidates["net_profit"] = (fallback_value, 112, True)
            break

    return candidates


def _derive_liabilities_from_components(
    long_term: float | None,
    short_term: float | None,
    total_assets: float | None,
    equity: float | None,
) -> float | None:
    if long_term is None or short_term is None:
        return None

    derived = long_term + short_term
    if not _is_valid_financial_value(derived):
        return None

    if total_assets is not None and total_assets > 0:
        ratio = derived / total_assets
        if ratio < 0.02:
            return None

    if total_assets is not None and equity is not None:
        assets_minus_equity = total_assets - equity
        if _is_valid_financial_value(assets_minus_equity):
            tolerance = max(1000.0, abs(assets_minus_equity) * 0.05)
            if abs(derived - assets_minus_equity) > tolerance:
                return None

    return derived


def _apply_form_like_guardrails(result: dict[str, ExtractionMetadata]) -> None:
    def _soft_null(metric_key: str) -> None:
        result[metric_key] = ExtractionMetadata(
            value=None,
            confidence=0.0,
            source="derived",
        )

    total_assets = result["total_assets"].value
    current_assets = result["current_assets"].value
    liabilities = result["liabilities"].value
    equity = result["equity"].value
    short_term = result["short_term_liabilities"].value

    if total_assets is not None:
        if current_assets is not None and current_assets > total_assets:
            _soft_null("current_assets")
            current_assets = None

        if liabilities is not None and liabilities > total_assets:
            _soft_null("liabilities")
            liabilities = None

        if equity is not None and equity > total_assets:
            _soft_null("equity")
            equity = None

        if short_term is not None and short_term > total_assets:
            _soft_null("short_term_liabilities")
            short_term = None

    for component_key in ("cash_and_equivalents", "inventory", "accounts_receivable"):
        component = result[component_key].value
        if (
            current_assets is not None
            and component is not None
            and component > current_assets
        ):
            _soft_null(component_key)

    if liabilities is not None and short_term is not None and short_term > liabilities:
        _soft_null("short_term_liabilities")


_TEXT_LINE_CODE_MAP: dict[str, tuple[tuple[str, ...], tuple[str, ...] | None]] = {
    # RSBU codes (форма 0710001)
    "revenue": (("2110",), ("выручка от реализации, без ндс", "выручка", "revenue")),
    "net_profit": (
        ("2400", "2300"),
        (
            "чистая прибыль",
            "чистая прибыль общества",
            "прибыль за период",
            "прибыль за год",
            "net profit",
            "net income",
        ),
    ),
    "total_assets": (("1600", "1700"), None),
    "current_assets": (("1200",), None),
    "inventory": (("1210",), ("запасы", "inventory")),
    "accounts_receivable": (
        ("1230",),
        (
            "дебиторская задолженность",
            "accounts receivable",
            "trade receivables",
        ),
    ),
    "long_term_liabilities": (
        ("1400",),
        (
            "долгосрочные обязательства",
            "итого по разделу iv",
            "total non-current liabilities",
        ),
    ),
    "short_term_liabilities": (
        ("1500",),
        (
            "краткосрочные обязательства",
            "итого краткосрочных обязательств",
            "итого краткосрочные обязательства",
            "total current liabilities",
        ),
    ),
    "cash_and_equivalents": (
        ("1250",),
        ("денежные средства", "cash and cash equivalents"),
    ),
}


def _extract_value_near_text_codes(
    text: str,
    codes: tuple[str, ...],
    anchor_keywords: tuple[str, ...] | None = None,
    lookahead_chars: int = 700,
) -> float | None:
    text_lower = text.lower()

    for code in codes:
        pattern = rf"(?<!\d){re.escape(code)}(?!\d)"
        for match in re.finditer(pattern, text_lower):
            line_start = text.rfind("\n", 0, match.start()) + 1
            line_end = text.find("\n", match.end())
            if line_end == -1:
                line_end = len(text)

            current_line = text[line_start:line_end]
            if not current_line:
                continue

            current_line_lower = current_line.lower()
            is_code_row = bool(
                re.search(rf"(^|\b)код\s+{re.escape(code)}(?!\d)", current_line_lower)
            ) or current_line_lower.strip().startswith(code)
            if (
                anchor_keywords
                and not any(
                    keyword in current_line_lower for keyword in anchor_keywords
                )
                and not is_code_row
            ):
                continue

            same_line_window = current_line[match.end() - line_start :]
            value = _extract_substantial_code_line_value(same_line_window)
            if _is_valid_financial_value(value):
                return value

    return None


def _extract_best_multiline_value(
    text: str,
    keywords: list[str],
    lookahead_lines: int = 8,
    ocr_mode: bool = False,
    metric_key: str | None = None,
) -> tuple[float | None, int | None]:
    best_score: int | None = None
    best_value: float | None = None
    best_quality: int | None = None
    ordered_keywords = sorted(keywords, key=len, reverse=True)
    normalized_lines = [
        " ".join(line.split()) for line in text.splitlines() if line.strip()
    ]
    prefer_smaller_on_tie = metric_key in {"accounts_receivable"}

    for index, line in enumerate(normalized_lines):
        lower_line = line.lower()
        metric_quality = (
            _metric_candidate_quality(metric_key, line)
            if metric_key is not None
            else 50
        )
        if metric_quality is None:
            continue
        matched_keyword = next(
            (kw for kw in ordered_keywords if kw in lower_line), None
        )
        if matched_keyword is None:
            continue

        block_lines = normalized_lines[index : index + lookahead_lines]
        block_lines = [
            candidate
            for candidate in block_lines
            if not any(
                noise in candidate.lower()
                for noise in ("форма 07", "поясне", "код", "приложение №")
            )
        ]
        if ocr_mode:
            score = (
                _score_metric_line(lower_line, matched_keyword, line)
                + max(0, 6 - index)
                + metric_quality // 20
            )
            same_line_source = line[
                line.lower().find(matched_keyword) + len(matched_keyword) :
            ]
            same_line_value = _extract_preferred_ocr_numeric_match(same_line_source)
            if _is_valid_financial_value(same_line_value):
                same_line_is_better = False
                if best_score is None or score > best_score:
                    same_line_is_better = True
                elif score == best_score:
                    if prefer_smaller_on_tie:
                        same_line_is_better = best_value is None or abs(
                            same_line_value
                        ) < abs(best_value)
                    else:
                        same_line_is_better = abs(same_line_value) > abs(
                            best_value or 0.0
                        )

                if same_line_is_better:
                    best_score = score
                    best_value = same_line_value
                    best_quality = metric_quality

            followup_lines = normalized_lines[index + 1 : index + lookahead_lines]
            if metric_key is not None:
                followup_lines = [
                    candidate
                    for candidate in followup_lines
                    if not _line_mentions_other_metric(candidate.lower(), metric_key)
                ]
            if metric_key == "net_profit":
                trimmed_followup: list[str] = []
                for candidate in followup_lines:
                    candidate_lower = candidate.lower()
                    if (
                        "совокупный финансовый результат периода" in candidate_lower
                        and "чистая прибыль" not in candidate_lower
                        and "2400" not in candidate_lower
                    ):
                        break
                    trimmed_followup.append(candidate)
                followup_lines = trimmed_followup

            line_value = _extract_numeric_value_from_following_lines(followup_lines)
            if _is_valid_financial_value(line_value):
                followup_is_better = False
                if best_score is None or score > best_score:
                    followup_is_better = True
                elif score == best_score:
                    if prefer_smaller_on_tie:
                        followup_is_better = best_value is None or abs(
                            line_value
                        ) < abs(best_value)
                    else:
                        followup_is_better = abs(line_value) > abs(best_value or 0.0)

                if followup_is_better:
                    best_score = score
                    best_value = line_value
                    best_quality = metric_quality
            continue

        block = " ".join(block_lines)
        keyword_index = block.lower().find(matched_keyword)
        if keyword_index == -1:
            continue

        value_source = block[keyword_index + len(matched_keyword) :]
        if ocr_mode:
            value = _extract_preferred_ocr_numeric_match(value_source)
        else:
            value = _extract_preferred_numeric_match(value_source)
        if not _is_valid_financial_value(value):
            continue

        score = (
            _score_metric_line(lower_line, matched_keyword, line)
            + max(0, 6 - index)
            + metric_quality // 20
        )
        if (
            best_score is None
            or score > best_score
            or (score == best_score and abs(value) > abs(best_value or 0.0))
        ):
            best_score = score
            best_value = value
            best_quality = metric_quality

    return best_value, best_quality


def _normalize_metric_text(text: str) -> str:
    return (
        text.replace("\u2019", "'")
        .replace("\u2018", "'")
        .replace("\u201c", '"')
        .replace("\u201d", '"')
    )


_LINE_NOISE_HINTS = (
    "consolidated statements of",
    "statement of stockholders",
    "statement of shareholders",
    "increase",
    "decrease",
    "decline",
    "growth",
    "represented more than",
    "customer accounted",
    "future",
    "may ",
    "could ",
    "price",
    "market value",
    "equity compensation",
    "risk",
    "table of contents",
)


def _extract_best_line_value(
    text: str,
    keywords: list[str],
    metric_key: str | None = None,
) -> tuple[float | None, int | None]:
    """Pick the most statement-like line candidate for the requested metric."""
    best_score: int | None = None
    best_value: float | None = None
    best_quality: int | None = None
    ordered_keywords = sorted(
        {_normalize_metric_text(keyword).lower() for keyword in keywords},
        key=len,
        reverse=True,
    )

    for raw_line in text.splitlines():
        line = _normalize_metric_text(" ".join(raw_line.split()))
        if not line:
            continue

        lower_line = line.lower()
        metric_quality = (
            _metric_candidate_quality(metric_key, line)
            if metric_key is not None
            else 50
        )
        if metric_quality is None:
            continue
        matched_keyword = next(
            (kw for kw in ordered_keywords if kw in lower_line), None
        )
        if matched_keyword is None:
            continue

        value = _extract_number_after_keyword(line, matched_keyword)
        if value is None:
            continue

        score = (
            _score_metric_line(lower_line, matched_keyword, line) + metric_quality // 20
        )
        if (
            best_score is None
            or score > best_score
            or (score == best_score and abs(value) > abs(best_value or 0.0))
        ):
            best_score = score
            best_value = value
            best_quality = metric_quality

    return best_value, best_quality


def _extract_number_after_keyword(line: str, keyword: str) -> float | None:
    normalized_line = _normalize_metric_text(line)
    normalized_keyword = _normalize_metric_text(keyword).lower()
    keyword_index = normalized_line.lower().find(normalized_keyword)
    if keyword_index == -1:
        return None

    window = normalized_line[keyword_index + len(normalized_keyword) :]
    return _extract_preferred_numeric_match(window)


def _score_metric_line(lower_line: str, keyword: str, line: str) -> int:
    """Prefer short statement rows over narrative sentences and headers."""
    score = 0
    keyword_index = lower_line.find(keyword)
    number_count = len(_NUMBER_PATTERN.findall(line))
    keyword_specificity_bonus = min(4, max(0, len(keyword.split()) - 1))

    score += keyword_specificity_bonus

    if keyword_index == 0:
        score += 5
    elif keyword_index < 12:
        score += 3
    elif keyword_index < 32:
        score += 1
    else:
        score -= 1

    if "$" in line:
        score += 2

    if 2 <= number_count <= 4:
        score += 2
    elif number_count == 1:
        score += 1
    elif number_count > 6:
        score -= 2

    if len(lower_line) <= 120:
        score += 1
    elif len(lower_line) > 220:
        score -= 2

    if "%" in line:
        score -= 3

    if any(hint in lower_line for hint in _LINE_NOISE_HINTS):
        score -= 5

    if keyword == "total liabilities" and (
        "stockholders' equity" in lower_line
        or "stockholders’ equity" in lower_line
        or "shareholders' equity" in lower_line
        or "shareholders’ equity" in lower_line
    ):
        score -= 4

    return score


def _line_mentions_other_metric(lower_line: str, metric_key: str) -> bool:
    for other_key, other_keywords in _METRIC_KEYWORDS.items():
        if other_key == metric_key:
            continue
        if any(keyword in lower_line for keyword in other_keywords):
            return True
    return False


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
    cleaned = _normalize_numeric_separators(cleaned)
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


def _normalize_numeric_separators(raw_value: str) -> str:
    """Normalize grouped numeric separators into a float-friendly string."""
    cleaned = raw_value.strip()
    if not cleaned:
        return cleaned

    comma_count = cleaned.count(",")
    dot_count = cleaned.count(".")

    if comma_count and dot_count:
        last_comma = cleaned.rfind(",")
        last_dot = cleaned.rfind(".")
        if last_dot > last_comma:
            return cleaned.replace(",", "")
        return cleaned.replace(".", "").replace(",", ".")

    if comma_count > 1:
        return cleaned.replace(",", "")

    if dot_count > 1:
        return cleaned.replace(".", "")

    if comma_count == 1:
        left, right = cleaned.rsplit(",", 1)
        normalized_right = right.rstrip(")")
        normalized_left = left.replace("-", "").replace("(", "")
        if (
            normalized_right.isdigit()
            and len(normalized_right) == 3
            and normalized_left.isdigit()
        ):
            return left + normalized_right
        return cleaned.replace(",", ".")

    if dot_count == 1:
        left, right = cleaned.rsplit(".", 1)
        normalized_right = right.rstrip(")")
        normalized_left = left.replace("-", "").replace("(", "")
        if (
            normalized_right.isdigit()
            and len(normalized_right) == 3
            and normalized_left.isdigit()
        ):
            return left + normalized_right

    return cleaned
