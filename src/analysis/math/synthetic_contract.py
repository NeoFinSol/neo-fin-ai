from __future__ import annotations

from typing import TypeAlias

SyntheticMetricKey: TypeAlias = str

DECLARED_SYNTHETIC_KEYS: frozenset[str] = frozenset(
    {
        "total_debt",
        "ebitda_reported",
        "ebitda_approximated",
        "average_total_assets",
        "average_equity",
    }
)

ALLOWED_SYNTHETIC_PRODUCERS: frozenset[str] = frozenset(
    {
        "precompute.total_debt",
        "precompute.ebitda_variants",
        "comparative.average_balance",
        "resolver.ebitda",
        "resolver.debt_basis",
        "resolver.reported_vs_derived",
    }
)


def is_declared_synthetic_key(key: str) -> bool:
    normalized_key = key.strip()
    if not normalized_key:
        return False
    return normalized_key in DECLARED_SYNTHETIC_KEYS


def validate_synthetic_key(key: str) -> None:
    if is_declared_synthetic_key(key):
        return
    raise ValueError(f"undeclared synthetic key: {key!r}")


def validate_synthetic_producer(producer: str) -> None:
    if producer in ALLOWED_SYNTHETIC_PRODUCERS:
        return
    raise ValueError(f"forbidden synthetic producer: {producer!r}")
