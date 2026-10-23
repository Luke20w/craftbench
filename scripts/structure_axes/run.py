"""Does change cost see structure? The docrender task's five organizations of the same behaviour, each given
both streams of changes (new node kinds, new formats) by a frozen extender.

    python scripts/structure_axes/run.py <model> <runs> <variant,...|all> <change,...|all> [parallel]
    python scripts/structure_axes/analyze.py
"""
from __future__ import annotations

import hashlib
import json
import sys
import traceback
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from craftbench import usage  # noqa: E402
from craftbench.agents import make_agent  # noqa: E402
from craftbench.env import Environment  # noqa: E402
from craftbench.grading import run_suites  # noqa: E402
from craftbench.task import load_task  # noqa: E402

usage.QUOTA.allow_overage = True
TASK = load_task("docrender")
OUT = ROOT / ".context/runs/axes"


def slug(name: str) -> str:
    """Run folders are anonymous: the agent sees its working path, which mustn't say "flat" or "layered"."""
    return "cb_" + hashlib.md5(("docrender/" + name).encode()).hexdigest()[:8]


def run_dir(variant: str, change: str, model: str, run: int) -> Path:
    return OUT / slug(variant) / change / model / f"run_{run}"


_BASE: dict[str, int] = {}


def milestone_base(variant: str) -> int:
    if variant not in _BASE:
        r = run_suites(TASK, TASK.mutant_dirs()[variant], list(TASK.milestones))
        _BASE[variant] = sum(len(s.passed) for s in r.values())
    return _BASE[variant]


def probe(variant: str, change: str, model: str, run: int) -> dict:
    agent = make_agent(model, budget_usd=5.0)
    env = Environment(TASK, extenders=[agent], runs_dir=OUT)
    return env.maintain(agent, TASK.mutant_dirs()[variant], TASK.change(change), run_dir(variant, change, model, run),
                        milestone_base(variant))


def main():
    model, runs, which, changes = sys.argv[1], int(sys.argv[2]), sys.argv[3], sys.argv[4]
    par = int(sys.argv[5]) if len(sys.argv) > 5 else 3
    variants = list(TASK.mutant_dirs()) if which == "all" else which.split(",")
    changes = [c.id for c in TASK.changes] if changes == "all" else changes.split(",")
    for v in variants:
        milestone_base(v)
    jobs = [(v, c, r) for r in range(runs) for c in changes for v in variants]

    def go(job):
        v, c, r = job
        try:
            res = probe(v, c, model, r)
            print(f"{model} {v} {c} run_{r}: effort {res['effort']:.0f}, "
                  f"{res.get('new_tests_passed')}/{res.get('new_tests_total')} passed", flush=True)
        except usage.QuotaExceeded as e:
            print(f"{model} {v} {c} run_{r}: stopped, {e}", flush=True)
        except Exception:
            print(f"{model} {v} {c} run_{r} failed:\n{traceback.format_exc()}", flush=True)

    with ThreadPoolExecutor(par) as ex:
        list(ex.map(go, jobs))


if __name__ == "__main__":
    main()
