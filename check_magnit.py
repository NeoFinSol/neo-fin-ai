#!/usr/bin/env python
"""Проверка извлечения метрик из PDF Магнита."""
import sys
sys.path.insert(0, '.')

from src.analysis.pdf_extractor import extract_tables, extract_text_from_scanned, is_scanned_pdf, parse_financial_statements, parse_financial_statements_with_metadata
from src.analysis.ratios import calculate_ratios
from src.analysis.scoring import calculate_integral_score

pdf_path = r"C:\Users\User\Downloads\Консолидированная финансовая отчетность ПАО «Магнит» за 2022 год.pdf"

print("=" * 70)
print(f"ПРОВЕРКА PDF: {pdf_path}")
print("=" * 70)

# Проверка типа PDF
print("\n1. Проверка типа PDF...")
try:
    scanned = is_scanned_pdf(pdf_path)
    print(f"   Это скан: {scanned}")
except Exception as e:
    print(f"   Ошибка проверки: {e}")
    scanned = True

# Извлечение таблиц
print("\n2. Извлечение таблиц camelot...")
try:
    tables = extract_tables(pdf_path)
    print(f"   Найдено таблиц: {len(tables)}")
    if tables:
        for i, t in enumerate(tables[:3]):
            rows = t.get('rows', [])
            print(f"   Таблица {i+1}: {len(rows)} строк")
            if rows:
                print(f"      Пример: {rows[0][:3] if len(rows[0]) > 3 else rows[0]}")
except Exception as e:
    print(f"   Ошибка извлечения таблиц: {e}")
    tables = []

# Извлечение текста
print("\n3. Извлечение текста...")
try:
    if scanned:
        text = extract_text_from_scanned(pdf_path)
    else:
        import pdfplumber
        text_parts = []
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages[:10]:  # первые 10 страниц
                page_text = page.extract_text() or ""
                text_parts.append(page_text)
        text = "\n".join(text_parts)
    
    print(f"   Длина текста: {len(text)} символов")
    print(f"   Первые 500 символов: {text[:500]}...")
    
    # Поиск ключевых слов
    print("\n   Поиск ключевых метрик в тексте...")
    keywords = ['Выручка', 'Чистая прибыль', 'Итого активов', 'Итого капитала', 'Итого обязательств']
    for kw in keywords:
        import re
        pattern = rf"{kw}[:\s\.]+([0-9\s,\.]+)"
        matches = re.findall(pattern, text, re.IGNORECASE)
        if matches:
            print(f"   ✓ {kw}: {matches[:3]}")
        else:
            print(f"   ✗ {kw}: не найдено")
except Exception as e:
    print(f"   Ошибка извлечения текста: {e}")
    import traceback
    traceback.print_exc()
    text = ""

# Извлечение метрик
print("\n4. Извлечение метрик...")
try:
    metadata = parse_financial_statements_with_metadata(tables, text)
    metrics = {k: v.value for k, v in metadata.items() if v.value is not None}
    print(f"   Извлечено метрик: {len(metrics)} из 15")
    for k, v in metrics.items():
        print(f"   ✓ {k}: {v:,.0f}")
    
    if len(metrics) < 5:
        print("\n   ⚠ МАЛО МЕТРИК! Пробую regex fallback...")
        from src.controllers.analyze import _extract_metrics_with_regex
        regex_metrics = _extract_metrics_with_regex(text)
        print(f"   Regex нашёл: {len([v for v in regex_metrics.values() if v is not None])} метрик")
        for k, v in regex_metrics.items():
            if v is not None and k not in metrics:
                print(f"   ✓ {k}: {v:,.0f} (из текста)")
                metrics[k] = v
except Exception as e:
    print(f"   Ошибка извлечения метрик: {e}")
    import traceback
    traceback.print_exc()
    metrics = {}

# Расчёт коэффициентов
print("\n5. Расчёт коэффициентов...")
if metrics:
    try:
        ratios = calculate_ratios(metrics)
        ratios_not_none = {k: v for k, v in ratios.items() if v is not None}
        print(f"   Рассчитано коэффициентов: {len(ratios_not_none)} из 13")
        for k, v in ratios_not_none.items():
            print(f"   ✓ {k}: {v:.4f}")
    except Exception as e:
        print(f"   Ошибка расчёта коэффициентов: {e}")
        ratios = {}
else:
    print("   Нет метрик для расчёта!")
    ratios = {}

# Скоринг
print("\n6. Интегральный скоринг...")
if ratios:
    try:
        score_data = calculate_integral_score(ratios)
        print(f"   Score: {score_data['score']}")
        print(f"   Risk level: {score_data['risk_level']}")
        print(f"   Факторов: {len(score_data.get('details', {}))}")
    except Exception as e:
        print(f"   Ошибка скоринга: {e}")
else:
    print("   Нет коэффициентов для скоринга!")

print("\n" + "=" * 70)
print("ПРОВЕРКА ЗАВЕРШЕНА")
print("=" * 70)
