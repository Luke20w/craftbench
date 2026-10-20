"""OpenAI models through Codex (`codex exec --json`). Auth: CODEX_API_KEY or `codex login`. Codex has
no dollar cap, so timeout_s is the backstop; the workspace is polled for snapshots."""

from __future__ import annotations

import json
import os
import shlex
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .base import AgentRun, CliAgent, ToolCall


@dataclass
class CodexAgent(CliAgent):
    def available(self) -> str | None:
        if not shutil.which("codex"):
            return "codex is not installed (npm i -g @openai/codex)"
        status = subprocess.run(["codex", "login", "status"], capture_output=True, text=True)
        if not os.environ.get("CODEX_API_KEY") and "Logged in" not in status.stdout + status.stderr:
            return "set CODEX_API_KEY or run `codex login`"
        return None

    def command(self, prompt: str, log_dir: Path, snapshot_dir: Path | None):
        return (["codex", "exec", "--json", "--model", self.model, "--sandbox", "workspace-write", "--ephemeral",
                 "--ignore-user-config", "-c", 'web_search="disabled"', "-"], {}, prompt)

    def parse(self, lines, times, log_dir):
        return parse_codex(lines, times)


def parse_codex(lines: list[str], times: list[float]) -> tuple[AgentRun | None, list[float]]:
    """The run (None if no turn finished) and when each tool call finished."""
    calls, call_times, usage, stop = [], [], {}, None
    for line, t in zip(lines, times):
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            continue
        if ev.get("type") == "turn.completed":
            stop = stop or "success"
            for k, v in (ev.get("usage") or {}).items():
                usage[k] = usage.get(k, 0) + v
        elif ev.get("type") == "turn.failed":  # bare "error" events are often transient (reconnects)
            stop = "turn.failed"
        elif ev.get("type") == "item.completed":
            item = ev.get("item", {})
            if item.get("type") == "command_execution":
                call = ToolCall("Bash", {"command": _unwrap_shell(item.get("command", ""))},
                                len(item.get("aggregated_output") or ""), (item.get("exit_code") or 0) != 0)
            elif item.get("type") == "file_change":
                paths = [c.get("path", "") for c in item.get("changes", [])]
                call = ToolCall("Edit", {"file_path": paths[0] if paths else ""}, 0)
            elif item.get("type") in ("mcp_tool_call", "web_search"):
                call = ToolCall(item["type"], {}, len(json.dumps(item.get("result") or "")))
            else:
                continue
            calls.append(call)
            call_times.append(t)
    return (AgentRun(calls, stop=stop, usage=usage) if stop else None), call_times


def _unwrap_shell(command) -> str:
    """`bash -lc 'sed -n 1,80p a.py'` -> `sed -n 1,80p a.py`, so effort sees what was run."""
    if isinstance(command, list):
        command = shlex.join(command)
    try:
        parts = shlex.split(command)
    except ValueError:
        return command
    return parts[2] if len(parts) == 3 and parts[0].endswith("sh") and parts[1] in ("-c", "-lc") else command
