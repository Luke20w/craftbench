"""Tables for the docrender axes experiment: per variant and change stream, reading (CraftBench effort),
change size, files touched and tests passed; then the by_kind / by_format ratio per stream and reader.

    python scripts/structure_axes/analyze.py
"""
from __future__ import annotations

import ast
import difflib
import json
import math
import re
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from run import OUT, TASK, slug  # noqa: E402

STREAMS = {"K": ["k1_strikethrough", "k2_callout", "k3_definition_list"], "F": ["f1_asciidoc", "f2_textile", "f3_rst"],
           "S": ["s1_list_start", "s2_quote_cite", "s3_default_alt"]}
TOK = re.compile(r"\w+|[^\w\s]")
SKIP = {"__pycache__", ".claude", ".git"}


def units(code: Path) -> dict[str, str]:
    """file::qualname -> normalized source (docstrings and formatting removed), per function; the rest of each
    module or class body as one unit."""
    out: dict[str, str] = {}
    for f in sorted(code.rglob("*.py")):
        if set(f.relative_to(code).parts) & SKIP:
            continue
        rel = str(f.relative_to(code))
        try:
            tree = ast.parse(f.read_text())
        except (SyntaxError, UnicodeDecodeError):
            out[rel + "::<unparsed>"] = f.read_text(errors="ignore")
            continue
        for n in ast.walk(tree):
            b = getattr(n, "body", None)
            if isinstance(b, list) and b and isinstance(b[0], ast.Expr) and isinstance(getattr(b[0], "value", None), ast.Constant) \
                    and isinstance(b[0].value.value, str):
                n.body = b[1:] or [ast.Pass()]

        def visit(node, prefix):
            rest = []
            for s in node.body:
                if isinstance(s, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    out[f"{rel}::{prefix}{s.name}"] = ast.unparse(s)
                elif isinstance(s, ast.ClassDef):
                    visit(s, f"{prefix}{s.name}.")
                else:
                    rest.append(ast.unparse(s))
            out[f"{rel}::{prefix}<body>"] = "\n".join(rest)
        visit(tree, "")
    return out


def diff(before: Path, after: Path) -> dict:
    """Tokens removed plus tokens added, per unit; files and units touched."""
    a, b = units(before), units(after)
    changed = 0
    for k in a.keys() | b.keys():
        if a.get(k) != b.get(k):
            x, y = TOK.findall(a.get(k, "")), TOK.findall(b.get(k, ""))
            for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, x, y, autojunk=False).get_opcodes():
                if op != "equal":
                    changed += (i2 - i1) + (j2 - j1)
    files = {k.split("::")[0] for k in a.keys() | b.keys() if a.get(k) != b.get(k)}
    return {"tokens": changed, "files": len(files), "units": sum(1 for k in a.keys() | b.keys() if a.get(k) != b.get(k))}


def geomean(xs):
    xs = [x for x in xs if x is not None]
    return math.exp(sum(math.log(max(x, 1)) for x in xs) / len(xs)) if xs else None


def collect() -> list[dict]:
    rows = []
    cache_f = OUT / "analysis_cache_tokens.json"
    cache = json.loads(cache_f.read_text()) if cache_f.exists() else {}
    for variant, base in TASK.mutant_dirs().items():
        for change in [c for s in STREAMS.values() for c in s]:
            for model_dir in sorted((OUT / slug(variant) / change).glob("*")):
                for run in sorted(model_dir.glob("run_*")):
                    res = run / "result.json"
                    if not res.exists():
                        continue
                    r = json.loads(res.read_text())
                    if r["key"] not in cache:
                        cache[r["key"]] = diff(base, run / "code")
                    rows.append({"variant": variant, "change": change, "model": model_dir.name, "run": run.name,
                                 "effort": r["effort"], "passed": r["new_tests_passed"], "total": r["new_tests_total"],
                                 "cost": r.get("cost_usd", 0), **cache[r["key"]]})
    cache_f.write_text(json.dumps(cache))
    return rows


def main():
    rows = collect()
    by = defaultdict(list)
    for r in rows:
        by[(r["variant"], r["change"], r["model"])].append(r)
    models = sorted({r["model"] for r in rows})
    variants = list(TASK.mutant_dirs())
    for metric in ("effort", "tokens", "files"):
        print(f"\n== {metric} (geomean over runs; per change) ==")
        changes = [c for s in STREAMS.values() for c in s]
        print(f"{'variant':10} {'model':18}", *(f"{c[:12]:>12}" for c in changes))
        for v in variants:
            for m in models:
                vals = [geomean([r[metric] for r in by[(v, c, m)]]) for c in changes]
                if any(vals):
                    print(f"{v:10} {m:18}", *(f"{x:12.0f}" if x else f"{'-':>12}" for x in vals))
    print("\n== tests passed (sum over runs) ==")
    for v in variants:
        for m in models:
            cells = [f"{sum(r['passed'] for r in by[(v, c, m)])}/{sum(r['total'] for r in by[(v, c, m)])}"
                     for s in STREAMS.values() for c in s]
            if any(by[(v, c, m)] for s in STREAMS.values() for c in s):
                print(f"{v:10} {m:18}", *(f"{x:>12}" for x in cells))

    print("\n== per stream: geomean over the stream's changes, relative to by_format ==")
    for metric in ("effort", "tokens", "files"):
        for m in models:
            line = []
            for s, changes in STREAMS.items():
                ref = geomean([geomean([r[metric] for r in by[("by_format", c, m)]]) for c in changes])
                for v in variants:
                    g = geomean([geomean([r[metric] for r in by[(v, c, m)]]) for c in changes if by[(v, c, m)]])
                    if g and ref:
                        line.append(f"{s}:{v} {g / ref:.2f}")
            print(f"{metric:7} {m:18}", "  ".join(line))


if __name__ == "__main__":
    main()
