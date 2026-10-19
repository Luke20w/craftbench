"""Harness registry: panel.toml's `harness = "..."` picks one of these."""

from .antigravity import Antigravity
from .base import Harness
from .claude_code import ClaudeCode
from .codex import Codex
from .opencode import OpenCode

REGISTRY: dict[str, Harness] = {h.name: h for h in (ClaudeCode(), Codex(), Antigravity(), OpenCode())}
