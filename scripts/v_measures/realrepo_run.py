"""CraftBench's extender on real open-source changes (probes from scripts/realrepo): the extender gets the
problem statement of a real commit and the repo as it was, and effort is reading until that commit's own
tests pass (same rules as CraftBench). Used for two witnesses that don't depend on LLM reading for their answer:

  refactor pairs : the same real change on the code before vs after an expert refactoring
  module history : effort per werkzeug module vs what actually happened to that module over the next years

    python scripts/realrepo/../v_measures/realrepo_run.py <refactor_pairs|module_history> <model,...> [runs] [parallel]
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import traceback
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts/realrepo"))
from craftbench import usage  # noqa: E402
from craftbench.agents import load_calls, make_agent, save_calls  # noqa: E402
from craftbench.analysis import ANALYZERS  # noqa: E402
from craftbench.effort import change_effort  # noqa: E402
from craftbench.env import EXTENDER_PROMPT  # noqa: E402
from craftbench.grading import Curve, CurvePoint, _test_slot  # noqa: E402
import harness  # noqa: E402

usage.QUOTA.max_five_hour, usage.QUOTA.max_seven_day, usage.QUOTA.allow_overage = 1.0, 1.0, True  # Luke: extra usage OK
DATA = ROOT / ".context/realrepo"
OUT = ROOT / os.environ.get("CRAFTBENCH_RUNS", "runs") / "realrepo"
PY = ANALYZERS["python"]


def grade(manifest, probe, snap: Path, regression: bool) -> set:
    with _test_slot():
        return harness.grade(probe, snap, manifest.python(probe), regression=regression)


def one(manifest, probe, model: str, run: int) -> dict:
    d = OUT / ("p_" + hashlib.md5(probe.id.encode()).hexdigest()[:8]) / model / f"run_{run}"  # ids say before/after
    spec = getattr(probe, "spec_naive", None) or probe.spec
    prompt = EXTENDER_PROMPT.format(program=f"the {probe.repo.split('/')[-1]} Python project",
                                    run=probe.run or "python -m pytest", spec=spec)
    key = hashlib.md5(f"{probe.id}|{probe.base}|{model}|{prompt}".encode()).hexdigest()
    done = d / "result.json"
    if done.exists() and json.loads(done.read_text())["key"] == key:
        return json.loads(done.read_text())
    if not (d / "calls.json").exists() or not (d / "key").exists() or (d / "key").read_text() != key:
        shutil.rmtree(d, ignore_errors=True)
        base = harness.prepare(probe, d / "base")
        ws = d / "code"
        shutil.copytree(base, ws)
        os.system(f"cd '{ws}' && git init -q && git add -A && git -c user.name=env -c user.email=env@local commit -q -m base")
        res = make_agent(model, budget_usd=3.0).run(ws, prompt, d, snapshot_dir=d / "snaps")
        save_calls(res.calls, d / "calls.json")
        final = sum(not c.is_error for c in res.calls) + 1
        shutil.copytree(ws, d / "snaps" / f"{final:04d}", ignore=shutil.ignore_patterns(".git", "__pycache__"))
        (d / "key").write_text(key)
    calls = load_calls(d / "calls.json")
    hidden = set(probe.hidden)
    snaps = sorted((d / "snaps").glob("[0-9]*"), key=lambda p: int(p.name))
    points = []
    for s in snaps:  # hidden tests on every snapshot; the regression suite only where hidden tests pass
        new = grade(manifest, probe, s, False) & hidden
        reg = len(grade(manifest, probe, s, True) & set(probe.regression)) if new else 0
        points.append(CurvePoint(int(s.name), frozenset(new), reg))
    curve = Curve(tuple(sorted(hidden)), tuple(points))
    effort = change_effort(calls, curve, d / "base", PY, len(probe.regression))
    meta = json.loads((d / "run.json").read_text()) if (d / "run.json").exists() else {}
    out = {"key": key, "probe": probe.id, "dir": str(d), "model": model, "effort": effort,
           "solved": len(points[-1].new_passed) if points else 0, "hidden": len(hidden),
           "tool_calls": len(calls), "cost_usd": meta.get("cost_usd", 0.0)}
    done.write_text(json.dumps(out))
    return out


def main():
    which, models = sys.argv[1], sys.argv[2].split(",")
    runs = int(sys.argv[3]) if len(sys.argv) > 3 else 1
    par = int(sys.argv[4]) if len(sys.argv) > 4 else 3
    path = DATA / f"{which}.json"
    manifest = harness.Manifest.load(path)
    raw = {p["id"]: p for p in json.loads(path.read_text())["probes"]}
    for p in manifest.probes:
        p.spec_naive = raw[p.id].get("spec_naive")
    jobs = [(p, m, r) for r in range(runs) for m in models for p in manifest.probes]

    def go(j):
        p, m, r = j
        try:
            o = one(manifest, p, m, r)
            print(f"{which} {p.id} {m} run_{r}: effort {o['effort']:,.0f} solved {o['solved']}/{o['hidden']}", flush=True)
        except Exception:
            print(f"{which} {p.id} {m} run_{r} failed:\n{traceback.format_exc()}", flush=True)

    with ThreadPoolExecutor(par) as ex:
        list(ex.map(go, jobs))


if __name__ == "__main__":
    main()
