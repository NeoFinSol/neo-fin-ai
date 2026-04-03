from __future__ import annotations

from collections.abc import Iterator, MutableMapping
from dataclasses import dataclass, field
from typing import Literal

ExtractionSource = Literal[
    "table_exact", "table_partial", "text_regex", "derived", "issuer_fallback"
]


@dataclass(slots=True)
class ExtractionMetadata:
    value: float | None
    confidence: float
    source: ExtractionSource


@dataclass(slots=True)
class DocumentSignals:
    text: str
    text_lower: str
    has_russian_balance_header: bool
    has_russian_results_header: bool
    is_form_like: bool
    is_balance_like: bool
    scale_factor: float


@dataclass(slots=True)
class ExtractorContext:
    tables: list
    text: str
    signals: DocumentSignals
    form_pnl_code_candidates: dict[str, float] = field(default_factory=dict)


@dataclass(slots=True)
class RawMetricCandidate:
    value: float
    match_type: str
    is_exact: bool
    candidate_quality: int = 50


@dataclass
class RawCandidates(MutableMapping[str, RawMetricCandidate]):
    _items: dict[str, RawMetricCandidate] = field(default_factory=dict)

    def __getitem__(self, key: str) -> RawMetricCandidate:
        return self._items[key]

    def __setitem__(self, key: str, value: RawMetricCandidate) -> None:
        self._items[key] = value

    def __delitem__(self, key: str) -> None:
        del self._items[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self._items)

    def __len__(self) -> int:
        return len(self._items)

    def get_value(self, key: str) -> float | None:
        candidate = self._items.get(key)
        return candidate.value if candidate is not None else None

    def as_legacy_dict(self) -> dict[str, tuple[float, str, bool, int]]:
        return {
            key: (
                candidate.value,
                candidate.match_type,
                candidate.is_exact,
                candidate.candidate_quality,
            )
            for key, candidate in self._items.items()
        }
