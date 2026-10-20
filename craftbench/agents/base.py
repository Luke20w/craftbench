"""What every agent shares: the record of a run, and running a coding-agent CLI as a subprocess.

Effort only needs the list of tool calls and snapshots of the workspace, so any agent that reports
those can be plugged in. A CLI agent supplies a command and a transcript parser; `CliAgent.run` does
the rest. Snapshots come from a hook after every tool call where the CLI has one (Claude Code), or
from polling the workspace for changes. Either way snapshot_dir/<n> is the workspace after n
successful tool calls (hooks don't fire for failed ones; effort.reading_at_snapshot maps n back).
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import threading
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Protocol

from ..sandbox import IGNORE, tree_digest
from ..usage import QUOTA

POLL_S = 0.5


@dataclass(frozen=True)
class ToolCall:
    name: str             # Claude Code's tool names (Read, Grep, Glob, Bash, Edit); other CLIs map onto them
    input: dict           # tool arguments
    result_chars: int     # size of what the tool returned to the agent
    is_error: bool = False  # the tool call failed (snapshot hooks don't fire for these)


@dataclass
class AgentRun:
    calls: list[ToolCall]
    cost_usd: float = 0.0
    stop: str = ""
    usage: dict = field(default_factory=dict)  # token counts, as the agent reports them
    quota: dict = field(default_factory=dict)  # subscription limits, where the CLI reports them


class Agent(Protocol):
    name: str

    def run(self, workspace: Path, prompt: str, log_dir: Path, snapshot_dir: Path | None = None) -> AgentRun:
        """Work on `workspace` until done. If `snapshot_dir` is given, snapshot the workspace into
        snapshot_dir/<n> whenever it changes, n = successful tool calls so far."""


def save_calls(calls: list[ToolCall], path: Path) -> None:
    """Compact record of a run: just what effort needs (a full transcript is ~100x bigger)."""
    keep = ("file_path", "command", "pattern", "path")
    path.write_text(json.dumps([{"name": c.name, "input": {k: c.input[k] for k in keep if k in c.input},
                                 "result_chars": c.result_chars, **({"is_error": True} if c.is_error else {})}
                                for c in calls]))


def load_calls(path: Path) -> list[ToolCall]:
    return [ToolCall(c["name"], c["input"], c["result_chars"], c.get("is_error", False))
            for c in json.loads(path.read_text())]


@dataclass
class RecordedAgent:
    """Replays a finished run from its calls.json (no model calls). For re-grading and tests."""

    run_dir: Path
    name: str = "recorded"

    def run(self, workspace: Path, prompt: str, log_dir: Path, snapshot_dir: Path | None = None) -> AgentRun:
        return AgentRun(load_calls(self.run_dir / "calls.json"), stop="recorded")


@dataclass
class CliAgent:
    """A model driven by its vendor's coding CLI. Subclasses give the command and the parser."""

    model: str
    max_turns: int = 80
    budget_usd: float = 1.0       # per run, where the CLI can enforce it; otherwise timeout_s is the backstop
    timeout_s: int = 1800
    snapshots_by_hook = False     # True: the CLI snapshots itself through a hook; False: poll the workspace

    @property
    def name(self) -> str:
        return self.model

    def available(self) -> str | None:
        """Why this agent can't run here (not installed, no credentials), or None."""
        raise NotImplementedError

    def command(self, prompt: str, log_dir: Path, snapshot_dir: Path | None) -> tuple[list[str], dict, str | None]:
        """(argv, extra environment, stdin)."""
        raise NotImplementedError

    def parse(self, lines: list[str], times: list[float], log_dir: Path) -> tuple[AgentRun | None, list[float]]:
        """The run from the CLI's stdout (None if it never finished), and when each tool call finished."""
        raise NotImplementedError

    def run(self, workspace: Path, prompt: str, log_dir: Path, snapshot_dir: Path | None = None) -> AgentRun:
        log_dir = log_dir.resolve()  # the agent runs inside the workspace, so paths must be absolute
        log_dir.mkdir(parents=True, exist_ok=True)
        snapshot_dir = snapshot_dir.resolve() if snapshot_dir else None
        cmd, env, stdin = self.command(prompt, log_dir, snapshot_dir)
        poll = snapshot_dir is not None and not self.snapshots_by_hook
        QUOTA.check()
        started = time.time()
        lines, times, taken = run_cli(cmd, workspace, log_dir, stdin, env, self.timeout_s, poll)
        run, call_times = self.parse(lines, times, log_dir)
        if run is None:  # fail loudly: a run that never started would otherwise score as maximum effort
            raise RuntimeError(f"{self.name} exited without finishing: {(log_dir / 'stderr.txt').read_text()[-500:]}")
        QUOTA.update(run.quota)
        if poll:
            number_snapshots(run.calls, call_times, taken, snapshot_dir)
        save_calls(run.calls, log_dir / "calls.json")
        (log_dir / "run.json").write_text(json.dumps({  # what it cost; see usage.summary
            "agent": self.name, "started": started, "finished": time.time(), "tool_calls": len(run.calls),
            **{k: v for k, v in asdict(run).items() if k != "calls"}}))
        return run


def run_cli(cmd: list[str], workspace: Path, log_dir: Path, stdin: str | None, env: dict, timeout_s: int,
            poll: bool) -> tuple[list[str], list[float], list[tuple[float, Path]]]:
    """Run a CLI in `workspace`: its stdout lines, when each arrived, and (if `poll`) a copy of the
    workspace every time it changed, with when. Logs go to log_dir."""
    taken, stop = [], threading.Event()
    poller = threading.Thread(target=_poll, args=(workspace, log_dir / "polled", taken, stop), daemon=True)
    if poll:
        poller.start()
    with open(log_dir / "stderr.txt", "w") as err:
        proc = subprocess.Popen(cmd, cwd=workspace, env={**os.environ, **env}, text=True, stderr=err,
                                stdin=subprocess.DEVNULL if stdin is None else subprocess.PIPE, stdout=subprocess.PIPE)
        if stdin is not None:
            proc.stdin.write(stdin)
            proc.stdin.close()
        killer = threading.Timer(timeout_s, proc.kill)
        killer.start()
        lines, times = [], []
        for line in proc.stdout:
            lines.append(line.rstrip("\n"))
            times.append(time.time())
        proc.wait()
        killer.cancel()
    stop.set()
    if poll:
        poller.join()
    (log_dir / "transcript.jsonl").write_text("\n".join(lines) + "\n")
    return lines, times, taken


def _poll(workspace: Path, tmp: Path, taken: list, stop: threading.Event) -> None:
    last = tree_digest(workspace)
    while not stop.wait(POLL_S):
        dest = tmp / str(len(taken))
        try:
            d = tree_digest(workspace)
            if d != last:
                shutil.copytree(workspace, dest, ignore=lambda _, names: [n for n in names if n in IGNORE])
                last = d
                taken.append((time.time(), dest))
        except (OSError, shutil.Error):  # a file vanished mid-copy: try again next poll
            shutil.rmtree(dest, ignore_errors=True)


def number_snapshots(calls: list[ToolCall], times: list[float], taken: list, snapshot_dir: Path) -> None:
    """Name polled snapshots by the successful calls finished when each was taken (latest wins)."""
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    for t, src in taken:
        dest = snapshot_dir / f"{sum(1 for c, ct in zip(calls, times) if ct <= t and not c.is_error):04d}"
        if dest.exists():
            shutil.rmtree(dest)
        src.rename(dest)
