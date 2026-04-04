from __future__ import annotations

import logging

from . import legacy_helpers, semantics
from .ranking import _raw_set, _source_priority
from .types import (
    ExtractionMetadata,
    ExtractorContext,
    RawCandidates,
    RawMetricCandidate,
)

logger = logging.getLogger(__name__)


def _metric_candidate_quality(metric_key: str, candidate_text: str) -> int | None:
    return legacy_helpers._metric_candidate_quality(metric_key, candidate_text)


def _derive_current_assets_from_available(
    raw: RawCandidates | dict[str, tuple[float, str, bool, int]],
) -> float | None:
    if isinstance(raw, RawCandidates):
        cash = raw.get_value("cash_and_equivalents")
        inventory = raw.get_value("inventory")
        receivables = raw.get_value("accounts_receivable")
        total_assets = raw.get_value("total_assets")
        equity = raw.get_value("equity")
        liabilities = raw.get_value("liabilities")
    else:
        cash = raw["cash_and_equivalents"][0] if "cash_and_equivalents" in raw else None
        inventory = raw["inventory"][0] if "inventory" in raw else None
        receivables = (
            raw["accounts_receivable"][0] if "accounts_receivable" in raw else None
        )
        total_assets = raw["total_assets"][0] if "total_assets" in raw else None
        equity = raw["equity"][0] if "equity" in raw else None
        liabilities = raw["liabilities"][0] if "liabilities" in raw else None

    components = [
        value for value in (cash, inventory, receivables) if value is not None
    ]
    if len(components) >= 2:
        return sum(components)

    if total_assets is not None and equity is not None and liabilities is not None:
        derived = total_assets - equity - liabilities
        if derived > 0:
            return derived
    return None


def _apply_form_like_pnl_sanity(
    raw: RawCandidates | dict[str, tuple[float, str, bool, int]],
    code_candidates: dict[str, float],
    *,
    is_standalone_form: bool = False,
) -> None:
    def _entry_value(entry: RawMetricCandidate | tuple) -> float:
        return entry.value if isinstance(entry, RawMetricCandidate) else entry[0]

    def _entry_priority(entry: RawMetricCandidate | tuple) -> int:
        if isinstance(entry, RawMetricCandidate):
            return _source_priority(entry.match_type, entry.is_exact)
        return _source_priority(entry[1], entry[2])

    def _entry_quality(entry: RawMetricCandidate | tuple) -> int:
        if isinstance(entry, RawMetricCandidate):
            return entry.candidate_quality
        return entry[3] if len(entry) > 3 else 50

    revenue_entry = raw.get("revenue")
    net_profit_entry = raw.get("net_profit")
    if revenue_entry is None or net_profit_entry is None:
        return

    revenue = _entry_value(revenue_entry)
    net_profit = _entry_value(net_profit_entry)

    if revenue <= 0:
        return

    current_margin = abs(net_profit) / revenue
    if current_margin <= 0.6:
        return

    if is_standalone_form:
        return

    revenue_code = code_candidates.get("revenue")
    net_profit_code = code_candidates.get("net_profit")
    if revenue_code is not None and net_profit_code is not None:
        _raw_set(
            raw,
            "revenue",
            revenue_code,
            "text_regex",
            True,
            candidate_quality=120,
            source=semantics.SOURCE_TEXT,
            match_semantics=semantics.MATCH_CODE,
            inference_mode=semantics.MODE_DIRECT,
            signal_flags=["ev:line_code"],
        )
        return

    revenue_priority = _entry_priority(revenue_entry)
    net_profit_priority = _entry_priority(net_profit_entry)
    if revenue_priority >= 3 or net_profit_priority >= 3:
        return

    best_revenue = revenue
    best_net_profit = net_profit
    best_margin = current_margin

    candidate_pairs = [
        (revenue_code, net_profit),
        (revenue, net_profit_code),
        (revenue_code, net_profit_code),
    ]
    for candidate_revenue, candidate_net_profit in candidate_pairs:
        if (
            candidate_revenue is None
            or candidate_net_profit is None
            or candidate_revenue <= 0
        ):
            continue

        candidate_margin = abs(candidate_net_profit) / candidate_revenue
        if candidate_margin < best_margin:
            best_margin = candidate_margin
            best_revenue = candidate_revenue
            best_net_profit = candidate_net_profit

    if best_revenue != revenue:
        _raw_set(
            raw,
            "revenue",
            best_revenue,
            "text_regex",
            True,
            candidate_quality=120,
            source=semantics.SOURCE_TEXT,
            match_semantics=semantics.MATCH_CODE,
            inference_mode=semantics.MODE_DIRECT,
            signal_flags=["ev:line_code"],
        )
        revenue_entry = raw["revenue"]
    if best_net_profit != net_profit:
        _raw_set(
            raw,
            "net_profit",
            best_net_profit,
            "text_regex",
            True,
            candidate_quality=120,
            source=semantics.SOURCE_TEXT,
            match_semantics=semantics.MATCH_CODE,
            inference_mode=semantics.MODE_DIRECT,
            signal_flags=["ev:line_code"],
        )
        net_profit_entry = raw["net_profit"]

    revenue = _entry_value(revenue_entry)
    net_profit = _entry_value(net_profit_entry)
    if revenue <= 0:
        return

    margin_after_fallback = abs(net_profit) / revenue
    if margin_after_fallback <= 0.6:
        return

    revenue_quality = _entry_quality(revenue_entry)
    net_profit_quality = _entry_quality(net_profit_entry)
    revenue_reliability = revenue_priority * 100 + revenue_quality
    net_profit_reliability = net_profit_priority * 100 + net_profit_quality

    if revenue_reliability < net_profit_reliability:
        conflicting_key = "revenue"
    elif net_profit_reliability < revenue_reliability:
        conflicting_key = "net_profit"
    elif "net_profit" in code_candidates and "revenue" not in code_candidates:
        conflicting_key = "revenue"
    elif "revenue" in code_candidates and "net_profit" not in code_candidates:
        conflicting_key = "net_profit"
    else:
        conflicting_key = "net_profit"

    logger.warning(
        "Dropping %s due to P&L sanity conflict: revenue=%s, net_profit=%s, margin=%s, reliability=(revenue:%s, net_profit:%s)",
        conflicting_key,
        revenue,
        net_profit,
        margin_after_fallback,
        revenue_reliability,
        net_profit_reliability,
    )
    raw.pop(conflicting_key, None)


def _derive_liabilities_from_components(
    long_term: float | None,
    short_term: float | None,
    total_assets: float | None,
    equity: float | None,
) -> float | None:
    return legacy_helpers._derive_liabilities_from_components(
        long_term,
        short_term,
        total_assets,
        equity,
    )


def derive_missing_metrics(
    context: ExtractorContext,
    raw: RawCandidates,
) -> None:
    if "liabilities" not in raw:
        long_term = raw.get_value("long_term_liabilities")
        if long_term is None and (
            context.tables or not context.signals.is_balance_like
        ):
            long_term = legacy_helpers._extract_section_total(
                context.tables,
                context.signals.text_lower,
                ["итого по разделу iv", "итого долгосрочных обязательств"],
            )
        short_term = raw.get_value("short_term_liabilities")
        total_assets = raw.get_value("total_assets")
        equity = raw.get_value("equity")

        derived = _derive_liabilities_from_components(
            long_term,
            short_term,
            total_assets,
            equity,
        )
        if derived is not None:
            logger.debug(
                "Derived liabilities = IV(%s) + V(%s) = %s",
                long_term,
                short_term,
                derived,
            )
            _raw_set(
                raw,
                "liabilities",
                derived,
                "derived_strong",
                False,
                60,
                source=semantics.SOURCE_DERIVED,
                match_semantics=semantics.MATCH_NA,
                inference_mode=semantics.MODE_DERIVED,
            )
        elif (
            total_assets is not None
            and equity is not None
            and not (
                context.signals.is_balance_like
                and not context.tables
                and "equity" in raw
                and raw["equity"].match_type == "text_regex"
                and not raw["equity"].is_exact
            )
        ):
            derived = total_assets - equity
            if total_assets > 0:
                ratio = derived / total_assets
                if ratio >= 0.02:
                    logger.debug("Derived liabilities = assets - equity = %s", derived)
                    _raw_set(
                        raw,
                        "liabilities",
                        derived,
                        "derived_strong",
                        False,
                        60,
                        source=semantics.SOURCE_DERIVED,
                        match_semantics=semantics.MATCH_NA,
                        inference_mode=semantics.MODE_DERIVED,
                    )

    if "short_term_liabilities" not in raw and "liabilities" in raw:
        long_term = raw.get_value("long_term_liabilities")
        liabilities = raw["liabilities"].value
        if long_term is not None:
            derived = liabilities - long_term
            if legacy_helpers._is_valid_financial_value(derived) and derived >= 0:
                logger.debug(
                    "Derived short_term_liabilities = liabilities(%s) - long_term(%s) = %s",
                    liabilities,
                    long_term,
                    derived,
                )
                _raw_set(
                    raw,
                    "short_term_liabilities",
                    derived,
                    "derived",
                    False,
                    30,
                    source=semantics.SOURCE_DERIVED,
                    match_semantics=semantics.MATCH_NA,
                    inference_mode=semantics.MODE_DERIVED,
                )

    if "current_assets" not in raw:
        derived = _derive_current_assets_from_available(raw)
        if legacy_helpers._is_valid_financial_value(derived):
            logger.debug("Derived current_assets from available fields = %s", derived)
            _raw_set(
                raw,
                "current_assets",
                derived,
                "derived",
                False,
                30,
                source=semantics.SOURCE_DERIVED,
                match_semantics=semantics.MATCH_NA,
                inference_mode=semantics.MODE_DERIVED,
            )

    current_assets_value = raw.get_value("current_assets")
    component_values = [
        raw[key].value
        for key in ("inventory", "accounts_receivable", "cash_and_equivalents")
        if key in raw
    ]
    if (
        current_assets_value is not None
        and component_values
        and current_assets_value < max(component_values)
    ):
        logger.warning(
            "Current assets candidate rejected by guardrail: current_assets=%s, max_component=%s",
            current_assets_value,
            max(component_values),
        )
        raw.pop("current_assets", None)
        derived = _derive_current_assets_from_available(raw)
        if legacy_helpers._is_valid_financial_value(derived):
            logger.debug(
                "Derived current_assets after guardrail fallback = %s", derived
            )
            _raw_set(
                raw,
                "current_assets",
                derived,
                "derived",
                False,
                30,
                source=semantics.SOURCE_DERIVED,
                match_semantics=semantics.MATCH_NA,
                inference_mode=semantics.MODE_DERIVED,
            )


def _apply_form_like_guardrails(result: dict[str, ExtractionMetadata]) -> None:
    def _guardrail_soft_null(metric_key: str, reason_code: str) -> None:
        current = semantics.normalize_legacy_metadata(result[metric_key])
        next_signal_flags = list(current.signal_flags)
        if semantics.FLAG_POSTPROCESS_GUARDRAIL_ADJUSTED not in next_signal_flags:
            next_signal_flags.append(semantics.FLAG_POSTPROCESS_GUARDRAIL_ADJUSTED)
        result[metric_key] = ExtractionMetadata(
            value=None,
            confidence=0.0,
            source=current.source,
            evidence_version=current.evidence_version,
            match_semantics=current.match_semantics,
            inference_mode=current.inference_mode,
            postprocess_state=semantics.POSTPROCESS_GUARDRAIL,
            reason_code=reason_code,
            signal_flags=next_signal_flags,
            candidate_quality=current.candidate_quality,
            authoritative_override=current.authoritative_override,
        )

    total_assets = result["total_assets"].value
    current_assets = result["current_assets"].value
    liabilities = result["liabilities"].value
    equity = result["equity"].value
    short_term = result["short_term_liabilities"].value

    if total_assets is not None:
        if current_assets is not None and current_assets > total_assets:
            _guardrail_soft_null(
                "current_assets",
                semantics.REASON_GUARDRAIL_CURRENT_ASSETS_GT_TOTAL_ASSETS,
            )
            current_assets = None

        if liabilities is not None and liabilities > total_assets:
            _guardrail_soft_null(
                "liabilities",
                semantics.REASON_GUARDRAIL_LIABILITIES_GT_TOTAL_ASSETS,
            )
            liabilities = None

        if equity is not None and equity > total_assets:
            _guardrail_soft_null(
                "equity",
                semantics.REASON_GUARDRAIL_EQUITY_GT_TOTAL_ASSETS,
            )
            equity = None

        if short_term is not None and short_term > total_assets:
            _guardrail_soft_null(
                "short_term_liabilities",
                semantics.REASON_GUARDRAIL_SHORT_TERM_GT_TOTAL_ASSETS,
            )
            short_term = None

    for component_key in (
        "cash_and_equivalents",
        "inventory",
        "accounts_receivable",
    ):
        component = result[component_key].value
        if (
            current_assets is not None
            and component is not None
            and component > current_assets
        ):
            _guardrail_soft_null(
                component_key,
                semantics.REASON_GUARDRAIL_COMPONENT_GT_CURRENT_ASSETS,
            )

    if liabilities is not None and short_term is not None and short_term > liabilities:
        _guardrail_soft_null(
            "short_term_liabilities",
            semantics.REASON_GUARDRAIL_SHORT_TERM_GT_LIABILITIES,
        )


def apply_result_guardrails(
    context: ExtractorContext,
    result: dict[str, ExtractionMetadata],
) -> None:
    if context.signals.is_balance_like:
        _apply_form_like_guardrails(result)
