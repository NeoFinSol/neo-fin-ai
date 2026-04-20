from __future__ import annotations

from pathlib import Path

from tests.scoring_freeze.helpers.doc_renderers import (
    render_classification_md,
    render_inventory_md,
    render_payload_matrix_md,
    render_wave_handoff_md,
)

_ROOT = Path(__file__).resolve().parents[2]


def test_inventory_doc_is_renderer_synced() -> None:
    expected = render_inventory_md().strip()
    committed = (
        (_ROOT / "docs" / "scoring_freeze_inventory.md")
        .read_text(encoding="utf-8")
        .strip()
    )
    assert committed == expected


def test_classification_doc_is_renderer_synced() -> None:
    expected = render_classification_md().strip()
    committed = (
        (_ROOT / "docs" / "scoring_freeze_classification.md")
        .read_text(encoding="utf-8")
        .strip()
    )
    assert committed == expected


def test_payload_matrix_doc_is_renderer_synced() -> None:
    expected = render_payload_matrix_md().strip()
    committed = (
        (_ROOT / "docs" / "scoring_freeze_payload_matrix.md")
        .read_text(encoding="utf-8")
        .strip()
    )
    assert committed == expected


def test_wave_handoff_doc_is_renderer_synced() -> None:
    expected = render_wave_handoff_md().strip()
    committed = (
        (_ROOT / "docs" / "WAVE_4_5_SCORING_FREEZE.md")
        .read_text(encoding="utf-8")
        .strip()
    )
    assert committed == expected
