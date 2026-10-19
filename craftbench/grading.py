"""Run hidden tests against a codebase, and grade every snapshot of an extender run per test."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from functools import cache
from pathlib import Path

from .task import Suite, Task


@dataclass(frozen=True)
class SuiteResult:
    passed: frozenset[str]
    tests: tuple[str, ...]


@dataclass(frozen=True)
class CurvePoint:
    call: int                    # tool-call index after which the snapshot was taken
    new_passed: frozenset[str]   # change tests passing at this snapshot
    regression_passed: int       # milestone tests still passing at this snapshot


@dataclass(frozen=True)
class Curve:
    tests: tuple[str, ...]       # all of the change's tests
    points: tuple[CurvePoint, ...]


def _pytest(task: Task, code: Path, suite: Suite, *flags: str) -> str:
    entry = task.entrypoint.format(python=sys.executable, workspace=code.resolve())
    files = [str(task.tests_dir / t) for t in suite.tests]
    cmd = [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", *flags, *files, "--entrypoint", entry]
    return subprocess.run(cmd, cwd=task.tests_dir, capture_output=True, text=True, timeout=900).stdout


@cache
def collect(task: Task, suite: Suite) -> tuple[str, ...]:
    """Names of every hidden test in a suite."""
    return tuple(sorted(set(re.findall(r"::(\S+)$", _pytest(task, task.root, suite, "--collect-only"), re.M))))


def run_suite(task: Task, code: Path, suite: Suite) -> SuiteResult:
    passed = re.findall(r"^PASSED \S+::(\S+)", _pytest(task, code, suite, "-rA"), re.M)
    return SuiteResult(frozenset(passed), collect(task, suite))


def run_suites(task: Task, code: Path, suites: list[Suite]) -> dict[str, SuiteResult]:
    with ThreadPoolExecutor(len(suites)) as ex:
        return dict(zip([s.id for s in suites], ex.map(lambda s: run_suite(task, code, s), suites)))


def grade_snapshots(task: Task, change: Suite, snap_root: Path) -> Curve:
    """Hidden tests on every snapshot: which change tests pass, and how many old tests survive.
    Cached next to the snapshots, which never change after a run."""
    cache_file = snap_root.parent / f"curve_{change.id}.json"
    if cache_file.exists():
        raw = json.loads(cache_file.read_text())
        return Curve(tuple(raw["tests"]), tuple(CurvePoint(p["call"], frozenset(p["new"]), p["reg"]) for p in raw["points"]))

    def point(path: Path) -> CurvePoint:
        new = run_suite(task, path, change).passed
        reg = sum(len(r.passed) for r in run_suites(task, path, list(task.milestones)).values())
        return CurvePoint(int(path.name), new, reg)

    snaps = sorted(snap_root.glob("[0-9]*"), key=lambda p: int(p.name)) if snap_root.exists() else []
    with ThreadPoolExecutor(4) as ex:
        curve = Curve(collect(task, change), tuple(ex.map(point, snaps)))
    cache_file.write_text(json.dumps({"tests": list(curve.tests), "points": [
        {"call": p.call, "new": sorted(p.new_passed), "reg": p.regression_passed} for p in curve.points]}))
    return curve
