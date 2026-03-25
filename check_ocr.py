#!/usr/bin/env python
"""Проверка OCR на PDF Магнита."""
import sys
sys.path.insert(0, '.')

from pdf2image import convert_from_path
import pytesseract

pdf_path = r"C:\Users\User\Downloads\Консолидированная финансовая отчетность ПАО «Магнит» за 2022 год.pdf"

print("=" * 70)
print("ПРОВЕРКА OCR: Магнит 2022 (страницы 3-8)")
print("=" * 70)

# Конвертация страниц 3-5 в изображения
print("\n1. Конвертация PDF в изображения...")
try:
    images = convert_from_path(pdf_path, first_page=3, last_page=5, dpi=300)
    print(f"   ✓ Конвертировано страниц: {len(images)}")
except Exception as e:
    print(f"   ✗ Ошибка конвертации: {e}")
    sys.exit(1)

# OCR каждой страницы
print("\n2. Распознавание текста (OCR)...")
for i, image in enumerate(images, start=3):
    print(f"\n   Страница {i}:")
    try:
        text = pytesseract.image_to_string(image, lang='rus+eng')
        print(f"   ✓ Распознано: {len(text)} символов")
        
        # Поиск ключевых слов
        keywords = ['Выручка', 'Прибыль', 'Актив', 'Капитал', 'Обязательств']
        for kw in keywords:
            if kw.lower() in text.lower():
                # Найти число рядом с ключевым словом
                import re
                pattern = rf"{kw}[:\s\.]+([0-9\s,\.]+)"
                matches = re.findall(pattern, text, re.IGNORECASE)
                if matches:
                    print(f"      ✓ {kw}: {matches[0]}")
    except Exception as e:
        print(f"   ✗ Ошибка OCR: {e}")

print("\n" + "=" * 70)
print("OCR ПРОВЕРКА ЗАВЕРШЕНА")
print("=" * 70)
