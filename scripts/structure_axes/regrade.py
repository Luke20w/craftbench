"""Regrade runs whose snapshots show existing tests failing, from their saved snapshots (no model calls).

Under heavy machine load the test runner can fail outright, which the grader records as the extender breaking
the existing tests and charges as a failed change. A real break reproduces when regraded; a load failure doesn't.

    python scripts/structure_axes/regrade.py          # list suspect runs, regrade them, report effort before -> after
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from run import OUT, TASK, milestone_base, slug  # noqa: E402

from craftbench.agents import make_agent  # noqa: E402
from craftbench.agents.base import AgentRun, load_calls  # noqa: E402
from craftbench.env import Environment  # noqa: E402

KEEP = 0.98


def suspects():
    for variant in TASK.mutant_dirs():
        for change in TASK.changes:
            for run in sorted((OUT / slug(variant) / change.id).glob("*/run_*")):
                curve = run / f"curve_{change.id}.json"
                if not (run / "result.json").exists() or not curve.exists():
                    continue
                base = milestone_base(variant)
                if any(p["new"] and p["reg"] < KEEP * base for p in json.loads(curve.read_text())["points"]):
                    yield variant, change, run


def main():
    for variant, change, run in list(suspects()):
        old = json.loads((run / "result.json").read_text())
        curve = run / f"curve_{change.id}.json"
        shutil.copy(curve, run / f"{curve.name}.before_regrade")
        curve.unlink()
        meta = json.loads((run / "run.json").read_text()) if (run / "run.json").exists() else {}
        agent_run = AgentRun(load_calls(run / "calls.json"), meta.get("cost_usd", 0.0), meta.get("stop", ""),
                             meta.get("usage", {}))
        env = Environment(TASK, extenders=[make_agent(old["extender"])], runs_dir=OUT)
        new = {**old, **env.score(agent_run, run, TASK.mutant_dirs()[variant], change, milestone_base(variant))}
        (run / "result.json").write_text(json.dumps(new))
        regs = [p["reg"] for p in json.loads(curve.read_text())["points"]]
        print(f"{variant:18} {change.id:20} {old['extender'][7:13]} {run.name}: effort {old['effort']:.0f} -> "
              f"{new['effort']:.0f}; existing tests passing per snapshot now {regs}", flush=True)


if __name__ == "__main__":
    main()
