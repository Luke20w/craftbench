"""Build the naive-spec XL task with several builders (build phase only; grading is done separately)."""
import os
import sys
import traceback
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from craftbench import usage  # noqa: E402
from craftbench.agents import make_agent  # noqa: E402
from craftbench.env import Environment  # noqa: E402
from craftbench.task import load_task  # noqa: E402

usage.QUOTA.max_five_hour, usage.QUOTA.max_seven_day, usage.QUOTA.allow_overage = 1.0, 1.0, True  # experiment queues run through subscription limits
RUNS = ROOT / os.environ.get("CRAFTBENCH_RUNS", "runs")
env = Environment(load_task("etl_pipeline_xl_naive"), extenders=[], runs_dir=RUNS)
JOBS = [(m, k) for m in sys.argv[1].split(",") for k in range(int(sys.argv[2]))]


def build(job):
    model, k = job
    name = f"bench/{model}/s{k}"
    d = RUNS / env.task.id / name
    if (d / "build" / "done").exists():
        return f"{name}: already built"
    try:
        agent = make_agent(model, max_turns=120, budget_usd=5.0)
        if (d / "build" / "code").exists():  # resume after the last finished milestone
            ep = env.reset(name + "__tmp")
            import shutil
            shutil.rmtree(ep.dir, ignore_errors=True)
            ep.dir, ep.workspace = d, d / "build" / "code"
        else:
            ep = env.reset(name)
        for i, prompt in enumerate(ep.prompts, 1):
            if (ep.dir / "build" / f"milestone_{i}" / "run.json").exists():
                continue
            agent.run(ep.workspace, prompt, ep.dir / "build" / f"milestone_{i}")
            print(f"{name}: milestone {i} done", flush=True)
        (ep.dir / "build" / "done").touch()
        return f"{name}: built"
    except Exception:
        return f"{name} failed:\n{traceback.format_exc()}"


with ThreadPoolExecutor(int(sys.argv[3]) if len(sys.argv) > 3 else 2) as ex:
    for r in ex.map(build, JOBS):
        print(r, flush=True)
