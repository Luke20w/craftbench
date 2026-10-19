"""Claude Code PostToolUse hook: snapshot the working tree whenever its code changes.

Snapshots go to $SNAPDIR/<n>, outside the extender's repo, with <n>.json recording which tool call
caused them, so they can be lined up with the transcript exactly. (PostToolUse does not fire for tool
calls that error, so n counts successful calls; the tool_use_id makes that irrelevant when present.)
"""

import hashlib
import json
import os
import shutil
import sys
from pathlib import Path

SKIP = {"__pycache__", ".git", ".pytest_cache", ".claude", ".venv", "node_modules"}

event = json.load(sys.stdin)
snapdir = Path(os.environ["SNAPDIR"])
snapdir.mkdir(parents=True, exist_ok=True)
counter = snapdir / ".count"
idx = int(counter.read_text()) + 1 if counter.exists() else 1
counter.write_text(str(idx))

root = Path(event.get("cwd") or os.getcwd())
h = hashlib.md5()
for p in sorted(root.rglob("*")):
    rel = p.relative_to(root)
    if p.is_file() and not set(rel.parts) & SKIP:
        h.update(str(rel).encode())
        h.update(p.read_bytes())
digest = h.hexdigest()
last = snapdir / ".last"
if not last.exists() or last.read_text() != digest:
    last.write_text(digest)
    shutil.copytree(root, snapdir / f"{idx:04d}", ignore=lambda d, names: [n for n in names if n in SKIP])
    (snapdir / f"{idx:04d}.json").write_text(json.dumps(
        {"tool_use_id": event.get("tool_use_id"), "tool_name": event.get("tool_name")}))
