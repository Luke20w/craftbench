"""Does the reward rate known-good code as easier to change than known-worse code?

A task can ship a reference solution and mutants: copies with the same behaviour and one deliberate
degradation (dead code, duplicated logic, junk names, needless indirection, golfing). Mutants named
control_* are the same code (e.g. plus a misleading comment) and should not look easier.

Recorded runs are laid out as <root>/<variant>/<change>/<run>/{calls.json, curve_<change>.json}.
"""

from __future__ import annotations

import statistics as st
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from .agents import RecordedAgent
from .env import Environment
from .grading import run_suites
from .reward import reward


def variants(env: Environment) -> dict[str, Path]:
    return {"reference": env.task.reference, **env.task.mutant_dirs()}


def live(env: Environment) -> dict[str, dict]:
    """Grade the reference and every mutant with real extender runs."""
    def grade(item):
        name, code = item
        g = env.grade(code, env.runs_dir / env.task.id / f"validate_{name}")
        return name, {"F": g.milestone_pass_fraction, "efforts": g.efforts}

    with ThreadPoolExecutor(4) as ex:  # variants at once; each also runs its extenders in parallel
        return dict(ex.map(grade, variants(env).items()))


def recorded(env: Environment, root: Path) -> dict[str, dict]:
    """Re-grade recorded extender runs (no model calls)."""
    out = {}
    for name, code in variants(env).items():
        if not (root / name).exists():
            continue
        milestones = run_suites(env.task, code, list(env.task.milestones))
        passed = sum(len(r.passed) for r in milestones.values())
        efforts = {}
        for change_dir in sorted(p for p in (root / name).iterdir() if p.is_dir()):
            change = env.task.change(change_dir.name)
            runs = [env.score(RecordedAgent(d).run(code, "", d), d, code, change, passed)["effort"]
                    for d in sorted(change_dir.iterdir()) if (d / "calls.json").exists()]
            efforts[change.id] = st.mean(runs)
        out[name] = {"F": passed / sum(len(r.tests) for r in milestones.values()), "efforts": efforts}
    return out


def report(results: dict[str, dict], lam: float = 0.5) -> str:
    ref = results["reference"]
    changes = sorted(ref["efforts"])
    rows = ["| variant | F | " + " | ".join(f"effort: {c}" for c in changes) + " | reward ×100 | verdict |",
            "|---|---|" + "---|" * len(changes) + "---|---|"]
    ref_reward = reward(ref["F"], list(ref["efforts"].values()), lam)
    pairs = []
    for name, r in results.items():
        rew = reward(r["F"], list(r["efforts"].values()), lam)
        if name == "reference":
            verdict = ""
        elif name.startswith("control_"):  # same code as the reference; should not look easier
            verdict = "control (same code)"
        else:
            verdict = "✓ harder" if rew < ref_reward else "✗ easier"
            pairs += [r["efforts"][c] > ref["efforts"][c] for c in changes]
        cells = " | ".join(f"{r['efforts'][c]:,.0f}" for c in changes)
        rows.append(f"| {name} | {r['F']:.2f} | {cells} | {rew * 100:.3f} | {verdict} |")
    rows.append(f"\nPer-change comparisons where the degraded copy needed more effort: {sum(pairs)}/{len(pairs)}")
    return "\n".join(rows)
