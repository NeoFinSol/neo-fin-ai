"""
Wave 3 Phase 6 — startup contract validation for Math Layer.

Fatal on failure: import-time / app lifespan callers must not swallow errors.
"""

from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from src.analysis.math.eligibility import OPENING_AND_CLOSING_REQUIRED_POLICY_REF
from src.analysis.math.policies import AveragingPolicy
from src.analysis.math.precedence import PRECEDENCE_POLICIES
from src.analysis.math.registry import (
    STRICT_AVERAGE_BALANCE_METRICS,
    MetricCoverageClass,
    MetricDefinition,
)
from src.analysis.math.resolver_engine import collect_resolver_framework_errors
from src.analysis.math.resolver_registry import RESOLVER_REGISTRY
from src.analysis.math.synthetic_contract import is_declared_synthetic_key

_MATH_PKG = Path(__file__).resolve().parent

_EXPECTED_REGISTRY_SEMANTIC_HASH = (
    "182a2ab041d9a30d9b6d3d465b395cf3d73bcf7404c77a33fa74d1ab9a1f54d9"
)

_WAVE3_REASON_LITERAL_SCAN_FILES = (
    "coverage.py",
    "compute_basis.py",
    "eligibility.py",
    "engine.py",
    "precompute.py",
    "refusals.py",
    "resolver_engine.py",
    "precedence.py",
    "trace_builders.py",
    "resolvers/common.py",
    "resolvers/debt_basis_resolver.py",
    "resolvers/ebitda_resolver.py",
    "resolvers/reported_vs_derived_resolver.py",
)


class Wave3ContractValidationError(RuntimeError):
    """Raised when Wave 3 startup contract validation fails."""


def validate_wave3_contract(metric_registry: Mapping[str, MetricDefinition]) -> None:
    """Validate Wave 3 registry and related contracts; raise on any failure."""
    _validate_registry_integrity(metric_registry)
    _validate_synthetic_integrity(metric_registry)
    _validate_coverage_completeness(metric_registry)
    _validate_resolver_integrity(metric_registry)
    _validate_average_balance_eligibility(metric_registry)
    _validate_strict_average_balance_metric_declarations(metric_registry)
    _validate_reason_token_integrity()
    _validate_wave4_reason_code_registry()
    _validate_registry_semantic_fingerprint(metric_registry)


def _validate_wave4_reason_code_registry() -> None:
    from src.analysis.math.reason_codes import validate_reason_code_registry

    validate_reason_code_registry()


def compute_registry_semantic_fingerprint(
    metric_registry: Mapping[str, MetricDefinition],
) -> str:
    """Deterministic SHA256 over semantic registry fields (excludes callables)."""
    rows = [
        _metric_semantic_row(key, metric_registry[key])
        for key in sorted(metric_registry)
    ]
    payload = json.dumps(rows, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _metric_semantic_row(
    registry_key: str, definition: MetricDefinition
) -> dict[str, Any]:
    return {
        "registry_key": registry_key,
        "metric_id": definition.metric_id,
        "formula_id": definition.formula_id,
        "formula_version": definition.formula_version,
        "required_inputs": list(definition.required_inputs),
        "coverage_class": definition.coverage_class.value,
        "resolver_slot": definition.resolver_slot or "",
        "precedence_policy_ref": definition.precedence_policy_ref or "",
        "synthetic_dependencies": sorted(definition.synthetic_dependencies),
        "average_balance_policy_ref": definition.average_balance_policy_ref or "",
        "denominator_key": definition.denominator_key or "",
        "denominator_policy": (
            definition.denominator_policy.value if definition.denominator_policy else ""
        ),
        "averaging_policy": definition.averaging_policy.value,
        "suppression_policy": definition.suppression_policy.value,
        "resolver_required_input_prefix": definition.resolver_required_input_prefix
        or "",
        "resolver_bridge_input_key": definition.resolver_bridge_input_key or "",
    }


def _validate_registry_semantic_fingerprint(
    metric_registry: Mapping[str, MetricDefinition],
) -> None:
    from src.analysis.math.registry import REGISTRY_VERSION

    actual = compute_registry_semantic_fingerprint(metric_registry)
    if actual != _EXPECTED_REGISTRY_SEMANTIC_HASH:
        msg = (
            "registry semantic fingerprint mismatch: "
            f"got {actual}, expected {_EXPECTED_REGISTRY_SEMANTIC_HASH}. "
            "After intentional registry changes, update "
            "EXPECTED_REGISTRY_SEMANTIC_HASH in startup_validation.py and "
            f"REGISTRY_VERSION (currently {REGISTRY_VERSION!r}) in registry.py."
        )
        raise Wave3ContractValidationError(msg)


def _validate_registry_integrity(
    metric_registry: Mapping[str, MetricDefinition]
) -> None:
    _assert_unique_metric_ids(metric_registry)
    _assert_registry_keys_match_metric_ids(metric_registry)
    _assert_formula_versions(metric_registry)
    _assert_formula_ids(metric_registry)


def _assert_registry_keys_match_metric_ids(
    metric_registry: Mapping[str, MetricDefinition],
) -> None:
    for registry_key, definition in metric_registry.items():
        if registry_key != definition.metric_id:
            raise Wave3ContractValidationError(
                f"registry integrity: key {registry_key!r} != metric_id "
                f"{definition.metric_id!r}"
            )


def _assert_unique_metric_ids(metric_registry: Mapping[str, MetricDefinition]) -> None:
    metric_ids = [definition.metric_id for definition in metric_registry.values()]
    if len(metric_ids) != len(set(metric_ids)):
        raise Wave3ContractValidationError(
            "registry integrity: duplicate metric_id among registry definitions"
        )


def _assert_formula_versions(metric_registry: Mapping[str, MetricDefinition]) -> None:
    for registry_key, definition in metric_registry.items():
        version = (definition.formula_version or "").strip()
        if not version:
            raise Wave3ContractValidationError(
                f"registry integrity: missing formula_version for metric {registry_key!r}"
            )


def _assert_formula_ids(metric_registry: Mapping[str, MetricDefinition]) -> None:
    for registry_key, definition in metric_registry.items():
        formula_id = (definition.formula_id or "").strip()
        if not formula_id:
            raise Wave3ContractValidationError(
                f"registry integrity: missing formula_id for metric {registry_key!r}"
            )


def _validate_synthetic_integrity(
    metric_registry: Mapping[str, MetricDefinition]
) -> None:
    for registry_key, definition in metric_registry.items():
        for dep in sorted(definition.synthetic_dependencies):
            if not is_declared_synthetic_key(dep):
                raise Wave3ContractValidationError(
                    f"synthetic integrity: metric {registry_key!r} declares "
                    f"undeclared synthetic dependency {dep!r}"
                )


def _validate_coverage_completeness(
    metric_registry: Mapping[str, MetricDefinition]
) -> None:
    for registry_key, definition in metric_registry.items():
        coverage = definition.coverage_class
        if not isinstance(coverage, MetricCoverageClass):
            raise Wave3ContractValidationError(
                f"coverage completeness: metric {registry_key!r} has invalid "
                f"coverage_class {coverage!r}"
            )


def _validate_resolver_integrity(
    metric_registry: Mapping[str, MetricDefinition]
) -> None:
    for registry_key, definition in metric_registry.items():
        slot = definition.resolver_slot
        if slot is not None and slot not in RESOLVER_REGISTRY:
            raise Wave3ContractValidationError(
                f"resolver integrity: metric {registry_key!r} references "
                f"unknown resolver_slot {slot!r}"
            )
        for message in collect_resolver_framework_errors(definition):
            raise Wave3ContractValidationError(
                f"resolver integrity: metric {registry_key!r}: {message}"
            )
        pref = definition.precedence_policy_ref
        if pref is not None and pref not in PRECEDENCE_POLICIES:
            raise Wave3ContractValidationError(
                f"resolver integrity: metric {registry_key!r} references "
                f"unknown precedence_policy_ref {pref!r}"
            )


def _validate_average_balance_eligibility(
    metric_registry: Mapping[str, MetricDefinition],
) -> None:
    for registry_key, definition in metric_registry.items():
        if definition.averaging_policy is AveragingPolicy.AVERAGE_BALANCE:
            _require_average_balance_policy(registry_key, definition)
        if definition.average_balance_policy_ref is not None:
            _require_average_balance_pairing(registry_key, definition)


def _require_average_balance_policy(
    registry_key: str, definition: MetricDefinition
) -> None:
    ref = definition.average_balance_policy_ref
    if ref is None:
        raise Wave3ContractValidationError(
            f"average-balance integrity: metric {registry_key!r} uses "
            f"AVERAGING_POLICY=AVERAGE_BALANCE but average_balance_policy_ref is missing"
        )
    if ref != OPENING_AND_CLOSING_REQUIRED_POLICY_REF:
        raise Wave3ContractValidationError(
            f"average-balance integrity: metric {registry_key!r} has unsupported "
            f"average_balance_policy_ref {ref!r}"
        )


def _require_average_balance_pairing(
    registry_key: str,
    definition: MetricDefinition,
) -> None:
    if definition.averaging_policy is not AveragingPolicy.AVERAGE_BALANCE:
        raise Wave3ContractValidationError(
            f"average-balance integrity: metric {registry_key!r} declares "
            f"average_balance_policy_ref but averaging_policy is not AVERAGE_BALANCE"
        )


def _validate_strict_average_balance_metric_declarations(
    metric_registry: Mapping[str, MetricDefinition],
) -> None:
    """Ensure STRICT_AVERAGE_BALANCE_METRICS stay wired to opening/closing eligibility."""
    for metric_id in sorted(STRICT_AVERAGE_BALANCE_METRICS):
        definition = metric_registry.get(metric_id)
        if definition is None:
            raise Wave3ContractValidationError(
                f"strict average-balance set references missing registry metric {metric_id!r}"
            )
        if definition.averaging_policy is not AveragingPolicy.AVERAGE_BALANCE:
            raise Wave3ContractValidationError(
                f"strict average-balance: metric {metric_id!r} must use "
                f"AVERAGING_POLICY.AVERAGE_BALANCE (got {definition.averaging_policy!r})"
            )
        if (
            definition.average_balance_policy_ref
            != OPENING_AND_CLOSING_REQUIRED_POLICY_REF
        ):
            raise Wave3ContractValidationError(
                f"strict average-balance: metric {metric_id!r} must declare "
                f"average_balance_policy_ref={OPENING_AND_CLOSING_REQUIRED_POLICY_REF!r}"
            )


def _validate_reason_token_integrity() -> None:
    violations = _collect_wave3_reason_literal_violations()
    if violations:
        joined = "; ".join(violations)
        raise Wave3ContractValidationError(
            f"reason-token integrity: legacy wave3_* string literals are not allowed "
            f"in scanned math modules (use reason_codes constants): {joined}"
        )


def _collect_wave3_reason_literal_violations() -> tuple[str, ...]:
    violations: list[str] = []
    for relative in _WAVE3_REASON_LITERAL_SCAN_FILES:
        path = _MATH_PKG / relative
        violations.extend(_scan_file_for_wave3_literals(path))
    return tuple(violations)


def _scan_file_for_wave3_literals(path: Path) -> list[str]:
    if not path.is_file():
        raise Wave3ContractValidationError(
            f"reason-token integrity: missing file {path}"
        )
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    return _wave3_literal_violations_in_tree(tree, path)


def _wave3_literal_violations_in_tree(tree: ast.AST, path: Path) -> list[str]:
    violations: list[str] = []
    for node in ast.walk(tree):
        value = _string_constant_value(node)
        if value is None:
            continue
        if not value.startswith("wave3_"):
            continue
        violations.append(f"{path.name}:{getattr(node, 'lineno', 0)}:{value!r}")
    return violations


def _string_constant_value(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def audit_wave3_reason_literals_source(
    source: str, *, filename: str = "<string>"
) -> tuple[str, ...]:
    """Test helper: return ``wave3_*`` string literals found in source (always violations).

    Canonical outward tokens live in ``reason_codes``; legacy ``wave3_*`` literals are
    forbidden in the AST-scanned math files regardless of membership in any allowlist.
    """
    tree = ast.parse(source, filename=filename)
    return tuple(_wave3_literal_violations_in_tree(tree, Path(filename)))
