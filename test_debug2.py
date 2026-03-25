#!/usr/bin/env python
from src.analysis.pdf_extractor_pro import extract_text_pdf, extract_metrics

pdf_path = r"C:\Users\User\Downloads\Консолидированная финансовая отчетность ПАО «Магнит» за 2022 год.pdf"

text = extract_text_pdf(pdf_path)
print(f"Text length: {len(text)}")

# Показать первые вхождения ключевых слов
keywords = ["выручка", "прибыль", "актив"]
for kw in keywords:
    idx = text.lower().find(kw)
    if idx >= 0:
        snippet = text[max(0, idx-20):idx+100]
        print(f"\n'{kw}' at {idx}:")
        print(f"  {snippet!r}")

# Тест extract_metrics
print("\n\n=== extract_metrics ===")
metrics = extract_metrics(text)
print(f"Found: {len(metrics)} metrics")
for k, m in metrics.items():
    print(f"  {k}: {m.value:,} (conf={m.confidence})")
