"""End-to-end plumbing without model calls, using an extender that changes nothing."""

import json
from pathlib import Path

import pytest

from craftbench import Environment, load_task
from craftbench.agents import AgentRun
from craftbench.effort import FAILURE_TOKENS
from craftbench.reward import reward


class NoOpAgent:
    name = "noop"

    def __init__(self):
        self.prompts = []

    def run(self, workspace: Path, prompt: str, log_dir: Path, snapshot_dir: Path | None = None) -> AgentRun:
        self.prompts.append(prompt)
        return AgentRun(calls=[])


def test_grade_with_an_extender_that_does_nothing(tmp_path):
    task = load_task("etl_pipeline")
    agent = NoOpAgent()
    stale = tmp_path / "out" / "maintain" / "limits" / "noop" / "run_0" / "snaps" / "0099"
    stale.mkdir(parents=True)  # left over from an earlier run: must not leak into this one
    g = Environment(task, extenders=[agent], runs_dir=tmp_path).grade(task.reference, tmp_path / "out")
    assert not stale.exists()
    assert g.milestone_pass_fraction == pytest.approx(115 / 117)
    assert set(g.efforts) == {"subpipelines", "limits", "trace"}
    # nothing changed: every new test is a failure. Tests that already passed on the untouched code
    # (3/20 for limits) aren't charged either way: the extender didn't make them pass.
    assert g.efforts["subpipelines"] == pytest.approx(FAILURE_TOKENS)
    assert g.efforts["limits"] == pytest.approx(FAILURE_TOKENS)
    assert g.extender_runs["limits"][0]["already_passing"] == 3
    assert g.reward == pytest.approx(reward(g.milestone_pass_fraction, list(g.efforts.values())))
    assert g.efforts_by_extender["limits"] == {"noop": pytest.approx(g.efforts["limits"])}
    assert "stop" in agent.prompts[0]
    assert json.loads((tmp_path / "out" / "grade.json").read_text())["reward"] == pytest.approx(g.reward)

