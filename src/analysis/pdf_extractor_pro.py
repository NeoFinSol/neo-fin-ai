"""
Simplified financial data extractor with confidence scoring.

Pipeline:
1. Extract text from PDF (pdfplumber)
2. If text is poor → use OCR (tesseract)
3. Extract metrics via regex with context window
4. Validate values (filter noise)
5. Return metrics with confidence scores
"""
import re
import logging
from typing import Dict, Any

import pdfplumber
from pdf2image import convert_from_path
import pytesseract

from src.analysis.confidence import build_metric, Metric, filter_by_confidence

logger = logging.getLogger(__name__)

# =========================
# CONFIG
# =========================

METRIC_KEYWORDS = {
    "revenue": ["выручка", "revenue", "доходы от реализации"],
    "net_profit": ["чистая прибыль", "net profit", "прибыль после налогообложения"],
    "total_assets": ["итого активов", "активы всего", "total assets", "баланс"],
    "equity": ["итого капитала", "капитал и резервы", "total equity", "собственный капитал"],
    "liabilities": ["итого обязательств", "total liabilities", "обязательства всего"],
    "current_assets": ["итого оборотных активов", "current assets", "оборотные активы"],
    "short_term_liabilities": ["итого краткосрочных обязательств", "current liabilities"],
    "accounts_receivable": ["дебиторская задолженность", "accounts receivable"],
    "inventory": ["запасы", "inventory", "товарно-материальные ценности"],
    "cash_and_equivalents": ["денежные средства", "cash and equivalents", "наличные"],
}

MIN_VALID_VALUE = 10_000    # Too small = noise (years, page numbers)
MAX_VALID_VALUE = 1e12       # Too large = parsing error (1 trillion)


# =========================
# TEXT EXTRACTION
# =========================

def extract_text_pdf(pdf_path: str) -> str:
    """Extract text from PDF using pdfplumber."""
    text = ""
    
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            t = page.extract_text()
            if t:
                text += t + "\n"
    
    logger.info(f"Text extracted: {len(text)} chars")
    return text


def extract_text_ocr(pdf_path: str) -> str:
    """Extract text from PDF using OCR (Tesseract)."""
    images = convert_from_path(pdf_path, dpi=300)
    
    text = ""
    for i, img in enumerate(images[:20]):  # Limit to 20 pages
        page_text = pytesseract.image_to_string(img, lang="rus+eng")
        text += page_text + "\n"
        logger.debug(f"OCR page {i+1}: {len(page_text)} chars")
    
    logger.info(f"OCR extracted: {len(text)} chars")
    return text


def is_text_poor(text: str, pdf_path: str = None) -> bool:
    """
    Check if extracted text is poor (needs OCR).
    
    Text is poor if:
    - Less than 2000 chars
    - OR PDF has many pages (complex report → likely scanned tables)
    - OR no real financial data found (only TOC)
    """
    if len(text) < 2000:
        return True
    
    # If PDF has > 50 pages, assume it's a complex report → use OCR
    if pdf_path:
        try:
            import PyPDF2
            with open(pdf_path, 'rb') as f:
                reader = PyPDF2.PdfReader(f)
                if len(reader.pages) > 50:
                    return True  # Complex report → OCR
        except:
            pass
    
    # Check for real financial data patterns
    import re
    
    # Pattern: keyword followed by LARGE numbers (financial data)
    data_pattern = r"(выручка|прибыль|актив|обязательств|капитал)[^\d]{0,100}(\d[\d\s\.,]{4,}\d)"
    data_matches = re.findall(data_pattern, text.lower(), re.IGNORECASE)
    
    # Count valid financial numbers (> 1 million but < 1 trillion)
    valid_data = 0
    for _, num_raw in data_matches:
        # Skip glued numbers (too many spaces)
        if num_raw.count(" ") > 4:
            continue
        
        # Skip too long numbers
        digits_only = num_raw.replace(" ", "").replace(".", "").replace(",", "")
        if len(digits_only) > 15:
            continue
        
        num = normalize_number(num_raw)
        if num and 1_000_000 < num < 1e12:
            valid_data += 1
    
    # If less than 10 large financial numbers found → text is poor (likely TOC)
    return valid_data < 10


# =========================
# VALIDATION
# =========================

def normalize_number(raw: str) -> float | None:
    """Normalize Russian number format to float."""
    try:
        raw = raw.strip()
        raw = raw.replace(" ", "").replace("\xa0", "").replace(",", ".")
        return float(raw)
    except (ValueError, AttributeError):
        return None


def is_valid_value(v: float | None) -> bool:
    """Check if value is in valid financial range."""
    if v is None:
        return False
    return MIN_VALID_VALUE < abs(v) < MAX_VALID_VALUE


# =========================
# METRIC EXTRACTION
# =========================

def extract_metrics(text: str) -> Dict[str, Metric]:
    """
    Extract financial metrics from text.
    
    Strategy:
    1. Split text into lines
    2. For each line with keyword, find ALL numbers
    3. Filter: skip years, skips glued numbers, skip too long
    4. Take the MAXIMUM valid number (real financial data is largest)
    """
    text_lower = text.lower()
    results: Dict[str, Metric] = {}
    
    # Split into lines for better processing
    lines = text_lower.split('\n')
    
    for metric, keywords in METRIC_KEYWORDS.items():
        if metric in results:
            continue
        
        valid_candidates = []
        matched_kw = None
        
        for line in lines:
            # Check if line contains any keyword
            line_has_keyword = False
            for kw in keywords:
                if kw in line:
                    line_has_keyword = True
                    matched_kw = kw
                    break
            
            if not line_has_keyword:
                continue
            
            # Find ALL numbers in line
            all_numbers = re.findall(r"\d[\d\s\.,]*\d", line)
            
            # Filter and collect valid candidates
            for num_raw in all_numbers:
                # 🚫 Skip glued numbers (too many spaces = multiple columns)
                if num_raw.count(" ") > 4:
                    logger.debug(f"  [SKIP] {num_raw[:30]}... (too many spaces)")
                    continue
                
                # 🚫 Skip too long numbers (parsing error)
                digits_only = num_raw.replace(" ", "").replace(".", "").replace(",", "")
                if len(digits_only) > 15:
                    logger.debug(f"  [SKIP] {num_raw[:30]}... (too many digits: {len(digits_only)})")
                    continue
                
                value = normalize_number(num_raw)
                
                if value and is_valid_value(value):
                    # 🚫 Skip years (1900-2100)
                    if 1900 < value < 2100:
                        logger.debug(f"  [SKIP] {value} (year)")
                        continue
                    
                    valid_candidates.append(value)
                    logger.debug(f"  [OK] {metric}: {value:,} via '{matched_kw}'")
        
        # 🎯 Choose the MAXIMUM valid candidate
        if valid_candidates:
            best_value = max(valid_candidates)
            results[metric] = build_metric(
                value=best_value,
                source="text_regex",
                method="max_candidate",
            )
            logger.info(f"[FINAL] {metric} = {best_value:,} (from {len(valid_candidates)} candidates)")
    
    return results


# =========================
# MAIN PIPELINE
# =========================

def extract_text_smart(pdf_path: str) -> tuple[str, str]:
    """
    Smart text extraction with OCR fallback.
    
    Returns:
        (text, source) where source is "pdf" or "ocr"
    """
    logger.info("=== START SMART TEXT EXTRACTION ===")
    
    # 1. Try PDF text layer
    text = extract_text_pdf(pdf_path)
    source = "pdf"
    
    # 2. Check if text is poor (TOC only, no financial data, or complex PDF)
    if is_text_poor(text, pdf_path):
        logger.info("Text is poor (TOC only or complex PDF) → switching to OCR as primary source")
        ocr_text = extract_text_ocr(pdf_path)
        if ocr_text:
            text = ocr_text
            source = "ocr"
            logger.info(f"OCR extracted {len(text)} chars")
        else:
            logger.warning("OCR failed, using PDF text anyway")
    
    logger.info(f"Final text: {len(text)} chars, source={source}")
    return text, source


def extract_financials(pdf_path: str) -> Dict[str, Any]:
    """
    Main extraction pipeline.
    
    Returns:
        Dict with metrics (with confidence), text_length, and source
    """
    # 1. Smart text extraction (PDF or OCR)
    text, source = extract_text_smart(pdf_path)
    
    # 2. Extract metrics
    metrics = extract_metrics(text)
    
    # 3. Filter by confidence
    reliable_metrics = filter_by_confidence(metrics, threshold=0.5)
    
    logger.info(f"Extracted metrics: {len(metrics)}")
    logger.info(f"Reliable metrics (>= 0.5): {len(reliable_metrics)}")
    
    return {
        "metrics": {k: v.value for k, v in reliable_metrics.items()},
        "metrics_with_confidence": metrics,
        "text_length": len(text),
        "source": source,
    }
