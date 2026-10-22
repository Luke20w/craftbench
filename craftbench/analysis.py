"""Per-language code analysis. Used to weight what the extender reads by how dense the code is,
and for metrics that are logged but never rewarded."""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from functools import cache
from pathlib import Path

SKIP_PARTS = {"__pycache__", ".git", ".pytest_cache", ".claude", ".venv", "node_modules"}
_NO_MEANING = (ast.expr_context, ast.boolop, ast.operator, ast.unaryop, ast.cmpop)  # bookkeeping nodes


@dataclass(frozen=True)
class PythonAnalyzer:
    suffixes: tuple[str, ...] = (".py",)
    # Nodes per character of clean, documented code: the ETL reference (3291 nodes / 17353 chars).
    reference_density: float = 0.1897
    # Nodes per word-or-symbol token, which barely changes with style (0.69 clean, 0.70 golfed): how much
    # syntax a file holds when it can't be parsed.
    nodes_per_token: float = 0.694

    def nodes(self, source: str) -> int:
        """Syntax nodes, ignoring docstrings. String literals count per word, so hiding code in a
        string isn't free."""
        tree = ast.parse(source)
        for n in ast.walk(tree):
            if isinstance(n, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and n.body \
                    and isinstance(n.body[0], ast.Expr) and isinstance(getattr(n.body[0], "value", None), ast.Constant) \
                    and isinstance(n.body[0].value.value, str):
                n.body = n.body[1:] or [ast.Pass()]
        count = 0
        for n in ast.walk(tree):
            if isinstance(n, ast.Constant) and isinstance(n.value, str):
                count += 1 + len(re.findall(r"\w+|[^\w\s]", n.value))
            elif not isinstance(n, _NO_MEANING):
                count += 1
        return count


ANALYZERS = {"python": PythonAnalyzer()}


def source_files(root: Path, analyzer: PythonAnalyzer) -> list[Path]:
    """Source files under root, excluding tests and tool directories."""
    if root.is_file():
        return [root]
    return sorted(p for p in root.rglob("*") if p.suffix in analyzer.suffixes
                  and not set(p.relative_to(root).parts) & SKIP_PARTS
                  and not any("test" in part.lower() for part in p.relative_to(root).parts))


def size(root: Path, analyzer: PythonAnalyzer) -> tuple[int, int, int]:
    """(lines of code, syntax nodes, characters) across the source files."""
    loc = nodes = chars = 0
    for f in source_files(root, analyzer):
        src = f.read_text(errors="replace")
        loc += sum(1 for line in src.splitlines() if line.strip() and not line.strip().startswith("#"))
        chars += len(src)
        try:
            nodes += analyzer.nodes(src)
        except SyntaxError:  # unparseable (e.g. stripped by an import hook): estimate, never count it as nothing
            nodes += round(len(re.findall(r"\w+|[^\w\s]", src)) * analyzer.nodes_per_token)
    return loc, nodes, chars


@cache
def density_weight(target: Path | tuple[Path, ...], analyzer: PythonAnalyzer) -> float:
    """Syntax nodes per token of `target` (a file, a directory, or several files), relative to clean code:
    converts tokens of code read into clean-code-equivalent nodes, so code is measured by its syntax rather
    than its characters."""
    nodes = chars = 0
    for t in (target if isinstance(target, tuple) else (target,)):
        _, n, c = size(t, analyzer)
        nodes, chars = nodes + n, chars + c
    return nodes / chars / analyzer.reference_density if chars else 1.0


def code_metrics(root: Path, analyzer: PythonAnalyzer) -> dict:
    """Logged only, never rewarded: watch these to see what structure emerges."""
    loc, nodes, chars = size(root, analyzer)
    return {"files": len(source_files(root, analyzer)), "loc": loc, "nodes": nodes,
            "density_vs_clean": round(nodes / chars / analyzer.reference_density, 2) if chars else 0}
