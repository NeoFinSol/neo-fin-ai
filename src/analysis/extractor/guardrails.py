from __future__ import annotations

from .legacy_helpers import (
    _apply_form_like_guardrails as _legacy_apply_form_like_guardrails,
)
from .legacy_helpers import (
    _apply_form_like_pnl_sanity as _legacy_apply_form_like_pnl_sanity,
)
from .legacy_helpers import (
    _derive_current_assets_from_available as _legacy_derive_current_assets_from_available,
)
from .legacy_helpers import (
    _derive_liabilities_from_components as _legacy_derive_liabilities_from_components,
)
from .legacy_helpers import (
    _metric_candidate_quality as _legacy_metric_candidate_quality,
)
from .types import ExtractionMetadata


def _metric_candidate_quality(metric_key: str, candidate_text: str) -> int | None:
    return _legacy_metric_candidate_quality(metric_key, candidate_text)


def _derive_current_assets_from_available(
    raw: dict[str, tuple[float, str, bool, int]],
) -> float | None:
    return _legacy_derive_current_assets_from_available(raw)


def _apply_form_like_pnl_sanity(
    raw: dict[str, tuple[float, str, bool, int]],
    code_candidates: dict[str, float],
    *,
    is_standalone_form: bool = False,
) -> None:
    _legacy_apply_form_like_pnl_sanity(
        raw,
        code_candidates,
        is_standalone_form=is_standalone_form,
    )


def _derive_liabilities_from_components(
    long_term: float | None,
    short_term: float | None,
    total_assets: float | None,
    equity: float | None,
) -> float | None:
    return _legacy_derive_liabilities_from_components(
        long_term,
        short_term,
        total_assets,
        equity,
    )


def _apply_form_like_guardrails(result: dict[str, ExtractionMetadata]) -> None:
    _legacy_apply_form_like_guardrails(result)
