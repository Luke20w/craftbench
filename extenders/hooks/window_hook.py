"""Claude Code PreToolUse hook for the "window:<N>" reader: code can only be read N lines at a time,
so the extender has to navigate by names and search, the way a person with limited working memory does.
Blocks Read without a small limit, and shell commands that print source files."""

import json
import os
import re
import sys

MAX = int(os.environ.get("READ_WINDOW", "200"))
SOURCE = r"\.(py|js|ts|tsx|jsx|go|rs|java|rb|c|cc|cpp|h|hpp|cs|kt|swift)\b"

ev = json.load(sys.stdin)
tool, inp = ev.get("tool_name"), ev.get("tool_input", {})
msg = None
if tool == "Read" and re.search(SOURCE, str(inp.get("file_path", ""))):
    if not inp.get("limit") or int(inp["limit"]) > MAX:
        msg = f"Reads are limited to {MAX} lines at a time here: pass offset and limit (<= {MAX}). Use Grep to find the right place first."
elif tool == "Bash":
    if re.search(r"(^|[|;&]\s*)(cat|head|tail|sed|awk|less|more|nl|bat)\b[^|;&]*" + SOURCE, inp.get("command", "")):
        msg = f"Printing source files from the shell is disabled here. Use Read with offset/limit (<= {MAX} lines) or Grep."
if msg:
    print(msg, file=sys.stderr)
    sys.exit(2)
