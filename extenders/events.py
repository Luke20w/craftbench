"""The harness-agnostic record of one extender run."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

READ, SEARCH, EDIT, SHELL, OTHER = "read", "search", "edit", "shell", "other"

_SHELL_READ = re.compile(r"(?:^|[|;&]\s*)(?:cat|head|tail|sed\s+-n|nl|less|more|bat|awk)\b[^|;&]*?(\S+\.\w+)")
_SHELL_SEARCH = re.compile(r"(?:^|[|;&]\s*)(?:grep|rg|ag|find|ls|tree|fd)\b")
_SHELL_EDIT = re.compile(r"\bsed\s+-i|>\s*\S+\.\w+|\bcat\s*>|\btee\b|\bapply_patch\b|\bpatch\b")


@dataclass
class ToolCall:
    id: str
    name: str                 # harness-native tool name
    kind: str                 # READ | SEARCH | EDIT | SHELL | OTHER
    input: dict
    output_chars: int         # size of what the agent got back (what it had to read)
    is_error: bool = False
    path: str | None = None   # file that was read, for kind == READ
    t: float | None = None    # wall-clock time the result arrived, when the runner streams


@dataclass
class Snapshot:
    dir: Path
    after_calls: int          # transcript tool calls completed when the snapshot was taken


@dataclass
class RunRecord:
    extender_id: str
    harness: str
    model: str
    seed: int
    workdir: Path
    transcript: Path
    calls: list[ToolCall]
    snapshots: list[Snapshot]
    cost_usd: float | None = None
    stop_reason: str | None = None
    turns: int | None = None
    extra: dict = field(default_factory=dict)


def classify_shell(command: str) -> tuple[str, str | None]:
    """(kind, path) for a shell command, so shell-based readers (Codex reads with `sed -n`, `cat`)
    are scored like tool-based ones."""
    if _SHELL_EDIT.search(command):
        return EDIT, None
    m = _SHELL_READ.search(command)
    if m:
        return READ, m.group(1)
    if _SHELL_SEARCH.search(command):
        return SEARCH, None
    return SHELL, None
