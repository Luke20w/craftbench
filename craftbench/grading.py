"""Run hidden tests against a codebase, and grade every snapshot of an extender run per test."""

from __future__ import annotations

import fcntl
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import dataclass
from functools import cache
from pathlib import Path

from .sandbox import tree_digest
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


# Hidden tests time out per CLI call, so an overloaded machine fails tests that would pass. Every grading process
# on the machine shares this many test-suite slots (default: one per CPU).
TEST_SLOTS = int(os.environ.get("CRAFTBENCH_TEST_SLOTS", os.cpu_count() or 4))
_SLOT_DIR = Path(tempfile.gettempdir()) / "craftbench_test_slots"
SUITE_TIMEOUT_S = 900  # a backstop: hidden tests already time out per CLI call
SNAPSHOT_WORKERS = 4   # snapshots graded at once; the test slots bound how many suites really run


@contextmanager
def _test_slot():
    _SLOT_DIR.mkdir(exist_ok=True)
    while True:
        for i in range(TEST_SLOTS):
            f = open(_SLOT_DIR / f"slot_{i}", "w")
            try:
                fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                f.close()
                continue
            try:
                yield
            finally:
                fcntl.flock(f, fcntl.LOCK_UN)
                f.close()
            return
        time.sleep(0.2)


def _pytest(task: Task, code: Path, suite: Suite, *flags: str) -> str:
    entry = task.entrypoint.format(python=sys.executable, workspace=code.resolve())
    files = [str(task.tests_dir / t) for t in suite.tests]
    cmd = [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", *flags, *files, "--entrypoint", entry]
    with _test_slot():
        return subprocess.run(cmd, cwd=task.tests_dir, capture_output=True, text=True,
                              timeout=SUITE_TIMEOUT_S).stdout


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
        return Curve(tuple(raw["tests"]),
                     tuple(CurvePoint(p["call"], frozenset(p["new"]), p["reg"]) for p in raw["points"]))

    def point(path: Path) -> CurvePoint:
        new = run_suite(task, path, change).passed
        # Old tests only matter where new ones pass (effort charges a test from the start of its final
        # passing streak), so skip the big regression run everywhere else.
        reg = sum(len(r.passed) for r in run_suites(task, path, list(task.milestones)).values()) if new else 0
        return CurvePoint(int(path.name), new, reg)

    snaps = sorted(snap_root.glob("[0-9]*"), key=lambda p: int(p.name)) if snap_root.exists() else []
    # Most tool calls only read, so most snapshots repeat the one before: grade each distinct tree once.
    digests = [tree_digest(p) for p in snaps]
    first = {}
    for p, dg in zip(snaps, digests):
        first.setdefault(dg, p)
    with ThreadPoolExecutor(SNAPSHOT_WORKERS) as ex:
        graded = dict(zip(first, ex.map(point, first.values())))
    curve = Curve(collect(task, change), tuple(
        CurvePoint(int(p.name), graded[dg].new_passed, graded[dg].regression_passed) for p, dg in zip(snaps, digests)))
    cache_file.write_text(json.dumps({"tests": list(curve.tests), "points": [
        {"call": p.call, "new": sorted(p.new_passed), "reg": p.regression_passed} for p in curve.points]}))
    return curve
