"""Command line: tasks, check-task, grade, validate, smoke, bench, usage."""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import asdict
from pathlib import Path

from . import bench, usage, validate
from .agents import make_agent
from .env import Environment
from .grading import run_suite, run_suites
from .task import list_tasks, load_task

BUILDER_TURNS = 120  # building from a spec takes more turns than an extender's change (make_agent's default)


def main(argv=None):
    p = argparse.ArgumentParser(prog="craftbench")
    p.add_argument("command", choices=["tasks", "check-task", "grade", "validate", "smoke", "bench", "usage"])
    p.add_argument("--task", default="etl_pipeline_xl_naive", help="task id or folder (default %(default)s)")
    p.add_argument("--code", help="grade: the codebase to grade")
    p.add_argument("--recorded", help="validate: re-grade recorded runs instead of running the extender")
    p.add_argument("--builders", default="",
                   help="bench, smoke: comma-separated models that build the code (the policies being benchmarked)")
    p.add_argument("--extenders", default="claude-sonnet-5-5,claude-opus-5-5",
                   help="comma-separated models in the extender panel; mix model families where you can "
                        "(e.g. add gpt-6-astra): what's easy to change depends on the reader")
    p.add_argument("--builder-budget", type=float, default=3.0, help="max USD per milestone (Claude Code only)")
    p.add_argument("--extender-budget", type=float, default=1.0, help="max USD per extender run (Claude Code only)")
    p.add_argument("--extender-runs", type=int, default=2, help="runs per extender per change")
    p.add_argument("--runs", type=int, default=3, help="bench: builds per builder")
    p.add_argument("--parallel", type=int, default=1, help="bench: builds at once")
    p.add_argument("--runs-dir", default=os.environ.get("CRAFTBENCH_RUNS", "runs"),
                   help="where runs are kept (default $CRAFTBENCH_RUNS or ./runs)")
    p.add_argument("--max-5h", type=float, default=usage.QUOTA.max_five_hour,
                   help="guards a Claude subscription's 5-hour limit: once it is this full (default %(default)s), "
                        "wait for it to reset before starting another run")
    p.add_argument("--max-week", type=float, default=usage.QUOTA.max_seven_day,
                   help="guards a Claude subscription's weekly limit: once it is this full (default %(default)s), "
                        "start no more runs")
    a = p.parse_args(argv)
    usage.QUOTA.max_five_hour, usage.QUOTA.max_seven_day = a.max_5h, a.max_week

    if a.command == "tasks":
        for t in list_tasks():
            print(t)
        return
    if a.command == "usage":
        print(usage.summary(Path(a.runs_dir)))
        return
    task = load_task(a.task)
    extenders = [make_agent(m, budget_usd=a.extender_budget) for m in a.extenders.split(",") if m]
    builders = [make_agent(m, max_turns=BUILDER_TURNS, budget_usd=a.builder_budget) for m in a.builders.split(",") if m]
    env = Environment(task, extenders=extenders, runs_per_extender=a.extender_runs, runs_dir=Path(a.runs_dir))
    if a.command in ("smoke", "bench"):
        missing = [f"{x.name}: {why}" for x in extenders + builders if (why := x.available())]
        if missing:
            p.error("agents not ready:\n  " + "\n  ".join(missing))

    if a.command == "check-task":
        # The reference should pass the milestones; each change's tests should mostly fail on it.
        for k, r in run_suites(task, task.reference, list(task.milestones)).items():
            print(f"milestone {k}: {len(r.passed)}/{len(r.tests)} pass on the reference")
        for c in task.changes:
            r = run_suite(task, task.reference, c)
            print(f"change {c.id}: {len(r.passed)}/{len(r.tests)} already pass on the reference")
    elif a.command == "grade":
        if not a.code:
            p.error("grade needs --code")
        grade = env.grade(Path(a.code), Path(a.runs_dir) / task.id / "graded")
        print(json.dumps(asdict(grade), indent=2))
    elif a.command == "validate":
        results = validate.recorded(env, Path(a.recorded)) if a.recorded else validate.live(env)
        print(validate.report(results, env.lam))
    elif a.command == "smoke":
        for agent in {x.name: x for x in extenders + builders}.values():
            print(bench.smoke(env, agent))
    elif a.command == "bench":
        if not builders:
            p.error("bench needs --builders")
        print(bench.report(bench.run(env, builders, a.runs, a.parallel)))
        print("\n" + usage.summary(Path(a.runs_dir)))


if __name__ == "__main__":
    main()
