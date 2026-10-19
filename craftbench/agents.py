"""Agents edit a workspace. The same interface serves the policy (build phase) and the frozen
extender (maintain phase). Effort only needs the list of tool calls and the snapshots, so any agent
that reports its tool calls and snapshots after each one can be plugged in.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

SNAPSHOT_HOOK = Path(__file__).resolve().parent / "hooks" / "snapshot.py"


@dataclass(frozen=True)
class ToolCall:
    name: str             # e.g. Read, Grep, Bash, Edit
    input: dict           # tool arguments
    result_chars: int     # size of what the tool returned to the agent
    is_error: bool = False  # the tool call failed (snapshot hooks don't fire for these)


@dataclass
class AgentRun:
    calls: list[ToolCall]
    cost_usd: float = 0.0
    stop: str = ""


class Agent(Protocol):
    def run(self, workspace: Path, prompt: str, log_dir: Path, snapshot_dir: Path | None = None) -> AgentRun:
        """Work on `workspace` until done. If `snapshot_dir` is given, snapshot the workspace after
        every tool call into snapshot_dir/<call index>."""


def save_calls(calls: list[ToolCall], path: Path) -> None:
    """Compact record of a run: just what effort needs (a full transcript is ~100x bigger)."""
    keep = ("file_path", "command", "pattern", "path")
    path.write_text(json.dumps([{"name": c.name, "input": {k: c.input[k] for k in keep if k in c.input},
                                 "result_chars": c.result_chars, **({"is_error": True} if c.is_error else {})}
                                for c in calls]))


def load_calls(path: Path) -> list[ToolCall]:
    return [ToolCall(c["name"], c["input"], c["result_chars"], c.get("is_error", False))
            for c in json.loads(path.read_text())]


def parse_claude_transcript(text: str) -> tuple[list[ToolCall], dict]:
    """Tool calls in order, and the final result event, from `claude -p --output-format stream-json`."""
    meta, size, errors, order, result = {}, {}, set(), [], {}
    for line in text.splitlines():
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            continue
        if ev.get("type") == "result":
            result = ev
        content = ev["message"].get("content") if isinstance(ev.get("message"), dict) else None
        for c in content if isinstance(content, list) else []:
            if c.get("type") == "tool_use":
                meta[c["id"]] = (c["name"], c.get("input", {}))
                order.append(c["id"])
            elif c.get("type") == "tool_result":
                body = c.get("content")
                size[c.get("tool_use_id")] = len(body if isinstance(body, str) else json.dumps(body))
                if c.get("is_error"):
                    errors.add(c.get("tool_use_id"))
    return [ToolCall(*meta[i], size.get(i, 0), i in errors) for i in order], result


@dataclass
class ClaudeCodeAgent:
    """Claude Code in headless mode: the default frozen extender (Haiku) and a demo policy."""

    model: str = "haiku"
    max_turns: int = 80
    max_budget_usd: float = 0.40

    def run(self, workspace: Path, prompt: str, log_dir: Path, snapshot_dir: Path | None = None) -> AgentRun:
        log_dir = log_dir.resolve()  # the agent runs inside the workspace, so paths must be absolute
        log_dir.mkdir(parents=True, exist_ok=True)
        cmd = ["claude", "-p", "--model", self.model, "--max-turns", str(self.max_turns),
               "--max-budget-usd", str(self.max_budget_usd),
               "--strict-mcp-config", "--setting-sources", "project",   # ignore user config and MCP servers
               "--dangerously-skip-permissions", "--no-session-persistence",
               "--disallowedTools", "WebSearch", "WebFetch", "Agent", "Task",
               "--output-format", "stream-json", "--verbose"]
        env = dict(os.environ)
        if snapshot_dir is not None:
            hook = {"type": "command", "command": f"{sys.executable} {SNAPSHOT_HOOK}"}
            settings = log_dir / "hook_settings.json"
            settings.write_text(json.dumps({"hooks": {"PostToolUse": [{"matcher": ".*", "hooks": [hook]}]}}))
            cmd += ["--settings", str(settings)]
            env["SNAPSHOT_DIR"] = str(snapshot_dir.resolve())
        proc = subprocess.run(cmd, input=prompt, cwd=workspace, capture_output=True, text=True, env=env)
        (log_dir / "transcript.jsonl").write_text(proc.stdout)
        calls, result = parse_claude_transcript(proc.stdout)
        if not result:  # fail loudly: a run that never started would otherwise score as maximum effort
            raise RuntimeError(f"claude exited without a result: {(proc.stderr or proc.stdout)[-500:]}")
        save_calls(calls, log_dir / "calls.json")
        return AgentRun(calls, result.get("total_cost_usd") or 0.0, result.get("subtype", "no_result"))


@dataclass
class RecordedAgent:
    """Replays a finished run from its calls.json (no model calls). For re-grading and tests."""

    run_dir: Path

    def run(self, workspace: Path, prompt: str, log_dir: Path, snapshot_dir: Path | None = None) -> AgentRun:
        return AgentRun(load_calls(self.run_dir / "calls.json"), stop="recorded")
