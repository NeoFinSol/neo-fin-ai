#!/usr/bin/env python
import re
from src.analysis.pdf_extractor_pro import extract_text_pdf, normalize_number

pdf_path = r"C:\Users\User\Downloads\Консолидированная финансовая отчетность ПАО «Магнит» за 2022 год.pdf"
text = extract_text_pdf(pdf_path)

data_pattern = r"(выручка|прибыль|актив|обязательств|капитал)[^\d]{0,100}(\d[\d\s\.,]{4,}\d)"
data_matches = re.findall(data_pattern, text.lower(), re.IGNORECASE)

print(f"Найдено совпадений: {len(data_matches)}")

valid_count = 0
for kw, num_raw in data_matches[:20]:  # первые 20
    # Skip glued
    if num_raw.count(" ") > 4:
        print(f"  SKIP (glued): {num_raw[:40]}")
        continue
    
    # Skip too long
    digits_only = num_raw.replace(" ", "").replace(".", "").replace(",", "")
    if len(digits_only) > 15:
        print(f"  SKIP (long): {num_raw[:40]} ({len(digits_only)} digits)")
        continue
    
    num = normalize_number(num_raw)
    if num and 1_000_000 < num < 1e12:
        valid_count += 1
        print(f"  VALID {kw}: {num:,}")
    else:
        print(f"  SKIP (range): {num:,}")

print(f"\nВалидных (> 1M, < 1T): {valid_count}")
print(f"is_text_poor: {valid_count < 5}")
