#!/usr/bin/env python
from src.analysis.pdf_extractor_pro import extract_text_pdf, is_text_poor

pdf_path = r"C:\Users\User\Downloads\Консолидированная финансовая отчетность ПАО «Магнит» за 2022 год.pdf"

text = extract_text_pdf(pdf_path)
print(f"Text length: {len(text)}")
print(f"is_text_poor(text, pdf_path): {is_text_poor(text, pdf_path)}")
