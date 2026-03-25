#!/usr/bin/env python
import re
from src.analysis.pdf_extractor_pro import normalize_number

pdf_text = "Выручка по договорам с покупателями 65\n25. Себестоимость реализации 65\nВыручка 2 351 996 423"

# TOC pattern
toc_pattern = r"(выручка|прибыль|актив)[^\d]{0,50}(\d{1,3})\s*$"
toc_matches = re.findall(toc_pattern, pdf_text.lower(), re.MULTILINE)
print(f"TOC matches: {len(toc_matches)}")
for m in toc_matches:
    print(f"  {m}")

# Data pattern
data_pattern = r"(выручка|прибыль|актив)[^\d]{0,50}(\d[\d\s\.,]{4,}\d)"
data_matches = re.findall(data_pattern, pdf_text.lower(), re.IGNORECASE)
print(f"\nData matches: {len(data_matches)}")
for m in data_matches:
    num = normalize_number(m[1])
    print(f"  {m[0]}: {m[1]} → {num}")
