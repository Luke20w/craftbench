"""Claude Code (`claude -p`, stream-json). Verified against recorded runs."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from ..config import ExtenderSpec
from ..events import EDIT, OTHER, READ, SEARCH, Snapshot, ToolCall, classify_shell
from .base import Harness

HOOKS = Path(__file__).resolve().parent.parent / "hooks"
KIND = {"Read": READ, "Grep": SEARCH, "Glob": SEARCH, "LS": SEARCH,
        "Edit": EDIT, "Write": EDIT, "MultiEdit": EDIT, "NotebookEdit": EDIT}


class ClaudeCode(Harness):
    name = "claude_code"
    binary = "claude"
    supports_window = True
    snapshot_mode = "hook"
    verified = True

    def command(self, spec: ExtenderSpec, workdir: Path, out_dir: Path):
        hooks = {"PostToolUse": [{"matcher": ".*", "hooks": [
            {"type": "command", "command": f"{sys.executable} {HOOKS / 'snapshot_hook.py'}"}]}]}
        if spec.window:
            hooks["PreToolUse"] = [{"matcher": "Read|Bash", "hooks": [
                {"type": "command", "command": f"{sys.executable} {HOOKS / 'window_hook.py'}"}]}]
        settings = out_dir / "settings.json"
        settings.parent.mkdir(parents=True, exist_ok=True)
        settings.write_text(json.dumps({"hooks": hooks}))
        argv = ["claude", "-p", "--model", spec.model, "--max-turns", str(spec.max_turns),
                "--max-budget-usd", str(spec.budget_usd), "--output-format", "stream-json", "--verbose",
                "--strict-mcp-config", "--setting-sources", "project", "--settings", str(settings),
                "--dangerously-skip-permissions", "--no-session-persistence",
                "--disallowedTools", "WebSearch", "WebFetch", "Agent", "Task", *spec.extra_args]
        env = {"SNAPDIR": str(out_dir / "snaps")}
        if spec.window:
            env["READ_WINDOW"] = str(spec.window)
        return argv, env, True

    def parse(self, lines):
        meta, calls, by_id, order = {}, [], {}, []
        for t, line in lines:
            try:
                ev = json.loads(line)
            except json.JSONDecodeError:
                continue
            if ev.get("type") == "result":
                meta = {"cost_usd": ev.get("total_cost_usd"), "stop_reason": ev.get("subtype"),
                        "turns": ev.get("num_turns"), "usage": ev.get("usage")}
            msg = ev.get("message") if isinstance(ev.get("message"), dict) else {}
            for c in msg.get("content", []) if isinstance(msg.get("content"), list) else []:
                if c.get("type") == "tool_use" and c["id"] not in by_id:
                    name, inp = c["name"], c.get("input", {})
                    kind, path = KIND.get(name, OTHER), inp.get("file_path")
                    if name == "Bash":
                        kind, path = classify_shell(inp.get("command", ""))
                    call = ToolCall(id=c["id"], name=name, kind=kind, input=inp, output_chars=0, path=path)
                    by_id[c["id"]] = call
                    order.append(call)
                elif c.get("type") == "tool_result" and c.get("tool_use_id") in by_id:
                    call = by_id[c["tool_use_id"]]
                    body = c.get("content")
                    call.output_chars = len(body if isinstance(body, str) else json.dumps(body))
                    call.is_error = bool(c.get("is_error"))
                    call.t = t
        calls.extend(order)
        return calls, meta

    def hook_snapshots(self, calls, snapdir: Path):
        """Line snapshots up with tool calls: by the recorded tool_use_id when the hook got one,
        otherwise as the k-th successful call (the hook never fires for calls that error)."""
        pos = {c.id: i for i, c in enumerate(calls)}
        successful = [i for i, c in enumerate(calls) if not c.is_error]
        snaps = []
        for d in sorted(p for p in snapdir.glob("[0-9]*") if p.is_dir()):
            meta = d.with_suffix(".json")
            tid = json.loads(meta.read_text()).get("tool_use_id") if meta.exists() else None
            if tid in pos:
                i = pos[tid]
            else:
                k = int(d.name)
                i = successful[min(k, len(successful)) - 1] if successful else -1
            snaps.append(Snapshot(dir=d, after_calls=i + 1))
        return snaps
