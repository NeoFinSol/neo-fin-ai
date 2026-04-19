"""Wave 4 — governance: outward reason usage patterns in critical math modules.

Does **not** require diagnostic tokens or lineage strings to be registry members.
Flags only **inline string literals** that duplicate canonical outward codes where
constants should be used (``reason_codes`` / ``reason_code`` keyword and trace dicts).
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from src.analysis.math import reason_codes as rc

_REPO_ROOT = Path(__file__).resolve().parents[1]
_CRITICAL_MATH_SOURCES: tuple[Path, ...] = (
    _REPO_ROOT / "src/analysis/math/engine.py",
    _REPO_ROOT / "src/analysis/math/validators.py",
    _REPO_ROOT / "src/analysis/math/comparative.py",
    _REPO_ROOT / "src/analysis/math/periods.py",
    _REPO_ROOT / "src/analysis/math/normalization.py",
    _REPO_ROOT / "src/analysis/math/precompute.py",
)


def test_outward_registry_integrity_callable() -> None:
    """A. Single source of truth: startup validation passes."""
    rc.validate_reason_code_registry()


def _ast_references_canonical_bindings_symbol(tree: ast.AST) -> bool:
    """True if AST mentions ``CANONICAL_REASON_CODE_BINDINGS`` (imports, attributes, assignment)."""
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.name == "CANONICAL_REASON_CODE_BINDINGS":
                    return True
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "CANONICAL_REASON_CODE_BINDINGS":
                    return True
        if isinstance(node, ast.Attribute) and node.attr == "CANONICAL_REASON_CODE_BINDINGS":
            return True
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id == "CANONICAL_REASON_CODE_BINDINGS":
                    return True
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            if node.target.id == "CANONICAL_REASON_CODE_BINDINGS":
                return True
    return False


def test_no_parallel_canonical_binding_tuple_elsewhere() -> None:
    """Only ``reason_codes.CANONICAL_REASON_CODE_BINDINGS`` defines the full binding list.

    Uses AST (not substring search) so comments/docstrings do not false-positive.
    """
    hits = []
    for path in sorted((_REPO_ROOT / "src/analysis/math").rglob("*.py")):
        if path.name == "reason_codes.py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        if _ast_references_canonical_bindings_symbol(tree):
            hits.append(path.relative_to(_REPO_ROOT))
    assert not hits, f"Unexpected references to CANONICAL_REASON_CODE_BINDINGS outside reason_codes.py: {hits}"


def _violations_for_inline_registry_strings(
    tree: ast.AST,
    *,
    filepath: str,
) -> list[tuple[int, str, str]]:
    """Find canonical outward strings used as inline literals in sensitive positions."""
    bad: list[tuple[int, str, str]] = []

    def check_str_in_registry(s: str, lineno: int, ctx: str) -> None:
        if s in rc.ALL_REASON_CODES:
            bad.append((lineno, ctx, s))

    def walk_call_keywords(call: ast.Call) -> None:
        for kw in call.keywords or []:
            if kw.arg is None or kw.value is None:
                continue
            if kw.arg in ("reason_code", "reason_code_primary"):
                if isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str):
                    check_str_in_registry(kw.value.value, kw.value.lineno, f"keyword {kw.arg}")
            if kw.arg in ("reason_codes", "extra_reason_codes", "refusal_reason_codes"):
                seq = kw.value
                if isinstance(seq, (ast.List, ast.Tuple)):
                    for elt in seq.elts:
                        if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                            check_str_in_registry(elt.value, elt.lineno, f"keyword {kw.arg}[]")

    class V(ast.NodeVisitor):
        def visit_Call(self, node: ast.Call) -> None:
            walk_call_keywords(node)
            self.generic_visit(node)

        def visit_Dict(self, node: ast.Dict) -> None:
            for k, v in zip(node.keys, node.values, strict=False):
                if k is None or v is None:
                    continue
                key = None
                if isinstance(k, ast.Constant) and isinstance(k.value, str):
                    key = k.value
                if key == "reason_code" and isinstance(v, ast.Constant) and isinstance(
                    v.value, str
                ):
                    check_str_in_registry(v.value, v.lineno, 'dict key "reason_code"')
                if key == "reason_codes" and isinstance(v, ast.List):
                    for elt in v.elts:
                        if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                            check_str_in_registry(elt.value, elt.lineno, 'dict "reason_codes"[]')
            self.generic_visit(node)

    V().visit(tree)
    return bad


@pytest.mark.parametrize("path", _CRITICAL_MATH_SOURCES, ids=lambda p: p.as_posix())
def test_critical_modules_avoid_inline_canonical_reason_literals(path: Path) -> None:
    """B. No ``reason_code=\"MATH_...\"``-style literals for registry tokens in critical paths."""
    assert path.is_file(), f"missing {path}"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    bad = _violations_for_inline_registry_strings(tree, filepath=str(path))
    assert not bad, f"inline canonical literals in {path}: {bad}"


