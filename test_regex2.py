#!/usr/bin/env python
import re
from src.analysis.pdf_extractor_pro import normalize_number

# Тестовые строки из PDF
test_cases = [
    "выручка 2 351 996 423",
    "прибыль до налогообложения 42 864 550",
    "активы всего 1 395 998 440",
]

for test in test_cases:
    pattern = r"выручка.*?(\d[\d\s\.,]*\d)"
    match = re.search(pattern, test, re.IGNORECASE)
    
    print(f"Text: {test}")
    print(f"Pattern: {pattern}")
    print(f"Match: {match}")
    if match:
        raw = match.group(1)
        print(f"Raw: '{raw}'")
        normalized = normalize_number(raw)
        print(f"Normalized: {normalized}")
    print()
