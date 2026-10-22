"""CraftBench for docs: score a README by how much a frozen agent that has ONLY the README must read before it
gets real tasks right. Each goal's answer (request.json) is checked by running the real tool, at every
snapshot of the agent's workspace, the same way code changes are checked by hidden tests.

    python scripts/v_measures/readme_use.py <model,...> [runs] [parallel]
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys
import traceback
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from craftbench import usage  # noqa: E402
from craftbench.agents import make_agent, save_calls  # noqa: E402
from craftbench.effort import reading_at_snapshot  # noqa: E402
from craftbench.sandbox import LocalSandbox  # noqa: E402

usage.QUOTA.max_five_hour, usage.QUOTA.max_seven_day, usage.QUOTA.allow_overage = 1.0, 1.0, True  # Luke: extra usage OK
RUNS = ROOT / os.environ.get("CRAFTBENCH_RUNS", "runs")
LAB = RUNS / "readme_lab"
OUT = LAB / "use"
TOOL = ROOT / "tasks/etl_pipeline_xl_naive/reference/etl_pipeline.py"
FAILURE = 20_000

DATA = [
    {"id": 7, "full name": " ann lee ", "team": "a", "age": 30, "unit price": 12.5, "price_text": "12.567", "score": None},
    {"id": 42, "full name": "Bob Stone", "team": "b", "age": 17, "unit price": 8, "price_text": "3.04", "discount": 0.1},
    {"id": 3, "full name": "cy ray", "team": "a", "age": 45, "unit price": 20.25, "price_text": "100", "score": 7,
     "discount": 0.2},
    {"id": 15, "full name": "Di Moe", "team": "b", "age": 52, "unit price": 5.75, "price_text": "0.55"},
]

# goal id -> (what the user wants, a reference pipeline that does it, how to compare)
GOALS = {
    "space_column": ("Keep only the rows whose `unit price` is more than 10. The output rows must keep all their "
                     "original columns, with their original names.",
                     [{"op": "rename", "from": "unit price", "to": "up"}, {"op": "filter", "where": "up > 10"},
                      {"op": "rename", "from": "up", "to": "unit price"}], "rows"),
    "rename_two": ("Rename `team` to `group` and `age` to `years`, using a single step.",
                   [{"op": "rename", "mapping": {"team": "group", "age": "years"}}], "rows_one_step"),
    "branch_fill": ("For rows in team \"a\", set a missing or null `score` to 0. Rows in team \"b\" must come out "
                    "exactly as they went in.",
                    [{"op": "branch", "branches": [
                        {"when": "team == \"a\"", "steps": [{"op": "fill", "column": "score", "value": "0"}]},
                        {"when": "otherwise", "steps": []}]}], "rows_any_order"),
    "fill_missing": ("Give every row that has no `discount` (or a null one) a discount of 0. Keep existing discounts.",
                     [{"op": "fill", "column": "discount", "value": "0"}], "rows"),
    "round_strings": ("`price_text` holds prices as strings. Turn it into a number rounded to 1 decimal place.",
                      [{"op": "cast", "column": "price_text", "to": "float"},
                       {"op": "round", "column": "price_text", "digits": 1}], "rows"),
    "error_code": ("Find out which `error_code` the tool returns when a `filter` step's `where` expression is not "
                   "a valid expression. Write just that code into answer.txt.", "BAD_EXPR", "answer"),
    "pad_id": ("Turn `id` into a 5-character string padded with zeros on the left (7 becomes \"00007\").",
               [{"op": "pad", "column": "id", "width": 5, "fill": "0"}], "rows"),
    "per_team": ("Produce one row per team with the team, the number of rows as `n`, and the average age as "
                 "`avg_age`.",
                 [{"op": "summarize", "by": ["team"], "metrics": [{"as": "n", "fn": "count"},
                                                                   {"as": "avg_age", "fn": "avg", "column": "age"}]}],
                 "rows_any_order"),
    "clean_name": ("Clean up `full name`: remove the spaces around it and make it upper case.",
                   [{"op": "text", "columns": ["full name"], "fn": "trim"},
                    {"op": "text", "columns": ["full name"], "fn": "upper"}], "rows"),
    "split_name": ("Split `full name` (with surrounding spaces removed first) into `first` and `last` at the space. "
                   "Keep `full name`.",
                   [{"op": "text", "columns": ["full name"], "fn": "trim"},
                    {"op": "split", "column": "full name", "sep": " ", "into": ["first", "last"]}], "rows"),
}

PROMPT = """You use a command-line ETL tool, documented in README.md in this directory. Run it as `./etl` \
(e.g. `./etl --execute < request.json`). Don't read the tool's source code; work from the README and by \
running the tool.

Goal: {goal}

The input rows are in data.json. {deliverable} When it's right, stop."""
DELIVER_REQUEST = ("Write request.json: a complete request for the tool whose dataset is the rows from data.json "
                   "and whose pipeline achieves the goal.")
DELIVER_ANSWER = "Put the answer in answer.txt."


def tool(request: dict) -> dict | None:
    res = subprocess.run([sys.executable, str(TOOL), "--execute"], input=json.dumps(request), capture_output=True,
                         text=True, timeout=30)
    try:
        return json.loads(res.stdout)
    except json.JSONDecodeError:
        return None


EXPECTED = {g: (tool({"pipeline": {"steps": p}, "dataset": DATA}) if kind != "answer" else p)
            for g, (_, p, kind) in GOALS.items()}
assert all(e != "answer" and (e == "BAD_EXPR" or e.get("status") == "ok") for e in EXPECTED.values()), EXPECTED


def correct(goal: str, ws: Path) -> bool:
    _, _, kind = GOALS[goal]
    if kind == "answer":
        f = ws / "answer.txt"
        return f.exists() and f.read_text().strip().strip("`\"'") == EXPECTED[goal]
    try:
        req = json.loads((ws / "request.json").read_text())
        steps = req["pipeline"]["steps"]
    except Exception:
        return False
    out = tool({"pipeline": req["pipeline"], "dataset": DATA})  # their pipeline on the real rows
    if not out or out.get("status") != "ok":
        return False
    want, got = EXPECTED[goal]["data"], out["data"]
    if kind == "rows_any_order":
        key = lambda r: json.dumps(r, sort_keys=True)  # noqa: E731
        return sorted(map(key, got)) == sorted(map(key, want))
    if kind == "rows_one_step":
        return got == want and len(steps) == 1
    return got == want


def readmes() -> dict[str, Path]:
    out = {"v0": LAB / "v0" / "README.md"}
    for d in sorted((LAB / "lineages").glob("*")):
        out[d.name] = d / "README_7.md"
    return out


def one(readme: str, path: Path, goal: str, model: str, run: int) -> dict:
    d = OUT / hashlib.md5(readme.encode()).hexdigest()[:8] / goal / model / f"run_{run}"
    key = hashlib.md5(f"{path.read_text()}|{goal}|{model}|{PROMPT}".encode()).hexdigest()
    done = d / "result.json"
    if done.exists() and json.loads(done.read_text())["key"] == key:
        return json.loads(done.read_text())
    shutil.rmtree(d, ignore_errors=True)
    ws = LocalSandbox().create(d / "work")
    shutil.copy(path, ws / "README.md")
    (ws / "data.json").write_text(json.dumps(DATA, indent=1))
    (ws / "etl").write_text(f"#!/bin/sh\nexec {sys.executable} {TOOL} \"$@\"\n")
    (ws / "etl").chmod((ws / "etl").stat().st_mode | stat.S_IEXEC)
    text, _, kind = GOALS[goal]
    prompt = PROMPT.format(goal=text, deliverable=DELIVER_ANSWER if kind == "answer" else DELIVER_REQUEST)
    res = make_agent(model, max_turns=40, budget_usd=1.0).run(ws, prompt, d, snapshot_dir=d / "snaps")
    save_calls(res.calls, d / "calls.json")
    final = sum(not c.is_error for c in res.calls) + 1
    shutil.copytree(ws, d / "snaps" / f"{final:04d}", ignore=shutil.ignore_patterns(".git"))
    snaps = sorted((d / "snaps").glob("[0-9]*"), key=lambda p: int(p.name))
    ok = [correct(goal, s) for s in snaps]
    read = [0.0]
    for c in res.calls:
        read.append(read[-1] + c.result_chars / 4)
    start = None
    for i in reversed(range(len(snaps))):  # earliest snapshot of the final correct streak
        if not ok[i]:
            break
        start = i
    effort = max(read[-1], FAILURE) if start is None else reading_at_snapshot(read, res.calls, int(snaps[start].name))
    peeked = any(str(TOOL.parent) in json.dumps(c.input) or "etl_pipeline.py" in json.dumps(c.input) for c in res.calls)
    out = {"key": key, "readme": readme, "goal": goal, "model": model, "effort": effort, "solved": start is not None,
           "read_total": read[-1], "peeked_at_source": peeked, "tool_calls": len(res.calls), "cost_usd": res.cost_usd}
    done.write_text(json.dumps(out))
    return out


def main():
    models = sys.argv[1].split(",")
    runs = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    par = int(sys.argv[3]) if len(sys.argv) > 3 else 4
    jobs = [(r, p, g, m, k) for k in range(runs) for m in models for r, p in readmes().items() for g in GOALS]

    def go(j):
        try:
            o = one(*j)
            print(f"{o['readme']} {o['goal']} {o['model']}: effort {o['effort']:,.0f} solved={o['solved']}"
                  f"{' PEEKED' if o['peeked_at_source'] else ''}", flush=True)
        except usage.QuotaExceeded as e:
            print(f"{j[:4]} stopped: {e}", flush=True)
        except Exception:
            print(f"{j[:4]} failed:\n{traceback.format_exc()}", flush=True)

    with ThreadPoolExecutor(par) as ex:
        list(ex.map(go, jobs))


if __name__ == "__main__":
    main()
