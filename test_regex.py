#!/usr/bin/env python
import re

text = "выручка от реализации составила 1 234 567,89 рублей"

# Простой паттерн: keyword → любые символы → число
pattern = r"выручка.*?(\d[\d\s\.,]*\d)"
match = re.search(pattern, text, re.IGNORECASE)

print(f"Text: {text}")
print(f"Pattern: {pattern}")
print(f"Match: {match}")
if match:
    print(f"Group 1: '{match.group(1)}'")
    
    # Нормализация
    raw = match.group(1).replace(" ", "").replace(",", ".")
    print(f"Normalized: {raw}")
    try:
        print(f"Float: {float(raw)}")
    except:
        print("Can't convert to float")
