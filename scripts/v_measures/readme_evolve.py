"""Grow a README through naive user complaints, one model lineage at a time, to see who patches special
cases and who restructures. The results go to a blind human ranking (and later to downstream-agent scoring).

    python scripts/v_measures/readme_evolve.py base            # write README v0 (Sonnet)
    python scripts/v_measures/readme_evolve.py evolve <model,...>
"""
from __future__ import annotations

import os
import shutil
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from craftbench import usage  # noqa: E402
from craftbench.agents import make_agent  # noqa: E402
from craftbench.sandbox import LocalSandbox  # noqa: E402

usage.QUOTA.max_five_hour, usage.QUOTA.max_seven_day, usage.QUOTA.allow_overage = 1.0, 1.0, True  # experiment queues run through subscription limits
RUNS = ROOT / os.environ.get("CRAFTBENCH_RUNS", "runs")
OUT = RUNS / "readme_lab"
CODE = ROOT / "tasks/etl_pipeline_xl_naive/reference"

BASE_PROMPT = """This directory is a CLI ETL tool (run it as `python etl_pipeline.py`, JSON request on stdin, \
JSON response on stdout). It has no README yet. Write README.md for the people who use the tool: what it does, \
how to run it, and how to use it. Read the code as much as you need. Only create README.md; don't change code."""

ISSUE_PROMPT = """This directory is a CLI ETL tool with a README.md for its users. A user report about the \
docs came in (below). Update README.md to address it. Only change README.md.

User report:
{issue}"""

ISSUES = [
    "Someone tried to filter on a column whose name has a space in it (`unit price`) and couldn't work out how "
    "to refer to it in the `where` expression.",
    "A user passed both `from`/`to` and `mapping` to `rename` and was confused by what happened.",
    "People keep asking whether steps like `fill` and `cast` work inside `branch` branches.",
    "A user got `MISSING_COLUMN` from `fill` on rows that didn't have the column yet and assumed it was a bug.",
    "Someone wanted to know why `\"price\": \"12\"` (a string) didn't work with `round`.",
    "A user asked what all the possible `error_code` values are and when each one happens.",
    "Someone couldn't tell which fields are optional for `pad`, and what the defaults are.",
]


def run(model: str, ws: Path, prompt: str, log: Path):
    if (log / "run.json").exists():
        return
    make_agent(model, max_turns=40, budget_usd=1.5).run(ws, prompt, log)


def base():
    d = OUT / "v0"
    if (d / "README.md").exists():
        return
    ws = LocalSandbox().create(d / "work", CODE)
    run("claude-sonnet-5-5", ws, BASE_PROMPT, d / "log")
    shutil.copy(ws / "README.md", d / "README.md")


def evolve(model: str):
    d = OUT / "lineages" / model
    ws = d / "work"
    if not ws.exists():
        LocalSandbox().create(ws, CODE)
        shutil.copy(OUT / "v0" / "README.md", ws / "README.md")
    for k, issue in enumerate(ISSUES, 1):
        if (d / f"README_{k}.md").exists():
            continue
        run(model, ws, ISSUE_PROMPT.format(issue=issue), d / f"log_{k}")
        shutil.copy(ws / "README.md", d / f"README_{k}.md")
        print(f"{model}: issue {k} done", flush=True)


if __name__ == "__main__":
    if sys.argv[1] == "base":
        base()
    else:
        models = sys.argv[2].split(",")
        with ThreadPoolExecutor(len(models)) as ex:
            list(ex.map(evolve, models))
