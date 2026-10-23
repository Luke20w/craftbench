"""Rescore every V-measures run with today's effort rules (no model calls). Writes rescored.json:
result path -> effort. Tests no run on a codebase ever passed (behaviour the specs leave open) are left out,
as in the published analysis. Tests already passing on the base are charged like any other: 720 of the runs
predate that rule and didn't record them, and treating every run alike keeps comparisons fair."""
import json, os, sys
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
os.environ["CRAFTBENCH_RUNS"] = str(ROOT / ".context/runs")
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "scripts/v_measures"))
import run  # noqa: E402
from craftbench.agents import load_calls  # noqa: E402
from craftbench.analysis import ANALYZERS  # noqa: E402
from craftbench.effort import change_effort  # noqa: E402
from craftbench.grading import Curve, CurvePoint  # noqa: E402

PY = ANALYZERS["python"]
OUT = run.RUNS / "precision_rescored.json"

def curve(d, cid):
    raw = json.loads((d / f"curve_{cid}.json").read_text())
    return Curve(tuple(raw["tests"]), tuple(CurvePoint(p["call"], frozenset(p["new"]), p["reg"]) for p in raw["points"]))

jobs = []  # (result dir, base code, change id, regression base, group key for unreachable tests)
for name, code in run.codebases().items():
    root = run.OUT / run.slug(name)
    mb = root / "milestones_passed.json"
    for kind in ("probe", "bigprobe"):
        for d in root.glob(f"{kind}/*/*/run_*"):
            if (d / "result.json").exists() and mb.exists():
                jobs.append((d, code, d.parts[-3], json.loads(mb.read_text())["passed"], (name, d.parts[-3])))
    for chain in root.glob("chain/*/run_*"):
        base = code
        for d in sorted(p for p in chain.glob("*_h*") if p.is_dir()):
            rb = Path(str(d) + ".regression_base.json")
            if (d / "result.json").exists() and rb.exists():
                jobs.append((d, base, d.name.split("_", 1)[1], json.loads(rb.read_text())["n"], (name, d.name)))
            base = d / "code"
bon = run.RUNS / "best_of_n"
for d in bon.glob("seed_*/m7/cand_*/probe/*/*"):
    cand = d.parents[2]
    name = f"bonm7_s{cand.parts[-3].split('_')[1]}_c{cand.name.split('_')[1]}"
    n = run.milestone_base(name, cand / "code")
    if (d / "result.json").exists():
        jobs.append((d, cand / "code", d.parts[-2], n, (name, d.parts[-2])))

reached = defaultdict(set)
for d, _, cid, _, g in jobs:
    for p in curve(d, cid).points:
        reached[g] |= p.new_passed

def score(job):
    d, base, cid, reg, g = job
    c = curve(d, cid)
    res = json.loads((d / "result.json").read_text())
    skip = frozenset(t for t in c.tests if t not in reached[g])
    return str(d), {"effort": change_effort(load_calls(d / "calls.json"), c, base, PY, reg, skip), "old": res["effort"]}

with ThreadPoolExecutor(6) as ex:
    out = dict(ex.map(score, jobs))
OUT.write_text(json.dumps(out))
print(len(out), "rescored")
