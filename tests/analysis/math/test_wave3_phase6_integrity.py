"""Wave 3 Phase 6 — startup validation and integrity suite (CI-friendly)."""

from __future__ import annotations

from types import MappingProxyType

import pytest

from src.analysis.math.contracts import MetricComputationResult
from src.analysis.math.policies import (
    AveragingPolicy,
    DenominatorPolicy,
    SuppressionPolicy,
)
from src.analysis.math.registry import REGISTRY, MetricCoverageClass, MetricDefinition
from src.analysis.math.startup_validation import (
    Wave3ContractValidationError,
    audit_wave3_reason_literals_source,
    compute_registry_semantic_fingerprint,
    validate_wave3_contract,
)


def _base_definition(**overrides) -> MetricDefinition:
    params = {
        "metric_id": "m_test",
        "formula_id": "m_test",
        "formula_version": "v1",
        "required_inputs": ("a",),
        "averaging_policy": AveragingPolicy.NONE,
        "suppression_policy": SuppressionPolicy.NEVER,
        "coverage_class": MetricCoverageClass.FULLY_SUPPORTED,
        "denominator_key": "a",
        "denominator_policy": DenominatorPolicy.STRICT_POSITIVE,
    }
    params.update(overrides)

    def _stub_compute(_: object) -> MetricComputationResult:
        return MetricComputationResult(value=None, trace={})

    params.setdefault("compute", _stub_compute)
    return MetricDefinition(**params)


@pytest.mark.wave3_integrity
def test_validate_live_registry_passes():
    validate_wave3_contract(REGISTRY)


@pytest.mark.wave3_integrity
def test_registry_integrity_duplicate_metric_id_fails():
    dup = _base_definition(metric_id="shared_mid")
    bad = MappingProxyType({"a": dup, "b": dup})
    with pytest.raises(Wave3ContractValidationError, match="duplicate metric_id"):
        validate_wave3_contract(bad)


@pytest.mark.wave3_integrity
def test_registry_integrity_key_mismatch_fails():
    bad = {"wrong_key": _base_definition(metric_id="m_test")}
    with pytest.raises(Wave3ContractValidationError, match="registry integrity"):
        validate_wave3_contract(MappingProxyType(bad))


@pytest.mark.wave3_integrity
def test_registry_integrity_missing_formula_id_fails():
    bad = MappingProxyType(
        {"m_test": _base_definition(metric_id="m_test", formula_id="  ")}
    )
    with pytest.raises(Wave3ContractValidationError, match="formula_id"):
        validate_wave3_contract(bad)


@pytest.mark.wave3_integrity
def test_registry_integrity_missing_formula_version_fails():
    bad = MappingProxyType(
        {"m_test": _base_definition(metric_id="m_test", formula_version="  ")}
    )
    with pytest.raises(Wave3ContractValidationError, match="formula_version"):
        validate_wave3_contract(bad)


@pytest.mark.wave3_integrity
def test_synthetic_integrity_undeclared_dep_fails():
    bad = MappingProxyType(
        {
            "m_test": _base_definition(
                metric_id="m_test",
                synthetic_dependencies=frozenset({"undeclared_synthetic_xyz"}),
            )
        }
    )
    with pytest.raises(Wave3ContractValidationError, match="undeclared synthetic"):
        validate_wave3_contract(bad)


@pytest.mark.wave3_integrity
def test_coverage_completeness_invalid_coverage_class_fails():
    bad = MappingProxyType(
        {"m_test": _base_definition(metric_id="m_test", coverage_class="not_an_enum")}
    )
    with pytest.raises(Wave3ContractValidationError, match="coverage_class"):
        validate_wave3_contract(bad)


@pytest.mark.wave3_integrity
def test_resolver_integrity_unknown_slot_fails():
    bad = MappingProxyType(
        {
            "m_test": _base_definition(
                metric_id="m_test",
                resolver_slot="nonexistent_resolver_slot_xyz",
                precedence_policy_ref="reported_over_derived",
            )
        }
    )
    with pytest.raises(Wave3ContractValidationError, match="unknown resolver_slot"):
        validate_wave3_contract(bad)


@pytest.mark.wave3_integrity
def test_resolver_integrity_missing_precedence_fails():
    bad = MappingProxyType(
        {"m_test": _base_definition(metric_id="m_test", resolver_slot="debt_basis")}
    )
    with pytest.raises(Wave3ContractValidationError, match="resolver_slot requires"):
        validate_wave3_contract(bad)


@pytest.mark.wave3_integrity
def test_resolver_integrity_precedence_without_resolver_fails():
    bad = MappingProxyType(
        {
            "m_test": _base_definition(
                metric_id="m_test",
                precedence_policy_ref="reported_over_derived",
            )
        }
    )
    with pytest.raises(
        Wave3ContractValidationError, match="precedence_policy_ref requires"
    ):
        validate_wave3_contract(bad)


@pytest.mark.wave3_integrity
def test_resolver_integrity_unknown_precedence_ref_fails():
    bad = MappingProxyType(
        {
            "m_test": _base_definition(
                metric_id="m_test",
                resolver_slot="debt_basis",
                precedence_policy_ref="unknown_policy_ref_xyz",
            )
        }
    )
    with pytest.raises(Wave3ContractValidationError, match="precedence_policy_ref"):
        validate_wave3_contract(bad)


@pytest.mark.wave3_integrity
def test_average_balance_missing_policy_ref_fails():
    bad = MappingProxyType(
        {
            "m_test": _base_definition(
                metric_id="m_test",
                averaging_policy=AveragingPolicy.AVERAGE_BALANCE,
                average_balance_policy_ref=None,
            )
        }
    )
    with pytest.raises(
        Wave3ContractValidationError, match="average_balance_policy_ref"
    ):
        validate_wave3_contract(bad)


@pytest.mark.wave3_integrity
def test_average_balance_policy_without_averaging_policy_fails():
    bad = MappingProxyType(
        {
            "m_test": _base_definition(
                metric_id="m_test",
                average_balance_policy_ref="opening_and_closing_required",
            )
        }
    )
    with pytest.raises(Wave3ContractValidationError, match="averaging_policy"):
        validate_wave3_contract(bad)


@pytest.mark.wave3_integrity
def test_reason_token_integrity_passes_on_current_tree():
    """AST scan: no legacy ``wave3_*`` string literals in scanned math modules."""
    validate_wave3_contract(REGISTRY)


@pytest.mark.wave3_integrity
def test_reason_token_integrity_detects_inline_literal():
    bad_source = 'REASON = "wave3_undeclared_inline_token_xyz"\n'
    hits = audit_wave3_reason_literals_source(bad_source, filename="bad_module.py")
    assert hits and "wave3_undeclared_inline_token_xyz" in hits[0]


@pytest.mark.wave3_integrity
def test_semantic_fingerprint_stable_for_live_registry():
    first = compute_registry_semantic_fingerprint(REGISTRY)
    second = compute_registry_semantic_fingerprint(REGISTRY)
    assert first == second


@pytest.mark.wave3_integrity
def test_semantic_fingerprint_detects_change():
    reg_dict = dict(REGISTRY)
    roa = reg_dict["roa"]
    reg_dict["roa"] = MetricDefinition(
        metric_id=roa.metric_id,
        formula_id=roa.formula_id,
        formula_version="v999-changed",
        required_inputs=roa.required_inputs,
        averaging_policy=roa.averaging_policy,
        suppression_policy=roa.suppression_policy,
        compute=roa.compute,
        coverage_class=roa.coverage_class,
        denominator_key=roa.denominator_key,
        denominator_policy=roa.denominator_policy,
        resolver_slot=roa.resolver_slot,
        precedence_policy_ref=roa.precedence_policy_ref,
        average_balance_policy_ref=roa.average_balance_policy_ref,
        synthetic_dependencies=roa.synthetic_dependencies,
        legacy_label=roa.legacy_label,
        frontend_key=roa.frontend_key,
        non_negative_inputs=roa.non_negative_inputs,
    )
    mutated = MappingProxyType(reg_dict)
    assert compute_registry_semantic_fingerprint(
        mutated
    ) != compute_registry_semantic_fingerprint(REGISTRY)
