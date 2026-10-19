"""OpenAI Codex CLI (`codex exec --json`). Flags checked against codex-cli 0.159; the event parser
follows the documented `item.completed` JSONL schema but has NOT been checked against a live run
(no credentials yet). Codex reads code through shell commands, which classify_shell turns into reads."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from ..config import ExtenderSpec
from ..events import EDIT, OTHER, SEARCH, ToolCall, classify_shell
from .base import Harness


class Codex(Harness):
    name = "codex"
    binary = "codex"

    def available(self):
        ok, where = super().available()
        if not ok:
            return ok, where
        status = subprocess.run([self.binary, "login", "status"], capture_output=True, text=True)
        out = (status.stdout + status.stderr).strip()
        return ("Not logged in" not in out, out or where)

    def command(self, spec: ExtenderSpec, workdir: Path, out_dir: Path):
        # No per-run dollar cap in Codex: spec.timeout_s is the backstop. Reading-window readers are
        # not enforceable here (no PreToolUse hooks we can rely on), so validate() rejects them.
        argv = [self.binary, "exec", "--json", "--model", spec.model, "--cd", str(workdir),
                "--sandbox", "workspace-write", "--skip-git-repo-check", "--ephemeral", *spec.extra_args, "-"]
        return argv, {}, True

    def parse(self, lines):
        calls, tokens_in, tokens_out, stop = [], 0, 0, None
        for t, line in lines:
            try:
                ev = json.loads(line)
            except json.JSONDecodeError:
                continue
            typ = ev.get("type")
            if typ == "turn.completed":
                u = ev.get("usage") or {}
                tokens_in += u.get("input_tokens", 0)
                tokens_out += u.get("output_tokens", 0)
            elif typ in ("turn.failed", "error"):
                stop = typ
            elif typ == "item.completed":
                item = ev.get("item", {})
                it = item.get("type")
                if it == "command_execution":
                    cmd = item.get("command", "")
                    kind, path = classify_shell(cmd if isinstance(cmd, str) else " ".join(cmd))
                    calls.append(ToolCall(id=item.get("id", str(len(calls))), name="shell", kind=kind,
                                          input={"command": cmd}, output_chars=len(item.get("aggregated_output") or ""),
                                          is_error=(item.get("exit_code") or 0) != 0, path=path, t=t))
                elif it == "file_change":
                    calls.append(ToolCall(id=item.get("id", str(len(calls))), name="file_change", kind=EDIT,
                                          input={"changes": item.get("changes")}, output_chars=0, t=t))
                elif it in ("mcp_tool_call", "web_search"):
                    calls.append(ToolCall(id=item.get("id", str(len(calls))), name=it,
                                          kind=SEARCH if it == "web_search" else OTHER,
                                          input=item, output_chars=len(json.dumps(item.get("result") or "")), t=t))
        return calls, {"stop_reason": stop or "completed", "tokens_in": tokens_in, "tokens_out": tokens_out}

    def run(self, spec, prompt, workdir, out_dir, seed):
        rec = super().run(spec, prompt, workdir, out_dir, seed)
        rec.cost_usd = self.cost_from_tokens(spec, rec.extra.get("tokens_in", 0), rec.extra.get("tokens_out", 0))
        return rec
