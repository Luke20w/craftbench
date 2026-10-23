"""Claude models through Claude Code (`claude -p --output-format stream-json`), the harness of the default
extender panel. Snapshots come from a PostToolUse hook, so they line up with tool calls exactly."""

from __future__ import annotations

import json
import os
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

from .base import AgentRun, CliAgent, ToolCall

SNAPSHOT_HOOK = Path(__file__).resolve().parent / "snapshot_hook.py"


@dataclass
class ClaudeCodeAgent(CliAgent):
    model: str = "haiku"
    snapshots_by_hook = True

    def available(self) -> str | None:
        if not shutil.which("claude"):
            return "claude is not installed"
        if os.environ.get("ANTHROPIC_API_KEY"):
            print("note: ANTHROPIC_API_KEY is set, so Claude Code bills the API, not a subscription", file=sys.stderr)
        return None

    def command(self, prompt: str, log_dir: Path, snapshot_dir: Path | None):
        cmd = ["claude", "-p", "--model", self.model, "--max-turns", str(self.max_turns),
               "--max-budget-usd", str(self.budget_usd),
               "--strict-mcp-config", "--setting-sources", "project",   # ignore user config and MCP servers
               "--dangerously-skip-permissions", "--no-session-persistence",
               "--disallowedTools", "WebSearch", "WebFetch", "Agent", "Task",
               "--output-format", "stream-json", "--verbose"]
        env = {}
        if snapshot_dir is not None:
            hook = {"type": "command", "command": f"{sys.executable} {SNAPSHOT_HOOK}"}
            settings = log_dir / "hook_settings.json"
            settings.write_text(json.dumps({"hooks": {"PostToolUse": [{"matcher": ".*", "hooks": [hook]}]}}))
            cmd += ["--settings", str(settings)]
            env["SNAPSHOT_DIR"] = str(snapshot_dir)
        return cmd, env, prompt

    def parse(self, lines, times, log_dir):
        calls, result = parse_claude_transcript("\n".join(lines))
        if not result or result.get("terminal_reason") == "api_error":  # e.g. the network was down: not a real run
            return None, []
        quota = {}
        for line in lines:  # subscription usage, reported as the run starts
            if '"rate_limit_event"' in line:
                try:
                    quota = json.loads(line).get("rate_limit_info") or quota
                except json.JSONDecodeError:
                    pass
        run = AgentRun(calls, result.get("total_cost_usd") or 0.0, result.get("subtype", "no_result"),
                       result.get("usage") or {}, quota)
        return run, []  # the hook numbers snapshots itself


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
