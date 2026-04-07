from __future__ import annotations

from collections.abc import Iterator, MutableMapping
from dataclasses import dataclass, field
from typing import Literal

ExtractionSource = Literal[
    "table_exact",
    "table_partial",
    "text_regex",
    "derived",
    "issuer_fallback",
    "llm",
    "table",
    "text",
    "ocr",
]
EvidenceVersion = Literal["v1", "v2"]
MatchSemantics = Literal[
    "exact",
    "code_match",
    "section_match",
    "keyword_match",
    "not_applicable",
]
InferenceMode = Literal["direct", "derived", "approximation", "policy_override"]
PostprocessState = Literal["none", "guardrail_adjusted"]


@dataclass(slots=True)
class ExtractionMetadata:
    value: float | None
    confidence: float
    source: ExtractionSource
    evidence_version: EvidenceVersion = "v1"
    match_semantics: MatchSemantics = "not_applicable"
    inference_mode: InferenceMode = "direct"
    postprocess_state: PostprocessState = "none"
    reason_code: str | None = None
    signal_flags: list[str] = field(default_factory=list)
    candidate_quality: int | None = None
    authoritative_override: bool = False


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
    source: str | None = None
    match_semantics: MatchSemantics | None = None
    inference_mode: InferenceMode | None = None
    reason_code: str | None = None
    signal_flags: list[str] = field(default_factory=list)
    conflict_count: int = 0
    postprocess_state: PostprocessState = "none"
    authoritative_override: bool = False


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
