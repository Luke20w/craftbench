"""Results for docs/experiments/review_followups.md from the runs that exist (no model calls).

    python scripts/review/analyze.py      # markdown on stdout, raw numbers in review_followups_data.json
"""
from __future__ import annotations

import json
import re
import statistics as st
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/v_measures"))
import analyze as va  # noqa: E402
import run as vm  # noqa: E402
from craftbench.agents import load_calls  # noqa: E402
from craftbench.effort import _printed_args, _workspace_paths  # noqa: E402
from followups import NOTES, TRUST  # noqa: E402

va.MODELS = {"opus": "claude-opus-5-5", "sonnet": "claude-sonnet-5-5", "codex": "gpt-6-astra"}
READERS = list(va.MODELS)
CLAUDE = {"opus": "claude-opus-5-5", "sonnet": "claude-sonnet-5-5"}


def rho_ci(x, y):
    lo, hi = va.boot_ci(x, y)
    return f"{va.spearman(x, y):+.2f} [{lo:+.2f}, {hi:+.2f}]"


# ------------------------------------------------------------------ 2 + 4: offline, from the V-measures runs
def defects(rows):
    """Defect rate per codebase: mean over its chains of the mean over steps."""
    f = vm.OUT / "defects.json"
    if not f.exists():
        return {}
    data = json.loads(f.read_text())
    return {n: st.mean(st.mean(c["defects"]) for c in chains) for n, chains in data.items() if n in rows}


def third_reader(rows):
    lines = ["| left-out maintainer | panel of the other two | " + " | ".join(f"{r} probe" for r in READERS) + " |",
             "|---|---|" + "---|" * len(READERS)]
    for out in READERS:
        ns = [n for n, r in rows.items() if r.get(f"truth_{out}") and all(r.get(f"probe_{x}_1run") for x in READERS)]
        y = [rows[n][f"truth_{out}"] for n in ns]
        others = [x for x in READERS if x != out]
        panel = [va.gmean([rows[n][f"probe_{x}_1run"] for x in others]) for n in ns]
        singles = [rho_ci([rows[n][f"probe_{x}_1run"] for n in ns], y) + (" (own)" if x == out else "") for x in READERS]
        lines.append(f"| {out} ({len(ns)}) | {rho_ci(panel, y)} | " + " | ".join(singles) + " |")
    agree = [f"{a}–{b} {va.spearman(*[[rows[n][f'truth_{m}'] for n in rows] for m in (a, b)]):+.2f}"
             for i, a in enumerate(READERS) for b in READERS[i + 1:]]
    return "\n".join(lines) + "\n\nAgreement between maintainers (ρ of chain cost): " + ", ".join(agree)


def defects_section(rows, rate):
    ns = [n for n in rows if n in rate]
    lines = ["| codebase | defect rate | reading cost (Opus+Sonnet chains) |", "|---|---|---|"]
    for n in ns:
        lines.append(f"| {n} | {rate[n]:.3%} | {rows[n].get('truth', float('nan')):,.0f} |")
    if len({rate[n] for n in ns}) < 3:
        return "\n".join(lines + ["", "Too little variance in defect rates to correlate with anything."])
    lines += ["", "| candidate | ρ vs defect rate (95% CI) |", "|---|---|"]
    cands = {"reading answer key (chains)": {n: rows[n].get("truth") for n in ns},
             **{f"probe {r} (1 run)": {n: rows[n].get(f"probe_{r}_1run") for n in ns} for r in READERS},
             "panel Opus+Sonnet (2 runs)": {n: rows[n].get("panel") for n in ns},
             "plan-only Sonnet": {n: rows[n].get("plan_sonnet") for n in ns},
             "judge Sonnet": {n: rows[n].get("judge_sonnet") for n in ns},
             **{f"static: {m}": {n: rows[n]["static"][m] for n in ns} for m in ("nodes", "clone_frac", "bad_name_frac")}}
    for k, v in cands.items():
        m = [n for n in ns if v.get(n) is not None]
        if len(m) >= 4:
            lines.append(f"| {k} | {rho_ci([v[n] for n in m], [rate[n] for n in m])} |")
    ref = rate.get("reference")
    if ref is not None:
        lines.append("\nDefect rate relative to the reference: " + ", ".join(
            f"{f} {rate[f] / ref:.2f}×" if ref else f"{f} {rate[f]:.3%}" for f in va.FLAWS + ["golfed"] if f in rate))
    return "\n".join(lines)


# ------------------------------------------------------------------ 1 + 3: the live runs
def runs(name, kind, change, model):
    return sorted((vm.OUT / vm.slug(name) / kind / change / model).glob("run_*/result.json"))


_SEARCH = re.compile(r"(^|[;&|(]\s*)(grep|rg)\b")  # turned into `:`, which prints nothing


def ops_opened(run_dir: Path, base: Path) -> float:
    """Share of the op modules' characters in files the run opened (Read, or a file-printing shell command naming
    the file). Searches (grep, rg, Grep) and whole directories don't count: they print only matching lines."""
    opened = set()
    for c in load_calls(run_dir / "calls.json"):
        args = ([c.input.get("file_path", "")] if c.name == "Read" else
                _printed_args(_SEARCH.sub(r"\1:", c.input.get("command", ""))) if c.name == "Bash" else [])
        opened |= {p.resolve() for p in _workspace_paths(args, base) if p.is_file()}
    size = {p.resolve(): len(p.read_text()) for p in (base / "etl/ops").glob("*.py")}
    return sum(n for p, n in size.items() if p in opened) / sum(size.values())


def run_stats(name, base, kind, change, model):
    out = []
    for f in runs(name, kind, change, model):
        r = json.loads(f.read_text())
        out.append({"effort": r["effort"], "passed": r["new_tests_passed"], "total": r["new_tests_total"],
                    "ops_read": ops_opened(f.parent, base), "edited_ops": edited_ops(f.parent, base)})
    return out


# Runs reused from the V-measures experiment keep their snapshots only where they were first run.
SNAP_ROOTS = [vm.OUT, ROOT.parent / "islamabad/.context/runs/exp_v"]


def edited_ops(run_dir: Path, base: Path) -> int:
    """Op modules the final snapshot changed (-1 if no snapshot is available)."""
    rel = run_dir.relative_to(vm.OUT)
    snaps = [s for root in SNAP_ROOTS for s in sorted((root / rel / "snaps").glob("[0-9]*"), key=lambda p: int(p.name))]
    if not snaps:
        return -1
    final = snaps[-1]
    return sum((final / "etl/ops" / p.name).exists() and (final / "etl/ops" / p.name).read_text() != p.read_text()
               for p in (base / "etl/ops").glob("*.py"))


def passed(rs) -> str:
    return ", ".join(f"{r['passed']}/{r['total']}" for r in rs)


def trust_section():
    lines = ["| variant | model | effort (mean of runs) | op modules opened | op modules edited | limits tests passed |",
             "|---|---|---|---|---|---|"]
    raw = {}
    for v, (name, base) in TRUST.items():
        for short, model in CLAUDE.items():
            s = raw[f"{v}/{short}"] = run_stats(name, base, "probe", "limits", model)
            if s:
                edited = ", ".join(str(x["edited_ops"]) for x in s)
                lines.append(f"| {v} | {short} | {st.mean(x['effort'] for x in s):,.0f} | "
                             f"{st.mean(x['ops_read'] for x in s):.0%} | {edited} | {passed(s)} |")
    return "\n".join(lines), raw


def notes_section():
    lines = ["| codebase | arm | change | model | effort per run | tests passed |", "|---|---|---|---|---|---|"]
    raw = {}
    for name, base in NOTES.items():
        for kind in ("probe", "probe_untrusted"):
            for change in ("limits", "trace"):
                for short, model in CLAUDE.items():
                    rs = [json.loads(f.read_text()) for f in runs(name, kind, change, model)]
                    rs = [{"effort": r["effort"], "passed": r["new_tests_passed"], "total": r["new_tests_total"]} for r in rs]
                    raw[f"{name}/{kind}/{change}/{short}"] = rs
                    if rs:
                        efforts = ", ".join(f"{r['effort']:,.0f}" for r in rs)
                        lines.append(f"| {name} | {kind} | {change} | {short} | {efforts} | {passed(rs)} |")
    return "\n".join(lines), raw


if __name__ == "__main__":
    rows = va.collect()
    rate = defects(rows)
    trust, trust_raw = trust_section()
    notes, notes_raw = notes_section()
    print("## 1. Notes\n\n" + notes + "\n\n## 2. Defects\n\n" + defects_section(rows, rate) +
          "\n\n## 3. Trust gap\n\n" + trust + "\n\n## 4. Third reader\n\n" + third_reader(rows))
    (ROOT / "docs/experiments/review_followups_data.json").write_text(json.dumps(
        {"rows": rows, "defects": rate, "trust": trust_raw, "notes": notes_raw}, indent=1, default=str))
