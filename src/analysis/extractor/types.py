from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

ExtractionSource = Literal[
    "table_exact", "table_partial", "text_regex", "derived", "issuer_fallback"
]


@dataclass
class ExtractionMetadata:
    value: float | None
    confidence: float
    source: ExtractionSource
