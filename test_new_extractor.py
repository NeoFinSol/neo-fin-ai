#!/usr/bin/env python
"""Тест нового extractor с confidence scoring и OCR fallback."""

from src.analysis.pdf_extractor_pro import extract_financials

pdf_path = r"C:\Users\User\Downloads\Консолидированная финансовая отчетность ПАО «Магнит» за 2022 год.pdf"

print("=" * 70)
print("НОВЫЙ EXTRACTOR: Магнит 2022")
print("=" * 70)

result = extract_financials(pdf_path)

print(f"\nТекст: {result['text_length']} символов")
print(f"Источник: {result['source']}")
print(f"\nНадёжные метрики ({len(result['metrics'])}):")
for k, v in sorted(result['metrics'].items()):
    if v and v > 1_000_000:
        print(f"  ✓ {k}: {v:,.0f}")
    elif v:
        print(f"  ✓ {k}: {v}")

print(f"\nВсе метрики с confidence ({len(result['metrics_with_confidence'])}):")
for k, m in sorted(result['metrics_with_confidence'].items()):
    if m.value:
        print(f"  {k}: {m.value:,.0f} (src={m.source}, conf={m.confidence})")

print("\n" + "=" * 70)
