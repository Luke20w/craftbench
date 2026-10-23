"""Optimization pressure without training: at each milestone, build N continuations and keep the one the
reward likes best. If the reward incentivizes good design, the selected codebases should end up better than
plain builds, judged by witnesses that never see the reward (humans, another model family, held-out chains).

    python scripts/v_measures/best_of_n.py <seed,...> [N] [first_selected_milestone]

Selection uses the task's 4 probe changes (never the held-out ones), a Sonnet + Opus extender panel with one
run each, and the shipped reward F × E^-½. Tests that fail in every probe run of every candidate (features
that don't exist yet at this milestone, or behaviour the specs leave open) are left out of E.
"""
from __future__ import annotations

import dataclasses
import json
import os
import shutil
import sys
import traceback
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from craftbench import usage  # noqa: E402
from craftbench.agents import load_calls, make_agent  # noqa: E402
from craftbench.analysis import ANALYZERS, code_metrics  # noqa: E402
from craftbench.effort import change_effort  # noqa: E402
from craftbench.env import Environment  # noqa: E402
from craftbench.grading import Curve, CurvePoint, run_suites  # noqa: E402
from craftbench.reward import geomean  # noqa: E402
from craftbench.sandbox import LocalSandbox  # noqa: E402
from craftbench.task import load_task  # noqa: E402

usage.QUOTA.max_five_hour, usage.QUOTA.max_seven_day, usage.QUOTA.allow_overage = 1.0, 1.0, True  # experiment queues run through subscription limits
TASK = load_task("etl_pipeline_xl_naive")
PY = ANALYZERS["python"]
RUNS = ROOT / os.environ.get("CRAFTBENCH_RUNS", "runs")
OUT = RUNS / "best_of_n"
BUILDER = "claude-opus-5-5"
READERS = ["claude-sonnet-5-5", "claude-opus-5-5"]
PROBES = ["subpipelines", "case", "limits", "trace"]


def _curve(d: Path) -> Curve:
    raw = json.loads(next(d.glob("curve_*.json")).read_text())
    return Curve(tuple(raw["tests"]), tuple(CurvePoint(p["call"], frozenset(p["new"]), p["reg"]) for p in raw["points"]))


def _failed(d: Path) -> set:
    c = _curve(d)
    return set(c.tests) - (set(c.points[-1].new_passed) if c.points else set())


def score(cands: list[Path], i: int, d: Path) -> list[dict]:
    """F, E and reward for each candidate after milestone i, with a shared set of unreachable tests dropped."""
    task_i = dataclasses.replace(TASK, milestones=TASK.milestones[:i])
    out = []
    for c in cands:
        res = run_suites(task_i, c, list(task_i.milestones))
        passed = sum(len(r.passed) for r in res.values())
        out.append({"code": str(c), "F": passed / sum(len(r.tests) for r in res.values()), "passed": passed,
                    "metrics": code_metrics(c, PY)})
    jobs = [(k, ch, rd) for k in range(len(cands)) for ch in PROBES for rd in READERS]

    def probe(job):
        k, ch, rd = job
        agent = make_agent(rd, budget_usd=3.0)
        env = Environment(task_i, extenders=[agent], runs_dir=RUNS)
        run_dir = d / f"cand_{k}" / "probe" / ch / rd
        env.maintain(agent, cands[k], TASK.change(ch), run_dir, out[k]["passed"])
        return run_dir

    with ThreadPoolExecutor(6) as ex:
        dirs = dict(zip(jobs, ex.map(probe, jobs)))
    for ch in PROBES:
        drop = set.intersection(*[_failed(dirs[(k, ch, rd)]) for k in range(len(cands)) for rd in READERS])
        for k in range(len(cands)):
            eff = []
            for rd in READERS:
                rdir = dirs[(k, ch, rd)]
                cv = _curve(rdir)
                keep = tuple(t for t in cv.tests if t not in drop) or cv.tests
                eff.append(change_effort(load_calls(rdir / "calls.json"), Curve(keep, cv.points), cands[k], PY,
                                         out[k]["passed"]))
            out[k].setdefault("effort", {})[ch] = {"by_reader": dict(zip(READERS, eff)), "panel": geomean(eff),
                                                    "dropped": len(drop)}
    for o in out:
        o["E"] = geomean(v["panel"] for v in o["effort"].values())
        o["reward"] = o["F"] * o["E"] ** -0.5
    return out


def trajectory(seed: int, n: int, first: int) -> Path:
    d = OUT / f"seed_{seed}"
    builder = make_agent(BUILDER, max_turns=120, budget_usd=5.0)
    env = Environment(TASK, extenders=[], runs_dir=RUNS)
    prompts = env.reset(f"_bon_tmp_{seed}").prompts
    shutil.rmtree(RUNS / TASK.id / f"_bon_tmp_{seed}", ignore_errors=True)
    state = None
    for i, prompt in enumerate(prompts, 1):
        md = d / f"m{i}"
        chosen_file = md / "chosen.json"
        if chosen_file.exists():
            state = Path(json.loads(chosen_file.read_text())["code"])
            continue
        k_n = n if i >= first else 1

        def build(k):
            ws = md / f"cand_{k}" / "code"
            done = md / f"cand_{k}" / "built"
            if done.exists():
                return ws
            LocalSandbox().create(ws, state)
            builder.run(ws, prompt, md / f"cand_{k}" / "build")
            done.touch()
            return ws

        with ThreadPoolExecutor(k_n) as ex:
            cands = list(ex.map(build, range(k_n)))
        if k_n == 1:
            record = {"code": str(cands[0]), "selected": 0}
        else:
            scored = score(cands, i, md)
            best = max(range(k_n), key=lambda k: scored[k]["reward"])
            record = {"code": str(cands[best]), "selected": best, "candidates": scored}
        chosen_file.write_text(json.dumps(record, indent=1, default=str))
        state = Path(record["code"])
        print(f"seed {seed} m{i}: chose cand_{record['selected']}"
              + (" | " + " ".join(f"c{k}: R={c['reward'] * 100:.3f} F={c['F']:.2f} E={c['E']:,.0f} files={c['metrics']['files']} nodes={c['metrics']['nodes']:,}"
                                  for k, c in enumerate(record.get("candidates", []))) if "candidates" in record else ""),
              flush=True)
    final = d / "final"
    if not final.exists():
        shutil.copytree(state, final, ignore=shutil.ignore_patterns(".git", "__pycache__", ".pytest_cache"))
    return final


def main():
    seeds = [int(s) for s in sys.argv[1].split(",")]
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 3
    first = int(sys.argv[3]) if len(sys.argv) > 3 else 3

    def go(s):
        try:
            return f"seed {s}: final at {trajectory(s, n, first)}"
        except usage.QuotaExceeded as e:
            return f"seed {s}: stopped, {e}"
        except Exception:
            return f"seed {s} failed:\n{traceback.format_exc()}"

    with ThreadPoolExecutor(len(seeds)) as ex:
        for r in ex.map(go, seeds):
            print(r, flush=True)


if __name__ == "__main__":
    main()
