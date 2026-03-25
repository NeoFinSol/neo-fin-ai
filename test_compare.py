#!/usr/bin/env python
from src.analysis.pdf_extractor_pro import extract_text_pdf, is_text_poor, extract_text_ocr

pdf_path = r"C:\Users\User\Downloads\Консолидированная финансовая отчетность ПАО «Магнит» за 2022 год.pdf"

print("PDF text...")
text = extract_text_pdf(pdf_path)
print(f"  Length: {len(text)}")
print(f"  is_text_poor: {is_text_poor(text)}")

print("\nOCR text...")
ocr = extract_text_ocr(pdf_path)
print(f"  Length: {len(ocr)}")
print(f"  First 200 chars: {ocr[:200]}")
