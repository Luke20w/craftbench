"""Agents edit a workspace. The same interface serves the builder/policy (build phase) and the frozen
extenders (maintain phase). Each model runs in its vendor's coding CLI; `make_agent` picks it."""

from .base import Agent, AgentRun, CliAgent, RecordedAgent, ToolCall, load_calls, save_calls
from .claude import ClaudeCodeAgent, parse_claude_transcript
from .codex import CodexAgent
from .gemini import GeminiAgent

HARNESSES = {"claude": ClaudeCodeAgent, "codex": CodexAgent, "gemini": GeminiAgent}


def make_agent(spec: str, max_turns: int = 80, budget_usd: float = 1.0) -> CliAgent:
    """An agent from a model id: claude-* / haiku / sonnet / opus / fable → Claude Code, gpt-* → Codex,
    gemini-* → Gemini CLI. `harness:model` (e.g. `codex:o4-mini`) picks the harness explicitly."""
    harness, _, model = spec.rpartition(":")
    if not harness:
        harness = ("claude" if model.startswith(("claude", "haiku", "sonnet", "opus", "fable")) else
                   "codex" if model.startswith(("gpt", "codex", "o3", "o4")) else
                   "gemini" if model.startswith("gemini") else "")
    if harness not in HARNESSES:
        raise ValueError(f"no harness for {spec!r}: use one of {', '.join(f'{h}:<model>' for h in HARNESSES)}")
    return HARNESSES[harness](model, max_turns=max_turns, budget_usd=budget_usd)


__all__ = ["Agent", "AgentRun", "CliAgent", "ClaudeCodeAgent", "CodexAgent", "GeminiAgent", "RecordedAgent",
           "ToolCall", "load_calls", "make_agent", "parse_claude_transcript", "save_calls"]
