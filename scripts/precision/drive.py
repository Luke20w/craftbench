"""A same-policy group: Sonnet builds the XL task from scratch 6 times; Sonnet probes and Sonnet chains on each.
Stays inside the subscription: stops on extra usage instead of running through it."""
import os, shutil, sys, traceback
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
os.environ["CRAFTBENCH_RUNS"] = str(ROOT / ".context/runs")
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "scripts/v_measures"))
import run  # noqa: E402
from craftbench import usage  # noqa: E402
from craftbench.agents import make_agent  # noqa: E402
from craftbench.env import Environment  # noqa: E402

usage.QUOTA.max_five_hour, usage.QUOTA.max_seven_day, usage.QUOTA.allow_overage = 0.85, 0.9, False
SONNET = "claude-sonnet-5-5"
N = int(sys.argv[1]) if len(sys.argv) > 1 else 6
env = Environment(run.TASK, extenders=[], runs_dir=run.RUNS)

def build(k):
    name = f"bench/{SONNET}/s{k}"
    d = run.RUNS / run.TASK.id / name
    if (d / "build" / "done").exists():
        return f"{name}: already built"
    try:
        agent = make_agent(SONNET, max_turns=120, budget_usd=5.0)
        shutil.rmtree(d, ignore_errors=True)
        ep = env.reset(name)
        for i, prompt in enumerate(ep.prompts, 1):
            agent.run(ep.workspace, prompt, ep.dir / "build" / f"milestone_{i}")
        (ep.dir / "build" / "done").touch()
        return f"{name}: built"
    except Exception:
        return f"{name} failed:\n{traceback.format_exc()}"

def job(kind, name, r):
    try:
        cb = run.codebases()
        res = run.KINDS[kind](name, cb[name], SONNET, r)
        return f"{kind} {name} run_{r}: {res}"
    except usage.QuotaExceeded as e:
        return f"{kind} {name} run_{r}: stopped, {e}"
    except Exception:
        return f"{kind} {name} run_{r} failed:\n{traceback.format_exc()}"

with ThreadPoolExecutor(4) as ex:
    for line in ex.map(build, range(N)):
        print(line, flush=True)
names = [f"sonnet-5-5_s{k}" for k in range(N) if f"sonnet-5-5_s{k}" in run.codebases()]
jobs = [(kind, n, r) for kind in ("probe", "chain") for r in range(2) for n in names]
with ThreadPoolExecutor(4) as ex:
    for line in ex.map(lambda j: job(*j), jobs):
        print(line, flush=True)
print("DRIVE DONE", flush=True)
