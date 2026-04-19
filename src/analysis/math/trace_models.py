from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TraceSeed:
    metric_key: str
    formula_id: str | None
    source_refs: tuple[str, ...]
    period_ref: str | None
    formula_version: str | None = None
