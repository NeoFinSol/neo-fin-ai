#!/usr/bin/env python
from src.analysis.pdf_extractor_pro import extract_text_pdf, extract_metrics

pdf_path = r"C:\Users\User\Downloads\Консолидированная финансовая отчетность ПАО «Магнит» за 2022 год.pdf"

print("Извлечение текста...")
text = extract_text_pdf(pdf_path)
print(f"Текст: {len(text)} символов")

if text:
    print(f"выручка in text: {'выручка' in text.lower()}")
    print(f"прибыль in text: {'прибыль' in text.lower()}")
    
    print("\nИзвлечение метрик...")
    metrics = extract_metrics(text)
    print(f"Найдено метрик: {len(metrics)}")
    for k, m in metrics.items():
        print(f"  {k}: {m.value:,} (conf={m.confidence})")
else:
    print("Текст пуст!")
