#!/usr/bin/env python
from src.analysis.pdf_extractor_pro import extract_text_ocr, extract_metrics

pdf_path = r"C:\Users\User\Downloads\Консолидированная финансовая отчетность ПАО «Магнит» за 2022 год.pdf"

print("OCR текст...")
text = extract_text_ocr(pdf_path)
print(f"Длина: {len(text)}")
print(f"Первые 500 символов:")
print(text[:500])

print("\n\nИзвлечение метрик...")
metrics = extract_metrics(text)
print(f"Найдено: {len(metrics)}")
for k, m in metrics.items():
    print(f"  {k}: {m.value:,}")
