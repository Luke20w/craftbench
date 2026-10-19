"""Replay recorded Claude Code runs (.context/exp7, circuit_eval scale test) through the package and
check it reproduces the experiment's nodes_read_per_test. No model calls: grading comes from each run's
recorded curve.json (per-snapshot test results), so nothing is re-executed either."""

from __future__ import annotations

import json
import statistics as st
from pathlib import Path

from .events import RunRecord
from .harnesses.claude_code import ClaudeCode
from .nodes import density
from .scoring import Grade, nodes_read_per_test

DEFAULT = Path(__file__).resolve().parent.parent / ".context" / "exp7"
EXPECTED = {("modular", "stats"): 10015, ("onefile", "stats"): 24161, ("onefile_junk", "stats"): 24346,
            ("modular", "dot"): 14445, ("onefile", "dot"): 24415, ("onefile_junk", "dot"): 24560}


def replay(run_dir: Path, base_dir: Path) -> tuple[RunRecord, dict]:
    h = ClaudeCode()
    lines = [(0.0, l) for l in (run_dir / "transcript.jsonl").read_text().splitlines()]
    calls, meta = h.parse(lines)
    snaps = h.hook_snapshots(calls, run_dir / "snaps")
    rec = RunRecord(extender_id="haiku-free", harness=h.name, model="haiku", seed=0, workdir=run_dir / "code",
                    transcript=run_dir / "transcript.jsonl", calls=calls, snapshots=snaps, **{k: meta.get(k) for k in ("cost_usd", "stop_reason", "turns")})
    curve = json.loads((run_dir / "curve.json").read_text())
    by_name = {f"{p['call']:04d}": p for p in curve["points"]}
    return rec, {"curve": curve, "grade": lambda d: Grade(frozenset(by_name[d.name]["new"]), by_name[d.name]["reg"])}


def main(exp7: Path | None = None) -> None:
    exp7 = exp7 or DEFAULT
    if not (exp7 / "runs").exists():
        raise SystemExit(f"selftest needs the recorded scale-test runs at {exp7}, which aren't included in this repo")
    ref = density(str(exp7 / "bases" / "modular"))
    got, worst = {}, 0.0
    for run in sorted(exp7.glob("runs/*/*/s*")):
        variant, cr = run.parts[-3], run.parts[-2]
        base = exp7 / "bases" / variant
        rec, g = replay(run, base)
        s = nodes_read_per_test(rec, g["grade"], g["curve"]["tests"], 437, base, ref)
        got.setdefault((variant, cr), []).append(s["nodes_read_per_test"])
    print(f"{'cell':22}{'package':>10}{'experiment':>12}{'diff':>8}")
    for k, v in sorted(got.items()):
        m = st.mean(v)
        diff = m / EXPECTED[k] - 1
        worst = max(worst, abs(diff))
        print(f"{'/'.join(k):22}{m:>10.0f}{EXPECTED[k]:>12}{diff:>+8.1%}")
    print(f"\nlargest deviation {worst:.1%}: {'OK' if worst < 0.05 else 'CHECK'} (differences come from classifying "
          f"shell greps as searches; rankings must match)")
    order = lambda d: [k[0] for k in sorted(d, key=lambda k: (k[1], d[k]))]  # noqa: E731
    pkg = {k: st.mean(v) for k, v in got.items()}
    print("ranking per change matches experiment:", order(pkg) == order(EXPECTED))
    group_check(exp7)


def group_check(exp7: Path | None = None) -> None:
    """End-to-end score_group on recorded runs: three codebases (rollouts) x 2 recorded seeds of one extender."""
    from dataclasses import replace

    from . import config
    from .panel import score_group

    exp7 = exp7 or DEFAULT
    panel = config.load()
    panel = replace(panel, extenders=tuple(replace(e, seeds=2) for e in panel.extenders if e.id == "haiku-free"))
    ref = density(str(exp7 / "bases" / "modular"))
    runs, bases, grades, tests = {}, {}, {}, None
    for variant in ("modular", "onefile", "onefile_junk"):
        bases[variant] = exp7 / "bases" / variant
        runs[variant] = []
        for run in sorted((exp7 / "runs" / variant / "stats").glob("s*")):
            rec, g = replay(run, bases[variant])
            rec.workdir = run / "code"
            runs[variant].append(rec)
            grades[str(run / "snaps")] = g["grade"]
            tests = g["curve"]["tests"]
    grade = lambda d: grades[str(d.parent)](d)  # noqa: E731
    out = score_group(panel, runs, bases, grade, tests, 437, ref)
    print("\nscore_group on recorded stats runs (cost ~1 = group typical, lower = cheaper to change):")
    for rid, v in sorted(out.items(), key=lambda kv: kv[1]["cost"]):
        print(f"  {rid:14} cost {v['cost']:.2f}   raw {v['by_extender']}")
