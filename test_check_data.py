#!/usr/bin/env python
import re
from src.analysis.pdf_extractor_pro import extract_text_pdf, normalize_number

pdf_path = r"C:\Users\User\Downloads\Консолидированная финансовая отчетность ПАО «Магнит» за 2022 год.pdf"
text = extract_text_pdf(pdf_path)

# Найти ВСЕ числа в тексте
all_numbers = re.findall(r"\d[\d\s\.,]*\d", text)
print(f"Всего чисел: {len(all_numbers)}")

# Посчитать большие (> 1 млн)
large = [n for n in all_numbers if normalize_number(n) and normalize_number(n) > 1_000_000]
print(f"Большие (> 1M): {len(large)}")

# Показать первые 10 больших
print("\nПервые 10 больших:")
for n in large[:10]:
    print(f"  {normalize_number(n):,}")

# Проверить есть ли финансовые ключевые слова рядом с большими числами
financial_keywords = ["выручка", "прибыль", "актив", "обязательств", "капитал"]
found_data = False
for kw in financial_keywords:
    pattern = rf"{kw}[^\d]{{0,100}}(\d[\d\s\.,]*\d)"
    matches = re.findall(pattern, text.lower())
    valid = [m for m in matches if normalize_number(m) and normalize_number(m) > 100_000]
    if valid:
        found_data = True
        print(f"\n{kw}: {len(valid)} больших чисел")
        print(f"  Пример: {valid[0]}")

print(f"\nЕсть финансовые данные: {found_data}")
