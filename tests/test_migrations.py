from __future__ import annotations

import ast
import configparser
from pathlib import Path

MIGRATIONS_DIR = Path(__file__).resolve().parents[1] / "migrations" / "versions"
ALEMBIC_INI = Path(__file__).resolve().parents[1] / "alembic.ini"


def _load_revision_metadata() -> list[tuple[str, str | None, Path]]:
    revisions: list[tuple[str, str | None, Path]] = []
    for path in sorted(MIGRATIONS_DIR.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
        revision: str | None = None
        down_revision: str | None = None
        for node in tree.body:
            if not isinstance(node, ast.Assign) or len(node.targets) != 1:
                continue
            target = node.targets[0]
            if not isinstance(target, ast.Name):
                continue
            if target.id == "revision":
                revision = ast.literal_eval(node.value)
            if target.id == "down_revision":
                down_revision = ast.literal_eval(node.value)
        if revision is not None:
            revisions.append((revision, down_revision, path))
    return revisions


def test_revision_ids_fit_alembic_version_column() -> None:
    for revision, down_revision, path in _load_revision_metadata():
        assert (
            len(revision) <= 32
        ), f"{path.name}: revision '{revision}' is longer than 32 chars"
        if down_revision is not None:
            assert (
                len(down_revision) <= 32
            ), f"{path.name}: down_revision '{down_revision}' is longer than 32 chars"


def test_revision_chain_references_existing_revisions() -> None:
    revisions = _load_revision_metadata()
    known = {revision for revision, _, _ in revisions}
    roots = [
        revision for revision, down_revision, _ in revisions if down_revision is None
    ]
    assert len(roots) == 1, "Expected exactly one root migration"

    for _, down_revision, path in revisions:
        if down_revision is not None:
            assert (
                down_revision in known
            ), f"{path.name}: down_revision '{down_revision}' does not match any known revision"


def test_alembic_ini_uses_nonsecret_placeholder_url() -> None:
    file_text = ALEMBIC_INI.read_text(encoding="utf-8")
    assert "postgres:postgres" not in file_text

    config = configparser.ConfigParser()
    config.read(ALEMBIC_INI, encoding="utf-8")
    assert config["alembic"]["sqlalchemy.url"] == (
        "postgresql+psycopg2://user:pass@localhost/dbname"
    )
