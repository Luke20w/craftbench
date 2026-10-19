"""Syntax-tree node counting: the unit reading is charged in, so dense (golfed) code is not cheaper
to read than the same logic written normally."""

from __future__ import annotations

import ast
import re
from functools import lru_cache
from pathlib import Path

SKIP_DIRS = {".git", "__pycache__", ".venv", "node_modules", ".pytest_cache", ".claude"}
_BOOKKEEPING = (ast.expr_context, ast.boolop, ast.operator, ast.unaryop, ast.cmpop)


def _strip_docstrings(tree: ast.AST) -> ast.AST:
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            b = node.body
            if b and isinstance(b[0], ast.Expr) and isinstance(getattr(b[0], "value", None), ast.Constant) \
                    and isinstance(b[0].value.value, str):
                node.body = b[1:] or [ast.Pass()]
    return tree


def count_nodes(source: str) -> int:
    """Meaningful nodes: identifiers kept, docstrings dropped, string contents counted as tokens
    (so hiding code in a string is not free)."""
    n = 0

    def visit(node):
        nonlocal n
        if isinstance(node, _BOOKKEEPING):
            return
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            n += 1 + len(re.findall(r"\w+|[^\w\s]", node.value))
            return
        n += 1
        for c in ast.iter_child_nodes(node):
            visit(c)

    visit(_strip_docstrings(ast.parse(source)))
    return n


def code_files(root: Path) -> list[Path]:
    return sorted(p for p in root.rglob("*.py")
                  if not set(p.relative_to(root).parts) & SKIP_DIRS and "test" not in p.name.lower())


@lru_cache(maxsize=None)
def density(path: str) -> float:
    """Nodes per character of one Python file, or of every Python file under a directory.
    0.0 when there is nothing parseable (non-Python code is then charged in plain tokens)."""
    p = Path(path)
    files = [p] if p.is_file() else code_files(p)
    chars = nodes = 0
    for f in files:
        src = f.read_text(errors="replace")
        try:
            nodes += count_nodes(src)
            chars += len(src)
        except SyntaxError:
            pass
    return nodes / chars if chars else 0.0
