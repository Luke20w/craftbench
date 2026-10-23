"""Claude Code PostToolUse hook: snapshot the workspace whenever its source files change.

Snapshots go to $SNAPSHOT_DIR/<tool-call-index>, outside the agent's workspace, so the agent
never sees them. PostToolUse doesn't fire for failed tool calls, so the index counts successful
calls; effort.reading_at_snapshot maps it back to the transcript.
"""

import hashlib
import json
import os
import shutil
import sys
from pathlib import Path

# A standalone script in a fresh interpreter per tool call, so it doesn't import the package: keep SKIP and
# the digest in sync with sandbox.IGNORE and sandbox.tree_digest.
SKIP = {"__pycache__", ".git", ".pytest_cache", ".claude", ".venv", "node_modules"}

event = json.load(sys.stdin)
snapdir = Path(os.environ["SNAPSHOT_DIR"])
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
