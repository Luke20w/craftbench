"""Load every finished V-measures run as (codebase, kind, change, model, run) -> effort."""
import json, math, os, sys
from collections import defaultdict
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
os.environ["CRAFTBENCH_RUNS"] = str(ROOT / ".context/runs")
sys.path.insert(0, str(ROOT / "scripts/v_measures"))
import run  # noqa: E402

RESCORED = ROOT / ".context/runs/precision_rescored.json"


_rescored = json.loads(RESCORED.read_text()) if RESCORED.exists() else {}


def effort(res):
    """Today's effort for a run (rescore.py), or the one stored when it ran."""
    hit = _rescored.get(str(res.parent))
    return hit["effort"] if hit else json.loads(res.read_text())["effort"]


def load():
    rows = []
    for name in run.codebases():
        d = run.OUT / run.slug(name)
        for kind in ("probe", "bigprobe"):
            for res in d.glob(f"{kind}/*/*/run_*/result.json"):
                r = json.loads(res.read_text())
                rows.append(dict(cb=name, kind=kind, change=res.parts[-4], model=res.parts[-3],
                                 run=int(res.parts[-2][4:]), effort=effort(res),
                                 passed=r.get("new_tests_passed"), total=r.get("new_tests_total")))
        for chain in d.glob("chain/*/run_*"):
            steps = sorted(chain.glob("*_h*/result.json"))
            if len(steps) == 4:
                e = [effort(s) for s in steps]
                rows.append(dict(cb=name, kind="chain", change="all", model=chain.parts[-2], run=int(chain.name[4:]),
                                 effort=math.exp(sum(map(math.log, e)) / 4), steps=e))
    bon = run.RUNS / "best_of_n"
    for res in bon.glob("seed_*/m7/cand_*/probe/*/*/result.json"):
        seed, cand = res.parts[-7].split("_")[1], res.parts[-5].split("_")[1]
        r = json.loads(res.read_text())
        rows.append(dict(cb=f"bonm7_s{seed}_c{cand}", kind="probe", change=res.parts[-3], model=res.parts[-2],
                         run=0, effort=effort(res), passed=r.get("new_tests_passed"), total=r.get("new_tests_total")))
    return rows
