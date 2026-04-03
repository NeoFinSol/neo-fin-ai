from __future__ import annotations

from dataclasses import dataclass

from . import legacy_helpers
from .rules import _METRIC_KEYWORDS
from .types import ExtractionMetadata


@dataclass(slots=True)
class PipelineContext:
    tables: list
    text: str


def _build_context(tables: list, text: str) -> PipelineContext:
    return PipelineContext(tables=tables or [], text=text or "")


def _collect_candidates(context: PipelineContext) -> dict[str, object]:
    return legacy_helpers.parse_financial_statements_with_metadata(
        context.tables,
        context.text,
    )


def _build_metadata_result(
    collected: dict[str, object],
) -> dict[str, ExtractionMetadata]:
    result: dict[str, ExtractionMetadata] = {}
    for key in _METRIC_KEYWORDS:
        item = collected[key]
        result[key] = ExtractionMetadata(
            value=getattr(item, "value"),
            confidence=getattr(item, "confidence"),
            source=getattr(item, "source"),
        )
    return result


def parse_financial_statements_with_metadata(
    tables: list,
    text: str,
) -> dict[str, ExtractionMetadata]:
    context = _build_context(tables, text)
    collected = _collect_candidates(context)
    return _build_metadata_result(collected)


def parse_financial_statements(tables: list, text: str) -> dict[str, float | None]:
    metadata = parse_financial_statements_with_metadata(tables, text)
    return {k: v.value for k, v in metadata.items()}
