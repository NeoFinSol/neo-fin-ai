#!/usr/bin/env python
"""Быстрая проверка regex fallback на PDF Магнита."""
import sys
sys.path.insert(0, '.')

import pdfplumber
from src.controllers.analyze import _extract_metrics_with_regex
from src.analysis.ratios import calculate_ratios
from src.analysis.scoring import calculate_integral_score

pdf_path = r"C:\Users\User\Downloads\Консолидированная финансовая отчетность ПАО «Магнит» за 2022 год.pdf"

print("=" * 70)
print("ПРОВЕРКА REGEX FALLBACK: Магнит 2022")
print("=" * 70)

# Извлечение текста
print("\n1. Извлечение текста...")
text_parts = []
with pdfplumber.open(pdf_path) as pdf:
    for i, page in enumerate(pdf.pages[:15]):  # первые 15 страниц
        try:
            page_text = page.extract_text() or ""
            text_parts.append(page_text)
            print(f"   Страница {i+1}: {len(page_text)} символов")
        except Exception as e:
            print(f"   Страница {i+1}: ошибка - {e}")

text = "\n".join(text_parts)
print(f"\n   Всего текста: {len(text)} символов")

# Regex извлечение
print("\n2. Извлечение метрик regex...")
metrics = _extract_metrics_with_regex(text)
metrics_not_none = {k: v for k, v in metrics.items() if v is not None}
print(f"   Найдено метрик: {len(metrics_not_none)} из 15")
for k, v in metrics_not_none.items():
    print(f"   ✓ {k}: {v:,.0f}")

# Расчёт коэффициентов
print("\n3. Расчёт коэффициентов...")
if len(metrics_not_none) >= 5:
    ratios = calculate_ratios(metrics)
    ratios_not_none = {k: v for k, v in ratios.items() if v is not None}
    print(f"   Рассчитано коэффициентов: {len(ratios_not_none)} из 13")
    for k, v in ratios_not_none.items():
        print(f"   ✓ {k}: {v:.4f}")
    
    # Скоринг
    print("\n4. Скоринг...")
    score_data = calculate_integral_score(ratios)
    print(f"   Score: {score_data['score']}")
    print(f"   Risk level: {score_data['risk_level']}")
else:
    print("   Недостаточно метрик для расчёта!")

print("\n" + "=" * 70)
