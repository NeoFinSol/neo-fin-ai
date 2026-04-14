from __future__ import annotations

import importlib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
THIS_FILE = Path(__file__).resolve()
DEAD_IMPORT_PATH = "src.models.database"
REMOVED_MODEL_FILES = (
    REPO_ROOT / "src" / "models" / "database" / "user.py",
    REPO_ROOT / "src" / "models" / "database" / "project.py",
)
SCAN_ROOTS = ("src", "tests", "scripts", "migrations")
TOP_LEVEL_TOOLING_FILES = (
    "pytest.ini",
    ".flake8",
    "alembic.ini",
    "docker-compose.yml",
    "docker-compose.prod.yml",
    "Dockerfile.backend",
    "requirements.txt",
)
TEXT_FILE_SUFFIXES = {
    ".py",
    ".pyi",
    ".ini",
    ".toml",
    ".yml",
    ".yaml",
    ".sh",
    ".ps1",
    ".bat",
    ".txt",
}


def _iter_maintained_surface_files() -> list[Path]:
    files: list[Path] = []

    for root_name in SCAN_ROOTS:
        root = REPO_ROOT / root_name
        if not root.exists():
            continue

        for path in root.rglob("*"):
            if not path.is_file():
                continue
            if path == THIS_FILE or "__pycache__" in path.parts:
                continue
            if path.suffix.lower() not in TEXT_FILE_SUFFIXES:
                continue
            files.append(path)

    for relative_path in TOP_LEVEL_TOOLING_FILES:
        path = REPO_ROOT / relative_path
        if path.exists():
            files.append(path)

    return files


def test_canonical_supported_orm_models_import_smoke() -> None:
    models_module = importlib.import_module("src.db.models")

    assert hasattr(models_module, "Analysis")
    assert hasattr(models_module, "MultiAnalysisSession")


def test_orphan_model_files_are_removed() -> None:
    for path in REMOVED_MODEL_FILES:
        assert not path.exists(), f"Expected removed orphan model file: {path}"


def test_no_supported_surface_references_removed_boundary() -> None:
    offenders: list[str] = []

    for path in _iter_maintained_surface_files():
        file_text = path.read_text(encoding="utf-8", errors="ignore")
        if DEAD_IMPORT_PATH in file_text:
            offenders.append(str(path.relative_to(REPO_ROOT)))

    assert (
        offenders == []
    ), "Found supported-surface references to removed boundary: " + ", ".join(offenders)
