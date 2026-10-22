"""Effort to change = how much the extender had to read before each hidden test passed for good.

  * Reading is everything the extender's tools returned to it (files, searches, command and test
    output), in tokens (chars / 4).
  * Reads of source code are measured in syntax nodes (analysis.density_weight), so compressing code,
    stripping comments or shortening names doesn't make it cheaper to read. A read is weighted by the
    workspace code it read: the file Read, the path Grep searched, or the files and directories named
    by the parts of a shell command that print files (cat, grep, sed, ...). Code is code whatever the
    file is called.
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

import os
import shlex
import statistics as st
from pathlib import Path

from .agents import ToolCall
from .analysis import PythonAnalyzer, density_weight
from .grading import Curve

REGRESSION_KEEP = 0.98
FAILURE_TOKENS = 40_000
PRELOADED = ("CLAUDE.md", "CLAUDE.local.md", "AGENTS.md", "GEMINI.md")
_PRINTS = {"cat", "head", "tail", "sed", "grep", "rg", "awk", "nl", "less", "more"}  # shell commands that print files


def _workspace_paths(args: list[str], base: Path) -> tuple[Path, ...]:
    """Files and directories of `base` that these paths name (globs expanded). The extender worked in a copy of
    `base`; workspaces are named "code"."""
    found = []
    for arg in filter(None, args):
        rel = arg.split("/code/", 1)[1] if "/code/" in arg else arg
        if not Path(rel).is_absolute():
            found += sorted(base.glob(rel)) if any(c in rel for c in "*?[") else [base / rel]
    return tuple(dict.fromkeys(p for p in found if p.exists() and p.resolve().is_relative_to(base.resolve())))


def _printed_args(command: str) -> list[str]:
    """Paths named by the parts of a shell command that print files, after any `cd` before them: e.g.
    `/x/code/etl` in `cd /x/code && grep -rn f etl`."""
    try:
        lex = shlex.shlex(command, posix=True, punctuation_chars=True)
        lex.whitespace_split = True
        tokens = list(lex)
    except ValueError:  # unbalanced quotes
        tokens = command.split()
    args, cwd, program, start = [], "", None, True
    for tok in tokens:
        if set(tok) <= set(";&|()"):
            start = True
        elif start:
            program, start = tok, False
        elif program == "cd":
            cwd = os.path.join(cwd, tok)
        elif program in _PRINTS:
            args.append(os.path.join(cwd, tok))
    return args


def read_weight(call: ToolCall, base: Path, analyzer: PythonAnalyzer) -> float:
    """Weight of one token of this tool result: the density of the code it read (the file Read, the path Grep
    searched, the paths a file-printing shell command names), or 1 if it read no code."""
    args = []
    if call.name == "Read":
        args = [call.input.get("file_path", "")]
    elif call.name == "Grep":
        args = [call.input.get("path") or "."]
    elif call.name == "Bash":
        args = _printed_args(call.input.get("command", ""))
    paths = _workspace_paths(args, base)
    return density_weight(paths, analyzer) if paths else 1.0


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
