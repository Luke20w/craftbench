"""Extender panel: frozen coding agents that implement hidden change requests on a policy's codebase,
so the environment can score how cheap that code is to change (nodes_read_per_test).

Harness-agnostic: each agent CLI (Claude Code, Codex, Antigravity, OpenCode, ...) has an adapter that
turns its transcript into a common list of ToolCalls plus snapshots of the working tree, and scoring
only ever sees that common form. Which extenders run is set in panel.toml.
"""
