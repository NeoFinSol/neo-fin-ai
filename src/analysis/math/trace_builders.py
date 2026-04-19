from __future__ import annotations

from src.analysis.math.candidates import MetricCandidate
from src.analysis.math.coverage import CoverageGateResult
from src.analysis.math.eligibility import EligibilityResult
from src.analysis.math.refusals import MetricRefusal
from src.analysis.math.registry import MetricDefinition


def build_candidate_trace(candidate: MetricCandidate) -> dict[str, object]:
    return {
        "candidate_id": candidate.candidate_id,
        "metric_key": candidate.metric_key,
        "source_kind": candidate.source_kind.value,
        "candidate_state": candidate.candidate_state.value,
        "synthetic_key": candidate.synthetic_key,
        "precedence_group": candidate.precedence_group,
        "producer": candidate.provenance.producer,
        "source_inputs": candidate.provenance.source_inputs,
        "source_metric_keys": candidate.provenance.source_metric_keys,
        "source_period_ref": candidate.provenance.source_period_ref,
        "extractor_source_ref": candidate.provenance.extractor_source_ref,
        "resolver_id": candidate.provenance.resolver_id,
        "trace_seed": {
            "metric_key": candidate.trace_seed.metric_key,
            "formula_id": candidate.trace_seed.formula_id,
            "formula_version": candidate.trace_seed.formula_version,
            "source_refs": candidate.trace_seed.source_refs,
            "period_ref": candidate.trace_seed.period_ref,
        },
    }


def build_eligibility_trace(result: EligibilityResult) -> dict[str, object]:
    return {
        "status": result.status.value,
        "policy_ref": result.policy_ref,
        "basis_candidate_ids": tuple(
            candidate.candidate_id for candidate in result.basis_candidates
        ),
        "refusal_reason_codes": (
            () if result.refusal is None else result.refusal.reason_codes
        ),
    }


def build_resolver_trace(
    *,
    metric_key: str,
    resolver_slot: str,
    precedence_policy_ref: str | None,
    selected_candidate_id: str | None,
    loser_candidate_ids: tuple[str, ...],
    status: str,
    reason_codes: tuple[str, ...],
) -> dict[str, object]:
    return {
        "metric_key": metric_key,
        "resolver_slot": resolver_slot,
        "precedence_policy_ref": precedence_policy_ref,
        "selected_candidate_id": selected_candidate_id,
        "loser_candidate_ids": loser_candidate_ids,
        "status": status,
        "reason_codes": reason_codes,
    }


def build_coverage_trace(
    metric_definition: MetricDefinition,
    result: CoverageGateResult,
) -> dict[str, object]:
    return {
        "metric_key": metric_definition.metric_id,
        "coverage_class": metric_definition.coverage_class.value,
        "compute_mode": result.compute_mode.value,
        "emit_mode": result.emit_mode.value,
        "final_validity_state": (
            None
            if result.final_validity_state is None
            else result.final_validity_state.value
        ),
        "approximation_required": result.approximation_required,
        "refusal_reason_codes": (
            () if result.refusal is None else result.refusal.reason_codes
        ),
    }


def build_refusal_trace(refusal: MetricRefusal) -> dict[str, object]:
    return {
        "stage": refusal.stage.value,
        "reason_codes": refusal.reason_codes,
        "details": dict(refusal.details),
    }
