"""Codex / Gemini parsing and polled snapshots, without model calls (event shapes from each CLI's
documented or source-level output format)."""

import json
import sys

import pytest

from craftbench.agents import ClaudeCodeAgent, CodexAgent, GeminiAgent, load_calls, make_agent
from craftbench.agents.codex import parse_codex
from craftbench.agents.gemini import parse_gemini, read_sizes


def test_codex_events_map_onto_claude_tool_names():
    events = [
        {"type": "thread.started"},
        {"type": "item.completed", "item": {"type": "command_execution", "command": "bash -lc 'sed -n 1,80p a.py'",
                                            "aggregated_output": "x" * 500, "exit_code": 0}},
        {"type": "item.completed", "item": {"type": "agent_message", "text": "editing"}},
        {"type": "item.completed", "item": {"type": "file_change", "changes": [{"path": "a.py", "kind": "update"}]}},
        {"type": "item.completed", "item": {"type": "command_execution", "command": "pytest", "aggregated_output": "F",
                                            "exit_code": 1}},
        {"type": "turn.completed", "usage": {"input_tokens": 10, "output_tokens": 2}},
    ]
    run, times = parse_codex([json.dumps(e) for e in events], [1, 2, 3, 4, 5, 6])
    assert [(c.name, c.result_chars, c.is_error) for c in run.calls] == [("Bash", 500, False), ("Edit", 0, False),
                                                                          ("Bash", 1, True)]
    assert run.calls[0].input["command"] == "sed -n 1,80p a.py"  # unwrapped, so effort sees a code read
    assert times == [2, 4, 5] and run.usage == {"input_tokens": 10, "output_tokens": 2} and run.stop == "success"
    assert parse_codex([json.dumps(events[1])], [1])[0] is None  # never finished a turn


def test_gemini_reading_comes_from_the_session_log(tmp_path):
    chats = tmp_path / ".gemini" / "tmp" / "proj" / "chats"
    chats.mkdir(parents=True)
    tool_call = {"id": "t1", "name": "read_file", "result": [{"functionResponse": {"id": "t1", "name": "read_file",
                                                                                     "response": {"output": "y" * 900}}}]}
    (chats / "session-1-abcd1234.jsonl").write_text(json.dumps({"sessionId": "s"}) + "\n" +
                                                    json.dumps({"type": "gemini", "toolCalls": [tool_call]}) + "\n")
    sizes = read_sizes(tmp_path)
    assert sizes == {"t1": 900}  # what the model got, not the "Read 30 lines" summary in the stream
    events = [
        {"type": "tool_use", "tool_name": "read_file", "tool_id": "t1", "parameters": {"file_path": "/w/code/a.py"}},
        {"type": "tool_result", "tool_id": "t1", "status": "success", "output": "Read 30 lines"},
        {"type": "tool_use", "tool_name": "run_shell_command", "tool_id": "t2", "parameters": {"command": "ls"}},
        {"type": "tool_result", "tool_id": "t2", "status": "error", "output": "boom"},
        {"type": "result", "status": "success", "stats": {"total_tokens": 5}},
    ]
    run, times = parse_gemini([json.dumps(e) for e in events], [1, 2, 3, 4, 5], sizes)
    assert [(c.name, c.result_chars, c.is_error) for c in run.calls] == [("Read", 900, False), ("Bash", 4, True)]
    assert run.calls[0].input == {"file_path": "/w/code/a.py"} and times == [2, 4] and run.stop == "success"


FAKE_CODEX = """
import json, pathlib, time
def item(i): print(json.dumps({"type": "item.completed", "item": i}), flush=True)
item({"type": "command_execution", "command": "cat a.py", "aggregated_output": "original", "exit_code": 0})
time.sleep(1.5)
pathlib.Path("a.py").write_text("changed")
time.sleep(0.1)
item({"type": "file_change", "changes": [{"path": "a.py", "kind": "update"}]})
time.sleep(1.5)
print(json.dumps({"type": "turn.completed", "usage": {}}), flush=True)
"""


class FakeCodex(CodexAgent):
    def command(self, prompt, log_dir, snapshot_dir):
        return [sys.executable, "-c", FAKE_CODEX], {}, prompt


def test_polled_snapshots_are_numbered_by_successful_calls(tmp_path):
    ws = tmp_path / "ws"
    ws.mkdir()
    (ws / "a.py").write_text("original")
    run = FakeCodex("fake").run(ws, "edit a.py", tmp_path / "logs", tmp_path / "snaps")
    saved = load_calls(tmp_path / "logs" / "calls.json")
    assert [c.name for c in run.calls] == ["Bash", "Edit"] == [c.name for c in saved]
    [snap] = list((tmp_path / "snaps").iterdir())
    # taken after the edit, before or just after its result arrived: either count is right
    assert snap.name in ("0001", "0002") and (snap / "a.py").read_text() == "changed"


@pytest.mark.parametrize("spec, kind", [("claude-opus-5-5", ClaudeCodeAgent), ("haiku", ClaudeCodeAgent),
                                        ("gpt-6-astra", CodexAgent), ("gemini-4-argon", GeminiAgent),
                                        ("codex:some-model", CodexAgent)])
def test_make_agent_picks_the_vendor_cli(spec, kind):
    agent = make_agent(spec)
    assert isinstance(agent, kind) and agent.name == spec.split(":")[-1]


def test_make_agent_rejects_unknown_models():
    with pytest.raises(ValueError):
        make_agent("llama-5")
