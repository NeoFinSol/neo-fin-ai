from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING, Mapping, cast

from src.analysis.math.resolvers import (
    DEBT_BASIS_RESOLVER,
    EBITDA_RESOLVER,
    REPORTED_VS_DERIVED_RESOLVER,
)

if TYPE_CHECKING:
    from src.analysis.math.resolver_engine import ResolverHandler


class ResolverRegistryLookupError(LookupError):
    """Raised when a resolver slot cannot be resolved from the registry."""


RESOLVER_REGISTRY: Mapping[str, "ResolverHandler"] = MappingProxyType(
    {
        "debt_basis": DEBT_BASIS_RESOLVER,
        "ebitda_variants": EBITDA_RESOLVER,
        "reported_vs_derived": REPORTED_VS_DERIVED_RESOLVER,
    }
)


def get_registered_resolver_slots() -> tuple[str, ...]:
    return tuple(sorted(RESOLVER_REGISTRY))


def has_resolver_handler(slot: str) -> bool:
    return slot in RESOLVER_REGISTRY


def get_resolver_handler(slot: str) -> "ResolverHandler":
    handler = RESOLVER_REGISTRY.get(slot)
    if handler is None:
        raise ResolverRegistryLookupError(f"unknown resolver slot: {slot}")
    return cast("ResolverHandler", handler)
