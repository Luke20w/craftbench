"""Score every V candidate against the chained ground truth. Reads whatever runs exist so far.

    python analyze.py            # markdown report on stdout, raw numbers in analysis.json
"""
from __future__ import annotations

import json
import math
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from run import OUT, PROBES, TASK, codebases, regression_base, slug  # noqa: E402
import dataclasses  # noqa: E402
import free_methods as fm  # noqa: E402

MODELS = {"opus": "claude-opus-5-5", "sonnet": "claude-sonnet-5-5"}
FLAWS = ["if_elif", "dead_code", "duplicated", "junk_names"]  # should all be harder than the reference


def gmean(xs):
    xs = [x for x in xs if x is not None]
    return math.exp(sum(math.log(max(x, 1.0)) for x in xs) / len(xs)) if xs else None


def mean(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else None


def _results(d: Path):
    return [json.loads(f.read_text()) for f in sorted(d.glob("run_*/result.json"))]


ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
from craftbench.agents import load_calls  # noqa: E402
from craftbench.analysis import ANALYZERS  # noqa: E402
from craftbench.effort import change_effort  # noqa: E402
from craftbench.grading import Curve, CurvePoint  # noqa: E402


def _curve(run_dir: Path) -> Curve:
    raw = json.loads(next(run_dir.glob("curve_*.json")).read_text())
    return Curve(tuple(raw["tests"]), tuple(CurvePoint(p["call"], frozenset(p["new"]), p["reg"]) for p in raw["points"]))


def _failed(run_dir: Path) -> set:
    c = _curve(run_dir)
    return set(c.tests) - (set(c.points[-1].new_passed) if c.points else set())


def rescore(run_dir: Path, base: Path, reg: int, drop: set) -> float:
    """Effort over the change's tests minus `drop`: tests no run on this codebase could pass, because their
    expected output depends on behaviour the milestone specs left open and this codebase chose differently."""
    c = _curve(run_dir)
    keep = tuple(t for t in c.tests if t not in drop) or c.tests
    return change_effort(load_calls(run_dir / "calls.json"), Curve(keep, c.points), base, ANALYZERS["python"], reg)


def _cost(paths):
    total = 0.0
    for p in paths:
        for f in p.rglob("run.json"):
            total += json.loads(f.read_text()).get("cost_usd", 0.0)
    return total


def collect():
    rows = {}
    for name, code in codebases().items():
        if name.startswith("x_"):  # exploits are scored separately
            continue
        base = OUT / slug(name)
        r = {"static": fm.all_static(code)}
        mb = OUT / slug(name) / "milestones_passed.json"
        reg0 = json.loads(mb.read_text())["passed"] if mb.exists() else None
        probe_drop, r["unreachable"] = {}, {}
        for c in PROBES:
            dirs = [d for m in MODELS.values() for d in sorted((base / "probe" / c / m).glob("run_*")) if (d / "result.json").exists()]
            probe_drop[c] = set.intersection(*[_failed(d) for d in dirs]) if len(dirs) >= 2 else set()
            if probe_drop[c]:
                r["unreachable"][c] = sorted(probe_drop[c])
        chain_drop = {}
        for k, h in enumerate(TASK.held_out):
            dirs = [d for m in MODELS.values() for d in sorted((base / "chain" / m).glob(f"run_*/{k + 1}_{h.id}")) if (d / "result.json").exists()]
            chain_drop[h.id] = set.intersection(*[_failed(d) for d in dirs]) if len(dirs) >= 2 else set()
            if chain_drop[h.id]:
                r["unreachable"][h.id] = sorted(chain_drop[h.id])
        for short, model in MODELS.items():
            per = {c: [rescore(d, code, reg0, probe_drop[c]) for d in sorted((base / "probe" / c / model).glob("run_*"))
                       if (d / "result.json").exists()] for c in PROBES}
            if all(per.values()):
                r[f"probe_{short}"] = gmean([mean(v) for v in per.values()])
                r[f"probe_{short}_1run"] = gmean([v[0] for v in per.values()])
                r[f"probe_{short}_runs"] = per
                r[f"probe_{short}_cost"] = _cost([base / "probe" / c / model for c in PROBES])
            per = {c: [x["effort"] for x in _results(base / "plan" / c / model)] for c in PROBES}
            if all(per.values()):
                r[f"plan_{short}"] = gmean([mean(v) for v in per.values()])
                r[f"plan_{short}_cost"] = _cost([base / "plan" / c / model for c in PROBES])
            js = _results(base / "judge" / model)
            if js:
                r[f"judge_{short}"] = gmean([gmean(j["estimates"].get(c) for c in PROBES) for j in js])
                r[f"judge_{short}_cost"] = _cost([base / "judge" / model])
            chains = []
            for run in sorted((base / "chain" / model).glob("run_*")):
                steps, prev = [], code
                for k, h in enumerate(TASK.held_out):
                    d = run / f"{k + 1}_{h.id}"
                    if not (d / "result.json").exists():
                        steps.append(None)
                        break
                    res = json.loads((d / "result.json").read_text())
                    reg = regression_base(dataclasses.replace(TASK, milestones=TASK.milestones + TASK.held_out[:k]), prev, d)
                    res["effort"] = rescore(d, prev, reg, chain_drop[h.id])
                    steps.append(res)
                    prev = d / "code"
                if all(steps):
                    chains.append(steps)
            if chains:
                r[f"truth_{short}"] = gmean([gmean(s["effort"] for s in ch) for ch in chains])
                r[f"truth_{short}_steps"] = [[round(s["effort"]) for s in ch] for ch in chains]
                r[f"truth_{short}_passed"] = [[f"{s['new_tests_passed']}/{s['new_tests_total']}" for s in ch] for ch in chains]
        if "probe_opus" in r and "probe_sonnet" in r:
            r["panel"] = gmean([r["probe_opus"], r["probe_sonnet"]])
            r["panel_1run"] = gmean([r["probe_opus_1run"], r["probe_sonnet_1run"]])
        truths = [r[k] for k in ("truth_opus", "truth_sonnet") if k in r]
        if len(truths) == len(MODELS):
            r["truth"] = gmean(truths)
        rows[name] = r
    return rows


def rank(v):
    o = sorted(range(len(v)), key=lambda i: v[i])
    r = [0.0] * len(v)
    i = 0
    while i < len(o):
        j = i
        while j + 1 < len(o) and v[o[j + 1]] == v[o[i]]:
            j += 1
        for t in range(i, j + 1):
            r[o[t]] = (i + j) / 2
        i = j + 1
    return r


def pearson(x, y):
    mx, my = sum(x) / len(x), sum(y) / len(y)
    sx = math.sqrt(sum((a - mx) ** 2 for a in x))
    sy = math.sqrt(sum((b - my) ** 2 for b in y))
    return sum((a - mx) * (b - my) for a, b in zip(x, y)) / (sx * sy) if sx and sy else float("nan")


def spearman(x, y):
    return pearson(rank(x), rank(y))


def residual(y, x):
    """y with the linear effect of x removed (both logged): what's left after size."""
    mx, my = sum(x) / len(x), sum(y) / len(y)
    b = sum((a - mx) * (c - my) for a, c in zip(x, y)) / sum((a - mx) ** 2 for a in x)
    return [c - (my + b * (a - mx)) for a, c in zip(x, y)]


def boot_ci(x, y, n=2000, seed=0):
    rnd = random.Random(seed)
    idx = list(range(len(x)))
    vals = []
    for _ in range(n):
        s = [rnd.choice(idx) for _ in idx]
        if len({x[i] for i in s}) < 3 or len({y[i] for i in s}) < 3:
            continue
        vals.append(spearman([x[i] for i in s], [y[i] for i in s]))
    vals.sort()
    return vals[int(0.025 * len(vals))], vals[int(0.975 * len(vals))]


def candidates(rows):
    keys = ["probe_opus", "probe_opus_1run", "probe_sonnet", "probe_sonnet_1run", "panel", "panel_1run",
            "plan_opus", "plan_sonnet", "judge_opus", "judge_sonnet"]
    out = {k: {n: r.get(k) for n, r in rows.items()} for k in keys}
    for m in ["nodes", "redundancy", "zlib_bytes", "clone_frac", "cc_mean", "bad_name_frac"]:
        out[f"static:{m}"] = {n: r["static"][m] for n, r in rows.items()}
    return out


def report(rows):
    lines = []
    have_truth = [n for n, r in rows.items() if r.get("truth")]
    lines.append(f"Codebases: {len(rows)}; with full ground truth: {len(have_truth)}\n")
    lines.append("| codebase | nodes | truth (opus / sonnet) | probe opus | probe sonnet | plan opus | judge sonnet |")
    lines.append("|---|---|---|---|---|---|---|")
    f = lambda v: "–" if v is None else f"{v:,.0f}"  # noqa: E731
    for n, r in rows.items():
        lines.append(f"| {n} | {r['static']['nodes']:,} | {f(r.get('truth_opus'))} / {f(r.get('truth_sonnet'))} | "
                     f"{f(r.get('probe_opus'))} | {f(r.get('probe_sonnet'))} | {f(r.get('plan_opus'))} | {f(r.get('judge_sonnet'))} |")
    if len(have_truth) >= 4:
        t = [rows[n]["truth"] for n in have_truth]
        nodes = [math.log(rows[n]["static"]["nodes"]) for n in have_truth]
        if all("truth_opus" in rows[n] and "truth_sonnet" in rows[n] for n in have_truth):
            rel = spearman([rows[n]["truth_opus"] for n in have_truth], [rows[n]["truth_sonnet"] for n in have_truth])
            lines.append(f"\nGround-truth agreement between maintainers (Opus chain vs Sonnet chain): ρ = {rel:+.2f}")
        lines.append(f"Truth vs size alone: ρ = {spearman(nodes, t):+.2f}\n")
        if all(len(rows[n].get("truth_opus_steps", [])) >= 2 for n in have_truth):
            for short in MODELS:
                a = [gmean([gmean(c) for c in rows[n][f"truth_{short}_steps"][:1]]) for n in have_truth]
                b = [gmean([gmean(c) for c in rows[n][f"truth_{short}_steps"][1:2]]) for n in have_truth]
                lines.append(f"Same maintainer, two independent chains ({short}): ρ = {spearman(a, b):+.2f}")
        lines.append("| candidate | ρ vs truth | 95% CI | vs Opus truth | vs Sonnet truth | beyond size (residual ρ) | flaws caught | golf harder | $ per codebase |")
        lines.append("|---|---|---|---|---|---|---|---|---|")
        for k, vals in candidates(rows).items():
            ns = [n for n in have_truth if vals.get(n) is not None]
            if len(ns) < 4:
                continue
            x = [vals[n] for n in ns]
            y = [rows[n]["truth"] for n in ns]
            rho = spearman(x, y)
            lo, hi = boot_ci(x, y)
            lx = [math.log(max(v, 1e-9)) for v in x]
            ln = [math.log(rows[n]["static"]["nodes"]) for n in ns]
            ly = [math.log(v) for v in y]
            beyond = spearman(residual(lx, ln), residual(ly, ln)) if k != "static:nodes" else float("nan")
            ref = vals.get("reference")
            caught = sum(1 for fl in FLAWS if vals.get(fl) is not None and ref is not None and vals[fl] > ref)
            nf = sum(1 for fl in FLAWS if vals.get(fl) is not None)
            golf = "–" if vals.get("golfed") is None or ref is None else ("yes" if vals["golfed"] > ref else "no")
            costk = k.replace("_1run", "") + "_cost"
            costs = [rows[n].get(costk) for n in ns if rows[n].get(costk) is not None]
            cost = mean(costs) / (2 if k.endswith("_1run") else 1) if costs else 0.0
            if k.startswith("panel"):
                cs = [mean([rows[n].get("probe_opus_cost"), rows[n].get("probe_sonnet_cost")]) * 2 for n in ns]
                cost = mean(cs) / (2 if k.endswith("_1run") else 1)
            ro = spearman(x, [rows[n]["truth_opus"] for n in ns])
            rs = spearman(x, [rows[n]["truth_sonnet"] for n in ns])
            lines.append(f"| {k} | {rho:+.2f} | [{lo:+.2f}, {hi:+.2f}] | {ro:+.2f} | {rs:+.2f} | {beyond:+.2f} | {caught}/{nf} | {golf} | {cost:.2f} |")
        ref = rows.get("reference", {}).get("truth")
        if ref:
            lines.append("\nGround truth on the known flaws (truth / reference): " + ", ".join(
                f"{fl} {rows[fl]['truth'] / ref:.2f}×" for fl in FLAWS + ["golfed"] if rows.get(fl, {}).get("truth")))
    lines.append("\nChain steps (effort per held-out change, per chain; tests passed):")
    for n, r in rows.items():
        for short in MODELS:
            if f"truth_{short}_steps" in r:
                lines.append(f"- {n} / {short}: {r[f'truth_{short}_steps']} {r[f'truth_{short}_passed']}")
    return "\n".join(lines)


if __name__ == "__main__":
    rows = collect()
    (ROOT / "docs/experiments/v_measures_data.json").write_text(json.dumps(rows, indent=1, default=str))
    print(report(rows))
