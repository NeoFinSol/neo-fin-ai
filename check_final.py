#!/usr/bin/env python
"""Финальная проверка pipeline с OCR."""
import sys
sys.path.insert(0, '.')

from src.analysis.pdf_extractor import extract_tables, parse_financial_statements_with_metadata
from src.analysis.ratios import calculate_ratios
from src.analysis.scoring import calculate_integral_score

pdf_path = r"C:\Users\User\Downloads\Консолидированная финансовая отчетность ПАО «Магнит» за 2022 год.pdf"

print("=" * 70)
print("ФИНАЛЬНАЯ ПРОВЕРКА: Магнит 2022 (OCR + camelot)")
print("=" * 70)

# Извлечение таблиц (с автоматическим выбором OCR)
print("\n1. Извлечение таблиц (camelot + OCR)...")
tables = extract_tables(pdf_path, force_ocr=False)  # False = автоматический выбор
print(f"   Найдено таблиц: {len(tables)}")
for i, t in enumerate(tables[:3]):
    flavor = t.get('flavor', 'unknown')
    rows = t.get('rows', [])
    print(f"   Таблица {i+1} ({flavor}): {len(rows)} строк")

# Извлечение метрик
print("\n2. Извлечение метрик...")
text = ""  # текст не нужен, если есть OCR в таблицах
metadata = parse_financial_statements_with_metadata(tables, text)
metrics = {k: v.value for k, v in metadata.items() if v.value is not None}
print(f"   Извлечено метрик: {len(metrics)} из 15")
for k, v in sorted(metrics.items()):
    if v and v > 1000000:  # показываем только крупные числа
        print(f"   ✓ {k}: {v:,.0f}")
    elif v:
        print(f"   ✓ {k}: {v}")

# Расчёт коэффициентов
print("\n3. Расчёт коэффициентов...")
if len(metrics) >= 5:
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
print("ПРОВЕРКА ЗАВЕРШЕНА")
print("=" * 70)
