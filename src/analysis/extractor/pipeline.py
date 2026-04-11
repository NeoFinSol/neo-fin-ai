from __future__ import annotations

import inspect
from dataclasses import dataclass, field

from . import legacy_helpers, semantics
from .confidence_policy import ConfidencePolicy
from .guardrails import apply_result_guardrails, derive_missing_metrics
from .ranking import build_metadata_from_candidate, build_metadata_with_decision_log
from .rules import _METRIC_KEYWORDS
from .tables import collect_table_candidates
from .text_extraction import (
    _detect_scale_factor,
    _normalize_metric_text,
    collect_text_candidates,
)
from .decision_trace import _build_candidate_id
from .types import DocumentSignals, ExtractionMetadata, ExtractorContext, RawCandidates

_RATIO_KEYS = frozenset(
    {
        "roa",
        "roe",
        "current_ratio",
        "equity_ratio",
        "debt_to_revenue",
    }
)


@dataclass(slots=True)
class ExtractorStageTrace:
    context: ExtractorContext
    raw_candidates: RawCandidates
    guardrail_events: list[semantics.GuardrailEvent]
    winner_map: dict[str, str | None] = field(default_factory=dict)


def _build_context(tables: list, text: str) -> ExtractorContext:
    normalized_text = _normalize_metric_text(text or "")
    text_lower = normalized_text.lower()
    has_russian_balance_header = "бухгалтерский баланс" in text_lower
    has_russian_results_header = "отчет о финансовых результатах" in text_lower
    signals = DocumentSignals(
        text=normalized_text,
        text_lower=text_lower,
        has_russian_balance_header=has_russian_balance_header,
        has_russian_results_header=has_russian_results_header,
        is_form_like=(
            "форма 071000" in text_lower
            or has_russian_balance_header
            or has_russian_results_header
        ),
        is_balance_like=(
            has_russian_balance_header
            or "форма 0710001" in text_lower
            or "итого по разделу iii" in text_lower
            or "итого по разделу ш" in text_lower
            or "итого по разделу iv" in text_lower
            or "итого по разделу v" in text_lower
            or "итого по разделу у" in text_lower
        ),
        scale_factor=_detect_scale_factor(normalized_text),
    )
    return ExtractorContext(tables=tables or [], text=normalized_text, signals=signals)


def _collect_table_candidates(
    context: ExtractorContext,
    raw: RawCandidates,
) -> None:
    collect_table_candidates(context, raw)


def _collect_text_candidates(
    context: ExtractorContext,
    raw: RawCandidates,
    *,
    guardrail_events: list[semantics.GuardrailEvent] | None = None,
) -> None:
    collect_text_candidates(context, raw, guardrail_events=guardrail_events)


def _derive_missing_metrics(
    context: ExtractorContext,
    raw: RawCandidates,
    *,
    guardrail_events: list[semantics.GuardrailEvent] | None = None,
) -> None:
    derive_missing_metrics(context, raw, guardrail_events=guardrail_events)


def _build_metadata_result(
    context: ExtractorContext,
    raw: RawCandidates,
    *,
    guardrail_events: list[semantics.GuardrailEvent] | None = None,
    include_decision_logs: bool = False,
    confidence_policy: ConfidencePolicy | None = None,
    winner_map: dict[str, str | None] | None = None,
) -> (
    dict[str, ExtractionMetadata]
    | tuple[dict[str, ExtractionMetadata], dict[str, semantics.SemanticsDecisionLog]]
):
    result: dict[str, ExtractionMetadata] = {}
    decision_logs: dict[str, semantics.SemanticsDecisionLog] | None = (
        {} if include_decision_logs else None
    )
    for key in _METRIC_KEYWORDS:
        candidate = raw.get(key)
        if candidate is None:
            result[key] = ExtractionMetadata(
                value=None,
                confidence=0.0,
                source="derived",
                evidence_version=semantics.V2,
                match_semantics=semantics.MATCH_NA,
                inference_mode=semantics.MODE_DERIVED,
                postprocess_state=semantics.POSTPROCESS_NONE,
                reason_code=None,
                signal_flags=[],
                candidate_quality=None,
                authoritative_override=False,
            )
            continue

        if decision_logs is None:
            metadata = build_metadata_from_candidate(
                candidate,
                confidence_policy=confidence_policy,
            )
        else:
            metadata, decision_log = build_metadata_with_decision_log(
                key,
                candidate,
                confidence_policy=confidence_policy,
            )
            decision_logs[key] = decision_log
        value = metadata.value
        if context.signals.scale_factor != 1.0 and key not in _RATIO_KEYS:
            value = value * context.signals.scale_factor

        result[key] = ExtractionMetadata(
            value=value,
            confidence=metadata.confidence,
            source=metadata.source,
            evidence_version=metadata.evidence_version,
            match_semantics=metadata.match_semantics,
            inference_mode=metadata.inference_mode,
            postprocess_state=metadata.postprocess_state,
            reason_code=metadata.reason_code,
            signal_flags=list(metadata.signal_flags),
            candidate_quality=metadata.candidate_quality,
            authoritative_override=metadata.authoritative_override,
        )

    apply_result_guardrails(
        context,
        result,
        guardrail_events=guardrail_events,
    )

    if winner_map is not None:
        for key in _METRIC_KEYWORDS:
            candidate = raw.get(key)
            if candidate is not None and result[key].value is not None:
                winner_map[key] = _build_candidate_id(key, candidate)
            else:
                winner_map[key] = None

    if decision_logs is None:
        return result

    decision_logs = {
        key: log for key, log in decision_logs.items() if result[key].value is not None
    }
    return result, decision_logs


def _invoke_stage_collector(
    collector,
    context: ExtractorContext,
    raw: RawCandidates,
    *,
    guardrail_events: list[semantics.GuardrailEvent],
) -> None:
    try:
        signature = inspect.signature(collector)
    except (TypeError, ValueError):
        collector(context, raw, guardrail_events=guardrail_events)
        return

    if "guardrail_events" in signature.parameters:
        collector(context, raw, guardrail_events=guardrail_events)
        return

    collector(context, raw)


def _invoke_metadata_builder(
    builder,
    context: ExtractorContext,
    raw: RawCandidates,
    *,
    guardrail_events: list[semantics.GuardrailEvent],
    include_decision_logs: bool,
    confidence_policy: ConfidencePolicy | None,
    winner_map: dict[str, str | None] | None = None,
):
    try:
        signature = inspect.signature(builder)
    except (TypeError, ValueError):
        return builder(
            context,
            raw,
            guardrail_events=guardrail_events,
            include_decision_logs=include_decision_logs,
            confidence_policy=confidence_policy,
            winner_map=winner_map,
        )

    kwargs = {}
    if "guardrail_events" in signature.parameters:
        kwargs["guardrail_events"] = guardrail_events
    if "include_decision_logs" in signature.parameters:
        kwargs["include_decision_logs"] = include_decision_logs
    if "confidence_policy" in signature.parameters:
        kwargs["confidence_policy"] = confidence_policy
    if "winner_map" in signature.parameters:
        kwargs["winner_map"] = winner_map
    return builder(context, raw, **kwargs)


def parse_financial_statements_with_metadata(
    tables: list,
    text: str,
) -> dict[str, ExtractionMetadata]:
    trace = build_extractor_trace(tables, text)
    return build_metadata_from_trace(trace)


def parse_financial_statements(tables: list, text: str) -> dict[str, float | None]:
    metadata = parse_financial_statements_with_metadata(tables, text)
    return {key: meta.value for key, meta in metadata.items()}


def build_extractor_trace(
    tables: list,
    text: str,
) -> ExtractorStageTrace:
    context = _build_context(tables, text)
    raw = RawCandidates()
    guardrail_events: list[semantics.GuardrailEvent] = []

    _collect_table_candidates(context, raw)
    _invoke_stage_collector(
        _collect_text_candidates,
        context,
        raw,
        guardrail_events=guardrail_events,
    )
    _invoke_stage_collector(
        _derive_missing_metrics,
        context,
        raw,
        guardrail_events=guardrail_events,
    )
    return ExtractorStageTrace(
        context=context,
        raw_candidates=raw,
        guardrail_events=guardrail_events,
    )


def build_metadata_from_trace(
    trace: ExtractorStageTrace,
    *,
    confidence_policy: ConfidencePolicy | None = None,
    include_decision_logs: bool = False,
) -> (
    dict[str, ExtractionMetadata]
    | tuple[dict[str, ExtractionMetadata], dict[str, semantics.SemanticsDecisionLog]]
):
    winner_map: dict[str, str | None] = {}
    result = _invoke_metadata_builder(
        _build_metadata_result,
        trace.context,
        trace.raw_candidates,
        guardrail_events=trace.guardrail_events,
        include_decision_logs=include_decision_logs,
        confidence_policy=confidence_policy,
        winner_map=winner_map,
    )
    trace.winner_map = winner_map
    return result


def parse_financial_statements_debug(
    tables: list,
    text: str,
) -> semantics.ExtractionDebugTrace:
    trace = build_extractor_trace(tables, text)
    metadata, decision_logs = build_metadata_from_trace(
        trace,
        include_decision_logs=True,
    )
    return semantics.ExtractionDebugTrace(
        metadata=metadata,
        decision_logs=decision_logs,
        guardrail_events=trace.guardrail_events,
        winner_map=trace.winner_map,
    )


def format_metric_debug_trace(
    debug_trace: semantics.ExtractionDebugTrace,
    metric_key: str,
) -> str:
    return semantics.format_metric_decision_trace(
        debug_trace.decision_logs[metric_key],
        debug_trace.guardrail_events,
    )
