#!/usr/bin/env python
import pdfplumber

pdf_path = r"C:\Users\User\Downloads\Консолидированная финансовая отчетность ПАО «Магнит» за 2022 год.pdf"

with pdfplumber.open(pdf_path) as pdf:
    print(f"Всего страниц: {len(pdf.pages)}")
    
    for i in [0, 9, 10, 11, 12]:
        if i < len(pdf.pages):
            text = pdf.pages[i].extract_text() or ""
            print(f"\n=== Страница {i+1} ({len(text)} символов) ===")
            print(text[:300])
            
            if "выручка" in text.lower():
                print("✓ Выручка найдена")
            if "прибыль" in text.lower():
                print("✓ Прибыль найдена")
            if "актив" in text.lower():
                print("✓ Активы найдены")
