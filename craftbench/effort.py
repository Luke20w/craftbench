"""Effort to change = how much the extender had to read before each hidden test passed for good.

  * Reading is everything the extender's tools returned to it (files, searches, command and test
    output), in tokens (chars / 4).
  * Reads of source code (Read, Grep/Glob, and shell commands that print source files) are measured
    in syntax nodes (analysis.density_weight), so compressing code, stripping comments or shortening
    names doesn't make it cheaper to read. A shell command that names files is weighted by those files;
    one that doesn't, by the whole codebase.
  * Reading never costs less than its tokens: prose, docstrings and padding can't dilute the weight of
    the code around them, or make anything free to read.
  * Tests that already pass on the untouched code aren't charged at all: the extender didn't make them
    pass. But a change whose tests ALL pass already is charged as a failure: hidden changes are features
    nobody has asked for yet, so code that already contains one has learned the change set or built
    speculatively, and neither should pay.
  * Each hidden test of the change is charged the reading done by the snapshot from which it passes
    all the way to the end, with >= 98% of the old tests still passing. Snapshots are numbered by
    successful tool calls (hooks don't fire for failed ones), so they are mapped back to transcript
    positions before reading is looked up.
  * Tests that never get there are charged max(all reading in the run, 40k tokens), so failing or
    giving up early is always expensive.
  * Instruction files the extender's harness loads into its context by itself (CLAUDE.md,
    AGENTS.md, GEMINI.md) are charged as read before the first tool call; otherwise the policy could hand the
    extender free reading.
  * Effort = the average over the change's tests.
"""

from __future__ import annotations

import re
import statistics as st
from pathlib import Path

from .agents import ToolCall
from .analysis import PythonAnalyzer, density_weight
from .grading import Curve

REGRESSION_KEEP = 0.98
FAILURE_TOKENS = 40_000
MIN_WEIGHT = 1.0  # a token read always costs at least one token
PRELOADED = ("CLAUDE.md", "CLAUDE.local.md", "AGENTS.md", "GEMINI.md")
# A shell command reads code when any of its parts (e.g. after `cd <dir> &&`) prints a source file.
_READS_CODE = re.compile(r"(?:^|[;&|\n])\s*(cat|head|tail|sed\s+-n|grep|rg|awk|nl|less|more)\b[^;&|\n]*\.py\b")
_PY_PATH = re.compile(r"[\w./*\-\[\]]+\.py\b")


def _named_files(command: str, base: Path) -> tuple[Path, ...]:
    """Source files of `base` that a shell command names (globs expanded), e.g. `cat etl/ops/*.py`."""
    found = []
    for tok in _PY_PATH.findall(command):
        rel = tok.split("/code/", 1)[1] if "/code/" in tok else tok.lstrip("./")
        found += [p for p in sorted(base.glob(rel)) if p.is_file()] if any(c in rel for c in "*?[") else \
            [base / rel] if (base / rel).is_file() else []
    return tuple(dict.fromkeys(found))


def read_weight(call: ToolCall, base: Path, analyzer: PythonAnalyzer) -> float:
    """Weight of one token of this tool result: the density of the code read, at least MIN_WEIGHT."""
    weight = 1.0
    if call.name == "Read":
        path = str(call.input.get("file_path", ""))
        if path.endswith(analyzer.suffixes):
            # The extender worked in a copy of `base`; map its path back. Workspaces are named "code".
            rel = path.split("/code/", 1)[1] if "/code/" in path else Path(path).name
            weight = density_weight(base / rel if (base / rel).exists() else base, analyzer)
    elif call.name in ("Grep", "Glob"):
        weight = density_weight(base, analyzer)
    elif call.name == "Bash" and _READS_CODE.search(command := call.input.get("command", "")):
        weight = density_weight(_named_files(command, base) or base, analyzer)
    return max(weight, MIN_WEIGHT)


def preloaded_tokens(base: Path) -> float:
    """Tokens of instruction files anywhere in the codebase that the harness loads unasked."""
    return sum(len(p.read_text(errors="replace")) / 4 for name in PRELOADED for p in base.rglob(name)
               if p.is_file() and ".git" not in p.parts)


def reading_at_snapshot(read: list[float], calls: list[ToolCall], snapshot: int) -> float:
    """Reading done by snapshot `snapshot`, which was taken after the snapshot-th *successful* tool
    call. read[k] is the reading after the first k calls of the transcript."""
    successful = [i for i, c in enumerate(calls) if not c.is_error]
    if snapshot > len(successful):  # the final snapshot, taken after the run ended
        return read[-1]
    if snapshot <= 0 or not successful:
        return read[0]
    return read[successful[min(snapshot, len(successful)) - 1] + 1]


def change_effort(calls: list[ToolCall], curve: Curve, base: Path, analyzer: PythonAnalyzer,
                  regression_base: int, already_passing: frozenset[str] = frozenset()) -> float:
    """Effort for one change. `base` is the code before the change; `regression_base` is how many
    milestone tests it passed; `already_passing` are the change's tests that pass on `base` untouched,
    which aren't charged (unless that's all of them: then the change costs a failure)."""
    read = [preloaded_tokens(base)]  # read[k] = reading done after the first k tool calls
    for c in calls:
        read.append(read[-1] + c.result_chars / 4 * read_weight(c, base, analyzer))
    failed = max(read[-1], FAILURE_TOKENS)
    intact = [p.regression_passed >= REGRESSION_KEEP * regression_base for p in curve.points]

    def charge(test: str) -> float:
        start = None
        for i in reversed(range(len(curve.points))):  # earliest snapshot of the final passing streak
            if test not in curve.points[i].new_passed or not intact[i]:
                break
            start = i
        return failed if start is None else reading_at_snapshot(read, calls, curve.points[start].call)

    tests = [t for t in curve.tests if t not in already_passing]
    return st.mean(charge(t) for t in tests) if tests else max(failed, FAILURE_TOKENS)
