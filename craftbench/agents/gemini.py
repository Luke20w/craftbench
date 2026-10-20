"""Google models through Gemini CLI (`gemini -p --output-format stream-json`). Auth: GEMINI_API_KEY.

Each run gets its own GEMINI_CLI_HOME, so user settings, extensions and memory don't leak in. The
event stream only carries display summaries of tool results ("Read 120 lines"), so what the model
actually read is taken from the session log Gemini CLI writes in that home. No dollar cap: timeout_s
is the backstop; the workspace is polled for snapshots."""

from __future__ import annotations

import json
import os
import shutil
from dataclasses import dataclass
from pathlib import Path

from .base import AgentRun, CliAgent, ToolCall

TOOLS = {"read_file": "Read", "read_many_files": "Grep", "grep_search": "Grep", "glob": "Glob",
         "list_directory": "Glob", "run_shell_command": "Bash", "replace": "Edit", "write_file": "Write"}


@dataclass
class GeminiAgent(CliAgent):
    def available(self) -> str | None:
        if not shutil.which("gemini"):
            return "gemini is not installed (npm i -g @google/gemini-cli)"
        return None if os.environ.get("GEMINI_API_KEY") else "set GEMINI_API_KEY"

    def command(self, prompt: str, log_dir: Path, snapshot_dir: Path | None):
        home = log_dir / "gemini_home"
        (home / ".gemini").mkdir(parents=True, exist_ok=True)
        (home / ".gemini" / "settings.json").write_text(json.dumps({
            "security": {"auth": {"selectedType": "gemini-api-key"}},
            "tools": {"exclude": ["web_fetch", "google_web_search", "invoke_agent"]},
            "model": {"maxSessionTurns": self.max_turns},
            "privacy": {"usageStatisticsEnabled": False}}))
        return (["gemini", "--model", self.model, "--output-format", "stream-json", "--approval-mode", "yolo",
                 "--skip-trust", "-p", prompt], {"GEMINI_CLI_HOME": str(home)}, None)

    def parse(self, lines, times, log_dir):
        return parse_gemini(lines, times, read_sizes(log_dir / "gemini_home"))


def parse_gemini(lines: list[str], times: list[float], sizes: dict[str, int]) -> tuple[AgentRun | None, list[float]]:
    """The run (None without a final result event) and when each tool call finished."""
    uses, calls, call_times, result = {}, [], [], None
    for line, t in zip(lines, times):
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            continue
        if ev.get("type") == "tool_use":
            uses[ev.get("tool_id")] = (ev.get("tool_name", ""), ev.get("parameters") or {})
        elif ev.get("type") == "tool_result" and ev.get("tool_id") in uses:
            name, args = uses[ev["tool_id"]]
            inp = ({"file_path": args.get("file_path") or args.get("absolute_path", "")} if name == "read_file" else
                   {"command": args.get("command", "")} if name == "run_shell_command" else {})
            chars = sizes.get(ev["tool_id"], len(ev.get("output") or ""))
            calls.append(ToolCall(TOOLS.get(name, name), inp, chars, ev.get("status") == "error"))
            call_times.append(t)
        elif ev.get("type") == "result":
            result = ev
    if result is None:
        return None, call_times
    return AgentRun(calls, stop=result.get("status", ""), usage=result.get("stats") or {}), call_times


def read_sizes(home: Path) -> dict[str, int]:
    """Tool call id -> characters of the result the model was given, from the session log."""
    sizes = {}
    for log in home.rglob("session-*.jsonl"):
        for line in log.read_text(errors="replace").splitlines():
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(record, dict):
                continue
            for tc in record.get("toolCalls") or []:  # a message is re-logged as it grows; the last copy wins
                responses = [p.get("functionResponse", {}).get("response") for p in tc.get("result") or []
                             if isinstance(p, dict)]
                sizes[tc.get("id")] = _text_chars(responses)
    return sizes


def _text_chars(obj) -> int:
    if isinstance(obj, str):
        return len(obj)
    if isinstance(obj, dict):
        return sum(_text_chars(v) for v in obj.values())
    if isinstance(obj, list):
        return sum(_text_chars(v) for v in obj)
    return 0
