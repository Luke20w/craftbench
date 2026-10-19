"""Command line: tasks, check-task, run, grade, validate."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from . import validate
from .agents import ClaudeCodeAgent
from .env import Environment
from .grading import run_suite, run_suites
from .task import list_tasks, load_task


def main(argv=None):
    p = argparse.ArgumentParser(prog="craftbench")
    p.add_argument("command", choices=["tasks", "check-task", "run", "grade", "validate"])
    p.add_argument("--task", default="etl_pipeline")
    p.add_argument("--code", help="grade: the codebase to grade")
    p.add_argument("--recorded", help="validate: re-grade recorded runs instead of running the extender")
    p.add_argument("--policy-model", default="haiku", help="run: model that builds the milestones")
    p.add_argument("--extender-model", default="haiku")
    p.add_argument("--extender-budget", type=float, default=0.40, help="max USD per extender run")
    p.add_argument("--extender-runs", type=int, default=1)
    p.add_argument("--runs-dir", default="runs")
    a = p.parse_args(argv)

    if a.command == "tasks":
        for t in list_tasks():
            print(t)
        return
    task = load_task(a.task)
    extender = ClaudeCodeAgent(a.extender_model, max_budget_usd=a.extender_budget)
    env = Environment(task, extender=extender, extender_runs=a.extender_runs, runs_dir=Path(a.runs_dir))

    if a.command == "check-task":
        # The reference should pass the milestones; each change's tests should mostly fail on it.
        for k, r in run_suites(task, task.reference, list(task.milestones)).items():
            print(f"milestone {k}: {len(r.passed)}/{len(r.tests)} pass on the reference")
        for c in task.changes:
            r = run_suite(task, task.reference, c)
            print(f"change {c.id}: {len(r.passed)}/{len(r.tests)} already pass on the reference")
    elif a.command == "run":
        grade = env.run_episode(ClaudeCodeAgent(a.policy_model, max_turns=120, max_budget_usd=1.0))
        print(json.dumps(asdict(grade), indent=2))
    elif a.command == "grade":
        if not a.code:
            p.error("grade needs --code")
        grade = env.grade(Path(a.code), Path(a.runs_dir) / task.id / "graded")
        print(json.dumps(asdict(grade), indent=2))
    elif a.command == "validate":
        results = validate.recorded(env, Path(a.recorded)) if a.recorded else validate.live(env)
        print(validate.report(results, env.lam))


if __name__ == "__main__":
    main()
