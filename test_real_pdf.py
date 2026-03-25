#!/usr/bin/env python
import pdfplumber
import re
from src.analysis.pdf_extractor_pro import normalize_number, is_valid_value

pdf_path = r"C:\Users\User\Downloads\Консолидированная финансовая отчетность ПАО «Магнит» за 2022 год.pdf"

with pdfplumber.open(pdf_path) as pdf:
    # Страница 11 где есть Выручка
    text = pdf.pages[10].extract_text() or ""
    
    print("=== Страница 11 ===")
    print(text[:500])
    print()
    
    # Поиск выручки - НОВЫЙ паттерн
    pattern = r"выручка.*?(\d{1,3}(?:[\s\.]?\d{3})*)"
    match = re.search(pattern, text.lower())
    
    if match:
        raw = match.group(1)
        print(f"Match: '{raw}'")
        value = normalize_number(raw)
        print(f"Normalized: {value}")
        print(f"Valid: {is_valid_value(value)}")
    else:
        print("No match")
