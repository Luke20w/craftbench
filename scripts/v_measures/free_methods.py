"""Free (no model calls) candidates for the change-cost signal V, scored against what we already know.

Ground truth used:
  A. known flaws: the ETL reference vs its same-behaviour copies (dead code, duplicated, indirection,
     junk names should all be worse; the "you're done" note copy should tie; golf is contested), and
     the XL composable reference vs its if/elif copy (composable should be better).
  B. agreement with measured Opus extender effort (geomean over changes) on the 7 ETL variants and
     the 9 benchmark builds.
Every metric is oriented so that higher = predicted harder to change.
"""
from __future__ import annotations

import ast
import json
import math
import re
import sys
import zlib
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from craftbench.analysis import ANALYZERS, source_files  # noqa: E402

PY = ANALYZERS["python"]
ETL = ROOT / "tasks/etl_pipeline"
XL = ROOT / "tasks/etl_pipeline_xl"
CHANGES = ["subpipelines", "limits", "trace"]
WORDS = {w.strip().lower() for w in open("/usr/share/dict/words") if len(w.strip()) >= 2}
WORDS |= {"etl", "json", "args", "kwargs", "dict", "str", "int", "expr", "op", "ops", "id", "ids", "cli",
          "stdin", "stdout", "len", "init", "repr", "eq", "bool", "tuple", "isinstance", "msg", "err",
          "idx", "src", "fn", "cfg", "val", "num", "ctx", "env", "tok", "toks", "lhs", "rhs", "params",
          "param", "elif", "def", "self", "cls", "metrics", "normalized", "normalize", "subpipelines"}


# ---------------------------------------------------------------- code units
def files(root: Path) -> dict[str, str]:
    return {str(f.relative_to(root)): f.read_text() for f in source_files(root, PY)}


def units(root: Path) -> dict[str, tuple[str, int]]:
    """Readable units: every function/method, plus each file's leftover module/class-level code.
    Returns name -> (source text, syntax nodes)."""
    out = {}
    for rel, src in files(root).items():
        tree = ast.parse(src)
        lines = src.splitlines()
        covered = set()

        def visit(body, prefix):
            for n in body:
                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    seg = "\n".join(lines[n.lineno - 1 - len(n.decorator_list):n.end_lineno])
                    covered.update(range(n.lineno - 1 - len(n.decorator_list), n.end_lineno))
                    out[f"{rel}::{prefix}{n.name}"] = seg
                elif isinstance(n, ast.ClassDef):
                    visit(n.body, f"{prefix}{n.name}.")
        visit(tree.body, "")
        rest = "\n".join(l for i, l in enumerate(lines) if i not in covered)
        out[f"{rel}::<module>"] = rest
    res = {}
    for k, seg in out.items():
        try:
            nn = PY.nodes(_dedent(seg))
        except SyntaxError:
            nn = len(re.findall(r"\w+|[^\w\s]", seg)) // 2
        res[k] = (seg, nn)
    return res


def _dedent(s: str) -> str:
    import textwrap
    s = textwrap.dedent(s)
    try:
        ast.parse(s)
        return s
    except SyntaxError:
        return "if True:\n" + textwrap.indent(s, "    ") if s.strip() else "pass"


# ---------------------------------------------------------------- metrics
def m_size(root):
    loc, nodes, chars = 0, 0, 0
    for src in files(root).values():
        loc += sum(1 for l in src.splitlines() if l.strip() and not l.strip().startswith("#"))
        chars += len(src)
        nodes += PY.nodes(src)
    return {"nodes": nodes, "loc": loc, "chars": chars}


def m_compression(root):
    raw = "\n".join(files(root).values()).encode()
    comp = len(zlib.compress(raw, 9))
    return {"zlib_bytes": comp, "redundancy": 1 - comp / len(raw)}


def _norm_dump(node) -> str:
    """Structure of a subtree with identifiers and constants erased (type-2 clones)."""
    class E(ast.NodeTransformer):
        def visit_Name(self, n): return ast.Name(id="_", ctx=n.ctx)
        def visit_arg(self, n): return ast.arg(arg="_")
        def visit_Attribute(self, n): self.generic_visit(n); n.attr = "_"; return n
        def visit_Constant(self, n): return ast.Constant(value=0)
    import copy
    return ast.dump(E().visit(copy.deepcopy(node)), annotate_fields=False)


def _count(node) -> int:
    return sum(1 for _ in ast.walk(node))


def m_clones(root, min_nodes=25):
    """Share of statement-subtree nodes that belong to a structural clone appearing 2+ times."""
    seen = defaultdict(list)
    total = 0
    for src in files(root).values():
        tree = ast.parse(src)
        total += _count(tree)
        for n in ast.walk(tree):
            if isinstance(n, ast.stmt) and _count(n) >= min_nodes:
                seen[_norm_dump(n)].append(n)
    covered = set()  # nodes inside copies beyond the first; a set so nested clones count once
    for occ in seen.values():
        for copy_ in occ[1:]:
            covered.update(id(x) for x in ast.walk(copy_))
    return {"clone_frac": len(covered) / total if total else 0}


def _defs_and_refs(root):
    defs, refs = {}, Counter()
    for rel, src in files(root).items():
        tree = ast.parse(src)
        for n in ast.walk(tree):
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and not n.decorator_list:
                defs.setdefault(n.name, []).append(_count(n))  # decorated = registered somewhere, so live
            elif isinstance(n, ast.Name):
                refs[n.id] += 1
            elif isinstance(n, ast.Attribute):
                refs[n.attr] += 1
            elif isinstance(n, ast.Constant) and isinstance(n.value, str):
                for w in re.findall(r"[A-Za-z_]\w*", n.value):
                    refs[w] += 1  # dispatch-by-string (getattr(f"op_{x}")) shouldn't count as dead
            elif isinstance(n, (ast.Import, ast.ImportFrom)):
                for a in n.names:
                    refs[a.name.split(".")[-1]] += 1
    return defs, refs


def m_dead(root):
    """Share of nodes in functions/classes whose name is never referenced (crude, prefix-dispatch aware)."""
    defs, refs = _defs_and_refs(root)
    total = sum(_count(ast.parse(s)) for s in files(root).values())
    keep = {"main", "__init__"}
    prefixes = {re.match(r"([a-z]+_)", k).group(1) for k in refs if re.match(r"[a-z]+_$", k)}
    dead = 0
    for name, sizes in defs.items():
        if name in keep or name.startswith("__") or refs[name] > 0:
            continue
        if any(name.startswith(p) for p in prefixes):
            continue
        dead += sum(sizes)
    return {"dead_frac": dead / total if total else 0}


def m_complexity(root):
    """Mean and max cyclomatic complexity per function."""
    ccs = []
    for src in files(root).values():
        for n in ast.walk(ast.parse(src)):
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
                cc = 1 + sum(isinstance(x, (ast.If, ast.For, ast.While, ast.IfExp, ast.ExceptHandler,
                                            ast.With, ast.comprehension, ast.Assert, ast.match_case))
                             + (len(x.values) - 1 if isinstance(x, ast.BoolOp) else 0)
                             for x in ast.walk(n))
                ccs.append(cc)
    return {"cc_mean": sum(ccs) / len(ccs) if ccs else 0, "cc_max": max(ccs, default=0)}


def m_propagation(root):
    """MacCormack propagation cost on the function call graph: average share of functions a change
    to one function can reach (transitively through callers)."""
    us = units(root)
    short = {k: k.split("::")[1].split(".")[-1] for k in us if not k.endswith("<module>")}
    by_name = defaultdict(set)
    for k, s in short.items():
        by_name[s].add(k)
    edges = defaultdict(set)
    for k in short:
        text = us[k][0]
        for w in set(re.findall(r"[A-Za-z_]\w*", text)):
            for tgt in by_name.get(w, ()):
                if tgt != k:
                    edges[k].add(tgt)
    n = len(short)
    if n == 0:
        return {"prop_cost": 0}
    reach_total = 0
    for k in short:
        seen, stack = {k}, [k]
        while stack:
            for t in edges[stack.pop()]:
                if t not in seen:
                    seen.add(t)
                    stack.append(t)
        reach_total += len(seen)
    return {"prop_cost": reach_total / (n * n)}


def _idents(root):
    ids = []
    for src in files(root).values():
        for n in ast.walk(ast.parse(src)):
            if isinstance(n, ast.Name):
                ids.append(n.id)
            elif isinstance(n, (ast.FunctionDef, ast.ClassDef, ast.AsyncFunctionDef)):
                ids.append(n.name)
            elif isinstance(n, ast.arg):
                ids.append(n.arg)
            elif isinstance(n, ast.Attribute):
                ids.append(n.attr)
    return ids


def _split(ident):
    parts = re.sub(r"([a-z])([A-Z])", r"\1_\2", ident).lower().split("_")
    return [p for p in parts if p]


def m_names(root):
    """Share of identifier pieces that aren't dictionary words (higher = worse names)."""
    pieces = [p for i in set(_idents(root)) for p in _split(i)]
    bad = sum(1 for p in pieces if p not in WORDS and not p.isdigit())
    return {"bad_name_frac": bad / len(pieces) if pieces else 0}


# ---------------------------------------------------------------- retrieval
def _toks(text):
    return [p for w in re.findall(r"[A-Za-z][A-Za-z0-9_]*", text) for p in _split(w) if len(p) > 1]


def bm25_rank(query, docs, k1=1.5, b=0.75):
    toks = {k: _toks(v) for k, v in docs.items()}
    N = len(toks)
    avg = sum(len(t) for t in toks.values()) / N
    df = Counter(w for t in toks.values() for w in set(t))
    q = Counter(_toks(query))
    scores = {}
    for k, t in toks.items():
        tf = Counter(t)
        s = 0.0
        for w in q:
            if w in tf:
                idf = math.log(1 + (N - df[w] + 0.5) / (df[w] + 0.5))
                s += idf * tf[w] * (k1 + 1) / (tf[w] + k1 * (1 - b + b * len(t) / avg))
        scores[k] = s
    return sorted(docs, key=lambda k: -scores[k])


def touched(before: Path, after: Path) -> set[str]:
    """Units of `before` that the extender changed or removed in `after`."""
    ub, ua = units(before), units(after)
    norm = lambda s: re.sub(r"\s+", " ", s).strip()
    return {k for k, (seg, _) in ub.items() if k not in ua or norm(ua[k][0]) != norm(seg)}


def retrieval_cost(root: Path, spec: str, need: set[str]):
    """Nodes a BM25-ordered reader reads before it has seen every unit that needed changing."""
    us = units(root)
    order = bm25_rank(spec, {k: v[0] for k, v in us.items()})
    need = need & set(us)
    if not need:
        return None
    read = 0
    left = set(need)
    for k in order:
        read += us[k][1]
        left.discard(k)
        if not left:
            break
    total = sum(v[1] for v in us.values())
    return read, read / total


# ---------------------------------------------------------------- ground truth
def gmean(xs):
    xs = [x for x in xs if x]
    return math.exp(sum(math.log(x) for x in xs) / len(xs)) if xs else None


def etl_efforts(variant):
    """All Opus extender runs on this variant: change -> [effort, ...] (opus_rel x2 + opus x1)."""
    out = defaultdict(list)
    for g in [ROOT / f"runs/opus_rel/{variant}/grade.json", ROOT / f"runs/opus/etl_pipeline/validate_{variant}/grade.json"]:
        if g.exists():
            d = json.loads(g.read_text())
            for ch, runs in d.get("extender_runs", {}).items():
                out[ch] += [r["effort"] for r in runs if r.get("effort")]
            if not d.get("extender_runs"):
                for ch, e in d["efforts"].items():
                    out[ch].append(e)
    return out


def spearman(xs, ys):
    def rank(v):
        o = sorted(range(len(v)), key=lambda i: v[i])
        r = [0] * len(v)
        i = 0
        while i < len(o):
            j = i
            while j + 1 < len(o) and v[o[j + 1]] == v[o[i]]:
                j += 1
            for t in range(i, j + 1):
                r[o[t]] = (i + j) / 2
            i = j + 1
        return r
    rx, ry = rank(xs), rank(ys)
    mx, my = sum(rx) / len(rx), sum(ry) / len(ry)
    cov = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    sx = math.sqrt(sum((a - mx) ** 2 for a in rx))
    sy = math.sqrt(sum((b - my) ** 2 for b in ry))
    return cov / (sx * sy) if sx and sy else float("nan")


def all_static(root):
    m = {}
    for f in (m_size, m_compression, m_clones, m_dead, m_complexity, m_propagation, m_names):
        m.update(f(root))
    return m


def main():
    variants = ["reference", "control_misleading_note", "dead_code", "duplicated", "indirection", "junk_names", "golfed"]
    rows = {}
    for v in variants:
        root = ETL / ("reference" if v == "reference" else f"mutants/{v}")
        r = all_static(root)
        eff = etl_efforts(v)
        r["extender"] = gmean([gmean(eff[c]) for c in CHANGES])
        r["extender_per_change"] = {c: gmean(eff[c]) for c in CHANGES}
        # retrieval: what did the extender actually have to change, per change, per run
        rc, rf = {}, {}
        for c in CHANGES:
            spec = (ETL / f"specs/{c}.md").read_text()
            costs = []
            for run in sorted((ROOT / f"runs/opus_rel/{v}/maintain/{c}").glob("run_*/code")):
                res = retrieval_cost(root, spec, touched(root, run))
                if res:
                    costs.append(res)
            if costs:
                rc[c] = gmean([x[0] for x in costs])
                rf[c] = sum(x[1] for x in costs) / len(costs)
        r["retrieval_nodes"] = gmean(list(rc.values()))
        r["retrieval_frac"] = sum(rf.values()) / len(rf) if rf else None
        r["retrieval_per_change"] = rc
        rows[v] = r

    xl = {}
    for v, root in [("xl_reference", XL / "reference"), ("xl_if_elif", XL / "mutants/if_elif")]:
        r = all_static(root)
        g = json.loads((ROOT / f"data/bench/etl_pipeline_xl/validate_{v[3:]}/grade.json").read_text())
        r["extender"] = gmean(list(g["efforts"].values()))
        xl[v] = r

    bench = {}
    for mdir in sorted((ROOT / "data/bench/etl_pipeline/bench").iterdir()):
        for s in sorted(mdir.iterdir()):
            g = json.loads((s / "grade.json").read_text())
            r = all_static(s / "build/code")
            r["extender"] = gmean(list(g["efforts"].values()))
            bench[f"{mdir.name.replace('claude-', '')}/{s.name}"] = r

    json.dump({"etl": rows, "xl": xl, "bench": bench}, open(Path(__file__).with_name("results.json"), "w"), indent=1, default=str)
    report(rows, xl, bench)


METRICS = ["nodes", "loc", "chars", "zlib_bytes", "redundancy", "clone_frac", "dead_frac", "cc_mean", "cc_max",
           "prop_cost", "bad_name_frac", "retrieval_nodes", "retrieval_frac", "extender"]


def report(rows, xl, bench):
    flaws = ["dead_code", "duplicated", "indirection", "junk_names"]
    print("\n## ETL variants (higher = predicted harder)\n")
    print("| metric | " + " | ".join(rows) + " |")
    print("|---|" + "---|" * len(rows))
    for m in METRICS:
        vals = [rows[v].get(m) for v in rows]
        print(f"| {m} | " + " | ".join(_fmt(x) for x in vals) + " |")

    print("\n## Scorecard\n")
    print("| metric | clear flaws caught (of 4) | control tie (<5%) | golf rated worse | XL if/elif worse | ρ vs extender (ETL 7) | ρ vs extender (9 builds) | ρ with nodes (builds) |")
    print("|---|---|---|---|---|---|---|---|")
    ref = rows["reference"]
    for m in METRICS:
        if ref.get(m) is None:
            continue
        caught = sum(1 for f in flaws if rows[f].get(m) is not None and rows[f][m] > ref[m] * 1.0001)
        ctl = rows["control_misleading_note"][m]
        tie = "yes" if ref[m] and abs(ctl - ref[m]) / abs(ref[m]) < 0.05 else ("yes" if ref[m] == ctl else "no")
        golf = "yes" if rows["golfed"][m] > ref[m] else "no"
        xlw = ("yes" if xl["xl_if_elif"].get(m, 0) > xl["xl_reference"].get(m, 0) else "no") if m in xl["xl_reference"] else "n/a"
        ks = [v for v in rows if rows[v].get(m) is not None]
        rho_e = spearman([rows[v][m] for v in ks], [rows[v]["extender"] for v in ks]) if m != "extender" else 1
        bk = [b for b in bench if bench[b].get(m) is not None]
        rho_b = spearman([bench[b][m] for b in bk], [bench[b]["extender"] for b in bk]) if bk and m != "extender" else (1 if m == "extender" else None)
        rho_n = spearman([bench[b][m] for b in bk], [bench[b]["nodes"] for b in bk]) if bk else None
        print(f"| {m} | {caught}/4 | {tie} | {golf} | {xlw} | {_fmt(rho_e)} | {_fmt(rho_b)} | {_fmt(rho_n)} |")

    print("\n## XL\n")
    for m in METRICS:
        if m in xl["xl_reference"]:
            print(f"- {m}: reference {_fmt(xl['xl_reference'][m])} vs if/elif {_fmt(xl['xl_if_elif'][m])}")
    print("\n## Builds\n")
    print("| build | " + " | ".join(m for m in METRICS if m in next(iter(bench.values()))) + " |")
    for b, r in bench.items():
        print(f"| {b} | " + " | ".join(_fmt(r.get(m)) for m in METRICS if m in r) + " |")


def _fmt(x):
    if x is None:
        return "–"
    if isinstance(x, float):
        return f"{x:.3f}" if abs(x) < 10 else f"{x:,.0f}"
    return f"{x:,}" if isinstance(x, int) else str(x)


if __name__ == "__main__":
    main()
