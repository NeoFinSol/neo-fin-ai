from __future__ import annotations

from decimal import Decimal

from src.analysis.math.candidates import (
    CandidateState,
    MetricCandidate,
    build_derived_candidate,
    build_reported_candidate,
    build_synthetic_candidate,
)
from src.analysis.math.contracts import MetricInputRef, MetricUnit, TypedInputs
from src.analysis.math.registry import REGISTRY

APPROXIMATED_EBITDA_REASON_CODES = {"gross_profit_to_ebitda_approximation"}
REPORTED_EBITDA_REASON_CODES = {"reported_ebitda"}
REPORTED_EBITDA_SOURCES = {"reported"}
DEFAULT_REPORTED_PRODUCER = "reported.extractor"
LIABILITIES_KEYS = ("liabilities", "total_liabilities")


def _registry_formula_version(metric_id: str) -> str | None:
    definition = REGISTRY.get(metric_id)
    return None if definition is None else definition.formula_version


def build_precomputed_candidates(inputs: TypedInputs) -> tuple[MetricCandidate, ...]:
    candidates = list(_input_candidates(inputs))
    candidates.extend(_total_debt_candidates(inputs))
    candidates.extend(_ebitda_family_candidates(inputs))
    candidates.extend(_debt_family_candidates(inputs))
    candidates.extend(_average_balance_candidates(inputs))
    return tuple(sorted(candidates, key=lambda candidate: candidate.candidate_id))


def _input_candidates(inputs: TypedInputs) -> tuple[MetricCandidate, ...]:
    return tuple(
        _reported_input_candidate(metric_key, input_ref)
        for metric_key, input_ref in sorted(inputs.items())
    )


def _reported_input_candidate(
    metric_key: str,
    input_ref: MetricInputRef,
) -> MetricCandidate:
    return build_reported_candidate(
        metric_key=metric_key,
        formula_id=None,
        canonical_value=_to_decimal(input_ref.value),
        unit=_metric_unit(metric_key, input_ref),
        producer=input_ref.source or DEFAULT_REPORTED_PRODUCER,
        source_inputs=(metric_key,),
        source_metric_keys=(metric_key,),
        source_refs=_source_refs(input_ref),
        period_ref=None,
        extractor_source_ref=input_ref.source or f"input:{metric_key}",
        candidate_state=_candidate_state(input_ref),
    )


def _total_debt_candidates(inputs: TypedInputs) -> tuple[MetricCandidate, ...]:
    total_debt = _build_total_debt_candidate(inputs)
    if total_debt is None:
        return ()
    family_candidates = tuple(
        _clone_candidate(
            total_debt,
            metric_key=metric_key,
            precedence_group="debt_only",
        )
        for metric_key in (
            "financial_leverage",
            "financial_leverage_debt_only",
        )
    )
    return (total_debt,) + family_candidates


def _build_total_debt_candidate(inputs: TypedInputs) -> MetricCandidate | None:
    short_term = inputs.get("short_term_borrowings")
    long_term = inputs.get("long_term_borrowings")
    if short_term is None and long_term is None:
        return None
    if short_term is None or long_term is None:
        return _missing_synthetic_candidate(
            metric_key="total_debt",
            synthetic_key="total_debt",
            source_metric_keys=("short_term_borrowings", "long_term_borrowings"),
        )
    if short_term.value is None or long_term.value is None:
        return _missing_synthetic_candidate(
            metric_key="total_debt",
            synthetic_key="total_debt",
            source_metric_keys=("short_term_borrowings", "long_term_borrowings"),
        )
    return build_synthetic_candidate(
        metric_key="total_debt",
        formula_id=None,
        synthetic_key="total_debt",
        canonical_value=_to_decimal(short_term.value + long_term.value),
        unit=MetricUnit.CURRENCY,
        producer="precompute.total_debt",
        source_inputs=("short_term_borrowings", "long_term_borrowings"),
        source_metric_keys=("short_term_borrowings", "long_term_borrowings"),
        source_refs=_source_refs(short_term) + _source_refs(long_term),
        period_ref=None,
        precedence_group="debt_only",
        candidate_state=CandidateState.READY,
    )


def _missing_synthetic_candidate(
    *,
    metric_key: str,
    synthetic_key: str,
    source_metric_keys: tuple[str, ...],
) -> MetricCandidate:
    return build_synthetic_candidate(
        metric_key=metric_key,
        formula_id=None,
        synthetic_key=synthetic_key,
        canonical_value=None,
        unit=MetricUnit.CURRENCY,
        producer="precompute.total_debt",
        source_inputs=source_metric_keys,
        source_metric_keys=source_metric_keys,
        source_refs=(),
        period_ref=None,
        precedence_group="debt_only",
        candidate_state=CandidateState.MISSING,
    )


def _ebitda_family_candidates(inputs: TypedInputs) -> tuple[MetricCandidate, ...]:
    generic_ebitda = inputs.get("ebitda")
    if generic_ebitda is None or generic_ebitda.value is None:
        return ()
    if _is_approximated_ebitda(generic_ebitda):
        return (
            build_derived_candidate(
                metric_key="ebitda_margin",
                formula_id="ebitda_margin",
                canonical_value=_to_decimal(generic_ebitda.value),
                unit=MetricUnit.CURRENCY,
                producer="precompute.ebitda_variants",
                source_inputs=("ebitda",),
                source_metric_keys=("ebitda_approximated",),
                source_refs=_source_refs(generic_ebitda),
                period_ref=None,
                derivation_mode="approximation",
                extractor_source_ref=generic_ebitda.source,
                precedence_group="approximated",
                resolver_id="ebitda_variants",
                formula_version=_registry_formula_version("ebitda_margin"),
            ),
        )
    if _is_reported_ebitda(generic_ebitda):
        return (
            build_reported_candidate(
                metric_key="ebitda_margin",
                formula_id="ebitda_margin",
                canonical_value=_to_decimal(generic_ebitda.value),
                unit=MetricUnit.CURRENCY,
                producer="precompute.ebitda_variants",
                source_inputs=("ebitda",),
                source_metric_keys=("ebitda_reported",),
                source_refs=_source_refs(generic_ebitda),
                period_ref=None,
                extractor_source_ref=generic_ebitda.source,
                precedence_group="reported",
                resolver_id="ebitda_variants",
                formula_version=_registry_formula_version("ebitda_margin"),
            ),
        )
    return ()


def _debt_family_candidates(inputs: TypedInputs) -> tuple[MetricCandidate, ...]:
    candidates = []
    candidates.extend(_liability_family_candidates(inputs, "financial_leverage"))
    candidates.extend(_liability_family_candidates(inputs, "financial_leverage_total"))
    return tuple(candidates)


def _liability_family_candidates(
    inputs: TypedInputs,
    metric_key: str,
) -> tuple[MetricCandidate, ...]:
    candidates = []
    liabilities_ref = _first_input(inputs, LIABILITIES_KEYS)
    if liabilities_ref is not None:
        candidates.append(
            build_reported_candidate(
                metric_key=metric_key,
                formula_id=metric_key,
                canonical_value=_to_decimal(liabilities_ref.value),
                unit=MetricUnit.CURRENCY,
                producer=liabilities_ref.source or DEFAULT_REPORTED_PRODUCER,
                source_inputs=("total_liabilities",),
                source_metric_keys=("total_liabilities",),
                source_refs=_source_refs(liabilities_ref),
                period_ref=None,
                extractor_source_ref=liabilities_ref.source
                or "family:liabilities_total",
                precedence_group="liabilities_total",
                formula_version=_registry_formula_version(metric_key),
            )
        )
    lease_ref = inputs.get("lease_liabilities")
    if lease_ref is None:
        return tuple(candidates)
    candidates.append(
        build_reported_candidate(
            metric_key=metric_key,
            formula_id=metric_key,
            canonical_value=_to_decimal(lease_ref.value),
            unit=MetricUnit.CURRENCY,
            producer=lease_ref.source or DEFAULT_REPORTED_PRODUCER,
            source_inputs=("lease_liabilities",),
            source_metric_keys=("lease_liabilities",),
            source_refs=_source_refs(lease_ref),
            period_ref=None,
            extractor_source_ref=lease_ref.source or "family:lease_liabilities",
            precedence_group="lease_liabilities",
            candidate_state=_candidate_state(lease_ref),
            formula_version=_registry_formula_version(metric_key),
        )
    )
    return tuple(candidates)


def _average_balance_candidates(inputs: TypedInputs) -> tuple[MetricCandidate, ...]:
    candidates = []
    candidates.extend(_average_family_candidates(inputs, "total_assets"))
    candidates.extend(_average_family_candidates(inputs, "equity"))
    return tuple(candidates)


def _average_family_candidates(
    inputs: TypedInputs,
    base_key: str,
) -> tuple[MetricCandidate, ...]:
    family_key = f"average_{base_key}"
    opening_ref = inputs.get(f"opening_{base_key}")
    closing_ref = inputs.get(f"closing_{base_key}")
    direct_average = inputs.get(family_key)
    candidates = []
    if opening_ref is not None:
        candidates.append(
            _average_basis_candidate(
                family_key=family_key,
                basis_key=f"opening_{base_key}",
                input_ref=opening_ref,
                precedence_group="opening_balance",
            )
        )
    if closing_ref is not None:
        candidates.append(
            _average_basis_candidate(
                family_key=family_key,
                basis_key=f"closing_{base_key}",
                input_ref=closing_ref,
                precedence_group="closing_balance",
            )
        )
    if direct_average is not None:
        candidates.append(
            _average_basis_candidate(
                family_key=family_key,
                basis_key=family_key,
                input_ref=direct_average,
                precedence_group="direct_average",
            )
        )
    if opening_ref is None or closing_ref is None:
        return tuple(candidates)
    if opening_ref.value is None or closing_ref.value is None:
        return tuple(candidates)
    candidates.append(
        build_synthetic_candidate(
            metric_key=family_key,
            formula_id=None,
            synthetic_key=family_key,
            canonical_value=_to_decimal((opening_ref.value + closing_ref.value) / 2),
            unit=MetricUnit.CURRENCY,
            producer="comparative.average_balance",
            source_inputs=(f"opening_{base_key}", f"closing_{base_key}"),
            source_metric_keys=(base_key,),
            source_refs=_source_refs(opening_ref) + _source_refs(closing_ref),
            period_ref=None,
            precedence_group="average_balance",
            candidate_state=CandidateState.READY,
        )
    )
    return tuple(candidates)


def _average_basis_candidate(
    *,
    family_key: str,
    basis_key: str,
    input_ref: MetricInputRef,
    precedence_group: str,
) -> MetricCandidate:
    return build_reported_candidate(
        metric_key=family_key,
        formula_id=None,
        canonical_value=_to_decimal(input_ref.value),
        unit=MetricUnit.CURRENCY,
        producer=input_ref.source or DEFAULT_REPORTED_PRODUCER,
        source_inputs=(basis_key,),
        source_metric_keys=(family_key,),
        source_refs=_source_refs(input_ref),
        period_ref=None,
        extractor_source_ref=input_ref.source or f"basis:{basis_key}",
        precedence_group=precedence_group,
        candidate_state=_candidate_state(input_ref),
    )


def _clone_candidate(
    candidate: MetricCandidate,
    *,
    metric_key: str,
    precedence_group: str,
) -> MetricCandidate:
    return build_synthetic_candidate(
        metric_key=metric_key,
        formula_id=metric_key,
        synthetic_key=candidate.synthetic_key or "total_debt",
        canonical_value=candidate.canonical_value,
        unit=candidate.unit,
        producer=candidate.provenance.producer,
        source_inputs=candidate.provenance.source_inputs,
        source_metric_keys=candidate.provenance.source_metric_keys,
        source_refs=candidate.trace_seed.source_refs,
        period_ref=candidate.trace_seed.period_ref,
        derivation_mode=candidate.provenance.derivation_mode,
        extractor_source_ref=candidate.provenance.extractor_source_ref,
        resolver_id=candidate.provenance.resolver_id,
        precedence_group=precedence_group,
        candidate_state=candidate.candidate_state,
        formula_version=_registry_formula_version(metric_key),
    )


def _first_input(
    inputs: TypedInputs,
    keys: tuple[str, ...],
) -> MetricInputRef | None:
    for key in keys:
        candidate = inputs.get(key)
        if candidate is not None:
            return candidate
    return None


def _candidate_state(input_ref: MetricInputRef) -> CandidateState:
    if input_ref.value is None:
        return CandidateState.MISSING
    if input_ref.reason_codes:
        return CandidateState.INVALID
    return CandidateState.READY


def _metric_unit(metric_key: str, input_ref: MetricInputRef) -> MetricUnit:
    if input_ref.unit is not None:
        try:
            return MetricUnit(input_ref.unit)
        except ValueError:
            return MetricUnit.CURRENCY
    if metric_key.endswith("_ratio") or metric_key in {"ros", "roa", "roe"}:
        return MetricUnit.RATIO
    if "turnover" in metric_key:
        return MetricUnit.TURNS
    return MetricUnit.CURRENCY


def _source_refs(input_ref: MetricInputRef) -> tuple[str, ...]:
    if input_ref.source is None:
        return ()
    return (input_ref.source,)


def _to_decimal(value: float | None) -> Decimal | None:
    if value is None:
        return None
    return Decimal(str(value))


def _is_approximated_ebitda(candidate: MetricInputRef) -> bool:
    return any(
        reason_code in APPROXIMATED_EBITDA_REASON_CODES
        for reason_code in candidate.reason_codes
    )


def _is_reported_ebitda(candidate: MetricInputRef) -> bool:
    if candidate.source in REPORTED_EBITDA_SOURCES:
        return True
    return any(
        reason_code in REPORTED_EBITDA_REASON_CODES
        for reason_code in candidate.reason_codes
    )
