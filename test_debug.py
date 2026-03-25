#!/usr/bin/env python
from src.analysis.pdf_extractor_pro import normalize_number, is_valid_value, METRIC_KEYWORDS
import re

# Симуляция текста из PDF
text = "выручка от реализации 2 351 996 423 тысячачистая прибыль 42 864 550итого активов 1 395 998 440"
text_lower = text.lower()

print(f"Text: {text[:100]}...")
print(f"Text length: {len(text)}")

for metric, keywords in METRIC_KEYWORDS.items():
    print(f"\n=== {metric} ===")
    for kw in keywords:
        pattern = rf"{kw}.*?(\d[\d\s\.,]*\d)"
        match = re.search(pattern, text_lower, re.IGNORECASE)
        
        if match:
            raw = match.group(1)
            value = normalize_number(raw)
            print(f"  kw='{kw}': raw='{raw}', value={value}, valid={is_valid_value(value)}")
        else:
            print(f"  kw='{kw}': no match")
