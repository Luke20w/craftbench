"""Which measure of change cost (V) best predicts what a codebase really costs to own?

Candidates, all measured on the starting code with the task's 4 probe changes:
  probe  : frozen extender implements each probe change on its own copy; reading until tests pass (CraftBench)
  plan   : frozen extender only works out a plan for each probe change (no edits, no tests); total reading
  judge  : model sees the whole codebase + the probe changes, estimates lines it would need to read
  static : free metrics (free_methods.py)
Ground truth:
  chain  : a maintainer applies the 4 held-out changes in sequence, each on the previous result; reading
           until each step's tests pass, with milestone + earlier held-out tests as the regression gate.

    python scripts/v_measures/run.py <probe|plan|judge|chain> <model> <runs> <codebase,...|all> [parallel]
    python scripts/v_measures/analyze.py      # after the runs; drive.sh runs the whole experiment
"""
from __future__ import annotations

import dataclasses
import os
import hashlib
import json
import re
import sys
import traceback
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from craftbench import usage  # noqa: E402
from craftbench.agents import make_agent  # noqa: E402
from craftbench.analysis import ANALYZERS, source_files  # noqa: E402
from craftbench.effort import preloaded_tokens, read_weight  # noqa: E402
from craftbench.env import Environment  # noqa: E402
from craftbench.grading import run_suites  # noqa: E402
from craftbench.sandbox import LocalSandbox, tree_digest  # noqa: E402
from craftbench.task import load_task  # noqa: E402

usage.QUOTA.max_five_hour, usage.QUOTA.max_seven_day, usage.QUOTA.allow_overage = 1.0, 1.0, True  # experiment queues run through subscription limits
TASK = load_task("etl_pipeline_xl_naive")
PY = ANALYZERS["python"]
RUNS = ROOT / os.environ.get("CRAFTBENCH_RUNS", "runs")  # the results in docs were run with .context/runs
OUT = RUNS / "exp_v"
PROBES = ["subpipelines", "case", "limits", "trace"]
BIG = ["explain", "column_types", "ignore_case_columns"]  # bigger probes (missing_as_null left out: too local)


def codebases() -> dict[str, Path]:
    cb = {"reference": TASK.reference}
    cb.update(TASK.mutant_dirs())
    for d in sorted((RUNS / TASK.id / "bench").glob("*/s*")):
        if (d / "build" / "done").exists():
            cb[f"{d.parent.name.replace('claude-', '')}_{d.name}"] = d / "build" / "code"
    for d in sorted((TASK.root / "exploits").glob("*/")):  # hand-built reward exploits; never part of "all"
        if (d / "etl_pipeline.py").exists():
            cb[f"x_{d.name}"] = d
    for d in sorted((RUNS / "best_of_n").glob("seed_*/final")):  # Opus builds selected by the reward each milestone
        cb[f"bon_s{d.parent.name.split('_')[1]}"] = d
    for d in sorted((RUNS / "best_of_n").glob("seed_*/m7/cand_*/code")):  # the final milestone's siblings
        seed, cand = d.parents[2].name.split("_")[1], d.parent.name.split("_")[1]
        cb[f"bonm7_s{seed}_c{cand}"] = d
    for d in sorted((RUNS / TASK.id / "redteam").glob("s*")):  # builders told how they're scored
        if (d / "build" / "done").exists():
            cb[f"redteam_{d.name}"] = d / "build" / "code"
    return cb


def slug(name: str) -> str:
    """Run folders are anonymous: the agent sees its working path, which mustn't say "golfed" or "dead_code"."""
    return "cb_" + hashlib.md5(name.encode()).hexdigest()[:8]


def passed_count(task, code: Path) -> int:
    return sum(len(r.passed) for r in run_suites(task, code, list(task.milestones)).values())


def milestone_base(name: str, code: Path) -> int:
    f = OUT / slug(name) / "milestones_passed.json"
    key = tree_digest(code)
    if f.exists() and json.loads(f.read_text())["key"] == key:
        return json.loads(f.read_text())["passed"]
    n = passed_count(TASK, code)
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps({"key": key, "passed": n,
                             "total": sum(len(r.tests) for r in run_suites(TASK, code, list(TASK.milestones)).values())}))
    return n


# ------------------------------------------------------------------ candidates
def probe(name, code, model, run, changes=PROBES, kind="probe"):
    """CraftBench as it is: the extender implements each probe change on a private copy."""
    agent = make_agent(model, budget_usd=5.0 if kind == "bigprobe" else 3.0)
    env = Environment(TASK, extenders=[agent], runs_dir=RUNS)
    base = milestone_base(name, code)
    out = {}
    for c in changes:
        r = env.maintain(agent, code, TASK.change(c), OUT / slug(name) / kind / c / model / f"run_{run}", base)
        out[c] = r["effort"]
    return out


def bigprobe(name, code, model, run):
    """The same, with the bigger probe changes."""
    return probe(name, code, model, run, BIG, "bigprobe")


PLAN_PROMPT = """You are maintaining the existing codebase in the current directory: {program}. It is run as `{run}`.

A new requirement has arrived (below). Do not change any files. Work out exactly what would have to change to \
implement it: which files and functions, and what each change would be. When you're confident the plan is \
complete and correct, write it as your final answer and stop.

{spec}
"""


def plan(name, code, model, run):
    """Cheaper probe: the extender only plans each change. Effort = everything it read."""
    agent = make_agent(model, budget_usd=2.0)
    out = {}
    for c in PROBES:
        spec = TASK.change(c).spec
        d = OUT / slug(name) / "plan" / c / model / f"run_{run}"
        key = hashlib.md5(f"{tree_digest(code)}|{model}|{spec}|{PLAN_PROMPT}".encode()).hexdigest()
        done = d / "result.json"
        if done.exists() and json.loads(done.read_text())["key"] == key:
            out[c] = json.loads(done.read_text())["effort"]
            continue
        ws = LocalSandbox().create(d / "code", code)
        prompt = PLAN_PROMPT.format(program=TASK.program, run=TASK.run_hint.format(python=sys.executable), spec=spec)
        res = agent.run(ws, prompt, d)
        effort = preloaded_tokens(code) + sum(k.result_chars / 4 * read_weight(k, code, PY) for k in res.calls)
        edited = tree_digest(ws) != tree_digest(code)
        done.write_text(json.dumps({"key": key, "effort": effort, "edited": edited, "cost_usd": res.cost_usd}))
        out[c] = effort
    return out


JUDGE_PROMPT = """Below is a complete Python codebase ({program}), followed by {n} change requests that will \
arrive next. For each change request, estimate how many lines of this codebase an engineer who has never seen \
it would need to read to implement the change correctly without breaking anything. Judge from the code as it \
is: how easy it is to find the right places, understand them, and change them safely.

Reply with only a JSON object mapping each change id to an integer, e.g. {{"a": 120, "b": 300}}. No other text.

=== CODEBASE ===
{code}

=== CHANGE REQUESTS ===
{changes}
"""


def judge(name, code, model, run):
    agent = make_agent(model, max_turns=2, budget_usd=1.0)
    d = OUT / slug(name) / "judge" / model / f"run_{run}"
    dump = "\n\n".join(f"--- {f.relative_to(code)} ---\n{f.read_text()}" for f in source_files(code, PY))
    changes = "\n\n".join(f"--- change id: {c} ---\n{TASK.change(c).spec}" for c in PROBES)
    prompt = JUDGE_PROMPT.format(program=TASK.program, n=len(PROBES), code=dump, changes=changes)
    key = hashlib.md5(f"{prompt}|{model}".encode()).hexdigest()
    done = d / "result.json"
    if done.exists() and json.loads(done.read_text())["key"] == key:
        return json.loads(done.read_text())["estimates"]
    ws = LocalSandbox().create(d / "empty")
    agent.run(ws, prompt, d)
    text = ""
    for line in (d / "transcript.jsonl").read_text().splitlines():
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            continue
        if ev.get("type") == "result":
            text = ev.get("result") or ""
    est = json.loads(re.search(r"\{.*\}", text, re.S).group(0))
    done.write_text(json.dumps({"key": key, "estimates": est}))
    return est


# ------------------------------------------------------------------ ground truth
def chain(name, code, model, run):
    """The maintainer applies the held-out changes in order, each on its own previous result."""
    agent = make_agent(model, budget_usd=4.0)
    base, out = code, {}
    for k, h in enumerate(TASK.held_out):
        task_k = dataclasses.replace(TASK, milestones=TASK.milestones + TASK.held_out[:k])
        env = Environment(task_k, extenders=[agent], runs_dir=RUNS)
        d = OUT / slug(name) / "chain" / model / f"run_{run}" / f"{k + 1}_{h.id}"
        r = env.maintain(agent, base, h, d, regression_base(task_k, base, d))
        out[h.id] = r["effort"]
        out[h.id + "_passed"] = f"{r['new_tests_passed']}/{r['new_tests_total']}"
        base = d / "code"
    return out


def regression_base(task_k, base: Path, d: Path) -> int:
    """Milestone + earlier held-out tests the step's starting code passes. Kept next to the run folder,
    which maintain() wipes when it starts a fresh run."""
    f = d.parent / f"{d.name}.regression_base.json"
    key = tree_digest(base)
    if f.exists() and json.loads(f.read_text())["key"] == key:
        return json.loads(f.read_text())["n"]
    n = passed_count(task_k, base)
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps({"key": key, "n": n}))
    return n


KINDS = {"probe": probe, "bigprobe": bigprobe, "plan": plan, "judge": judge, "chain": chain}


def main():
    kind, model, runs, which = sys.argv[1], sys.argv[2], int(sys.argv[3]), sys.argv[4]
    par = int(sys.argv[5]) if len(sys.argv) > 5 else 3
    cb = codebases()
    names = [n for n in cb if not n.startswith(("x_", "bon"))] if which == "all" else which.split(",")
    jobs = [(n, r) for r in range(runs) for n in names]

    def go(job):
        n, r = job
        try:
            res = KINDS[kind](n, cb[n], model, r)
            print(f"{kind} {model} {n} run_{r}: {json.dumps({k: (round(v) if isinstance(v, float) else v) for k, v in res.items()})}", flush=True)
        except usage.QuotaExceeded as e:
            print(f"{kind} {model} {n} run_{r}: stopped, {e}", flush=True)
        except Exception:
            print(f"{kind} {model} {n} run_{r} failed:\n{traceback.format_exc()}", flush=True)

    with ThreadPoolExecutor(par) as ex:
        list(ex.map(go, jobs))


if __name__ == "__main__":
    main()
