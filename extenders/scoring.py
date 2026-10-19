"""nodes_read_per_test: how much an extender had to read before each hidden test started passing.

For every hidden test of the change request: the extender's cumulative reading at the snapshot from
which that test passes and keeps passing to the end of the run (with >= stable_regression of the old
tests still passing). Tests that never get there are charged `fail_charge`. Average over tests.
Lower = cheaper to change.

Reading is the size of every tool result the extender took in (chars / 4 ~ tokens). Code reads are
charged in syntax-tree nodes or tokens, whichever is larger (relative to a reference codebase's node
density), so packing code densely never makes it cheaper to read.
"""

from __future__ import annotations

import statistics as st
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .events import READ, SEARCH, RunRecord, ToolCall
from .nodes import density
from .runner import tree_digest


@dataclass(frozen=True)
class Grade:
    new_passing: frozenset[str]       # ids of the change request's hidden tests that pass
    regression_passing: int           # how many of the old tests still pass


GradeFn = Callable[[Path], Grade]


def read_weight(call: ToolCall, base_dir: Path, workdir: Path, ref_density: float) -> float:
    """>= 1. Code reads are scaled up by how much denser (nodes per char) the code read is than the
    reference; everything else (test output, prose, non-Python code) is charged plain tokens.
    Density is taken from the base codebase (what the policy wrote), not the extender's edits."""
    if call.kind not in (READ, SEARCH) or ref_density <= 0:
        return 1.0
    d = density(str(base_dir))
    if call.kind == READ and call.path:
        p = Path(call.path)
        if p.suffix != ".py":
            return 1.0
        rel = p.relative_to(workdir) if p.is_absolute() and p.is_relative_to(workdir) else Path(p.name) if p.is_absolute() else p
        if (base_dir / rel).is_file():
            d = density(str(base_dir / rel))
    return max(1.0, d / ref_density) if d else 1.0


def cumulative_reading(rec: RunRecord, base_dir: Path, ref_density: float) -> list[float]:
    """cum[i] = node-weighted tokens read after the first i tool calls."""
    cum = [0.0]
    for c in rec.calls:
        cum.append(cum[-1] + c.output_chars / 4 * read_weight(c, base_dir, rec.workdir, ref_density))
    return cum


class CachedGrader:
    """Grades each distinct tree once (runs often revisit identical states)."""

    def __init__(self, grade: GradeFn):
        self.grade, self.cache = grade, {}

    def __call__(self, d: Path) -> Grade:
        key = tree_digest(d)
        if key not in self.cache:
            self.cache[key] = self.grade(d)
        return self.cache[key]


def nodes_read_per_test(rec: RunRecord, grade: GradeFn, tests: list[str], regression_base: int,
                        base_dir: Path, ref_density: float, fail_charge: float | None = None,
                        stable_regression: float = 0.98) -> dict:
    """Score one run. `fail_charge` None = charge never-passing tests the run's own full reading
    (rewards an extender that gives up early; prefer a ceiling such as 2x the group median)."""
    cum = cumulative_reading(rec, base_dir, ref_density)
    snaps = sorted(rec.snapshots, key=lambda s: s.after_calls)
    grades = [grade(s.dir) for s in snaps]
    ok = [g.regression_passing >= stable_regression * regression_base for g in grades]
    charge = cum[-1] if fail_charge is None else fail_charge
    per, reached = [], 0
    for t in tests:
        start = None
        for i in range(len(snaps) - 1, -1, -1):
            if t in grades[i].new_passing and ok[i]:
                start = i
            else:
                break
        if start is None:
            per.append(charge)
        else:
            reached += 1
            per.append(cum[min(snaps[start].after_calls, len(cum) - 1)])
    final = grades[-1] if grades else Grade(frozenset(), 0)
    return {"nodes_read_per_test": st.mean(per) if per else charge, "per_test": dict(zip(tests, per)),
            "tests_reached": reached, "tests_total": len(tests), "total_reading": cum[-1],
            "final_new_passing": len(final.new_passing & set(tests)), "final_regression": final.regression_passing}
