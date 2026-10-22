"""More final-milestone siblings: extra candidates for milestone 7, built from the same milestone-6 code as
best_of_n's three, so the sibling test (does the reward pick the one that's cheapest to own?) has more to rank.

    python scripts/v_measures/more_siblings.py <seed,...> <first_cand> <last_cand>
"""
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import best_of_n as bon  # noqa: E402
from craftbench.agents import make_agent  # noqa: E402
from craftbench.env import Environment  # noqa: E402
from craftbench.sandbox import LocalSandbox  # noqa: E402

seeds = [int(s) for s in sys.argv[1].split(",")]
first, last = int(sys.argv[2]), int(sys.argv[3])
prompt7 = Environment(bon.TASK, extenders=[], runs_dir=bon.RUNS).reset("_sib_tmp").prompts[6]
builder = make_agent(bon.BUILDER, max_turns=120, budget_usd=5.0)


def build(job):
    seed, k = job
    d = bon.OUT / f"seed_{seed}"
    state = Path(json.loads((d / "m6" / "chosen.json").read_text())["code"])
    md = d / "m7"
    ws, done = md / f"cand_{k}" / "code", md / f"cand_{k}" / "built"
    if not done.exists():
        LocalSandbox().create(ws, state)
        builder.run(ws, prompt7, md / f"cand_{k}" / "build")
        done.touch()
    return f"seed {seed} m7 cand_{k} built"


with ThreadPoolExecutor(4) as ex:
    for r in ex.map(build, [(s, k) for s in seeds for k in range(first, last + 1)]):
        print(r, flush=True)
