from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CandidateProvenance:
    producer: str
    source_inputs: tuple[str, ...]
    derivation_mode: str | None
    source_metric_keys: tuple[str, ...]
    source_period_ref: str | None
    extractor_source_ref: str | None
    resolver_id: str | None
