"""Benchmark report and resume, without model calls."""

import shutil

import pytest

from craftbench import Environment, load_task
from craftbench.agents import AgentRun
from craftbench.bench import report, run
from craftbench.reward import geomean, reward


def grade(F, efforts):  # efforts: change -> extender -> effort
    panel = {c: geomean(e.values()) for c, e in efforts.items()}
    return {"reward": reward(F, list(panel.values())), "milestone_pass_fraction": F, "efforts": panel,
            "efforts_by_extender": efforts, "metrics": {"nodes": 3000}}


def test_report_shows_each_extenders_relative_view():
    out = report({"a": [grade(1.0, {"limits": {"x": 1000, "y": 4000}})],
                  "b": [grade(0.9, {"limits": {"x": 2000, "y": 4000}})]})
    assert "| a | 1 | 1.00 |" in out
    assert "| a | 0.67 | 1.00 |" in out and "| b | 1.33 | 1.00 |" in out  # x prefers a; y can't tell them apart


class CopiesReference:
    """Copies the reference into the workspace: as a builder it writes the solution; as an extender it
    changes nothing (its workspace already is the reference). Counts its runs."""

    def __init__(self, name, task):
        self.name, self.task, self.runs = name, task, 0

    def run(self, workspace, prompt, log_dir, snapshot_dir=None):
        self.runs += 1
        shutil.copytree(self.task.reference, workspace, dirs_exist_ok=True)
        return AgentRun(calls=[])


def test_rerunning_reuses_builds_and_extender_runs(tmp_path):
    task = load_task("etl_pipeline")
    builder, ext = CopiesReference("ref", task), CopiesReference("x", task)
    env = Environment(task, extenders=[ext], runs_dir=tmp_path)
    first = run(env, [builder], runs=1)["ref"][0]
    assert first["milestone_pass_fraction"] == pytest.approx(115 / 117) and (builder.runs, ext.runs) == (3, 3)
    assert "| ref | 1 | 0.98 |" in report({"ref": [first]})

    again = run(env, [builder], runs=1)["ref"][0]
    assert (builder.runs, ext.runs) == (3, 3) and again["efforts"] == first["efforts"]  # nothing redone

    new = CopiesReference("y", task)  # a bigger panel later: only the new extender runs
    env.extenders = [ext, new]
    graded = run(env, [builder], runs=1)["ref"][0]
    assert (builder.runs, ext.runs, new.runs) == (3, 3, 3) and set(graded["efforts_by_extender"]["limits"]) == {"x", "y"}


def test_results_carry_over_to_another_checkout(tmp_path, monkeypatch):
    task = load_task("etl_pipeline")
    builder, ext = CopiesReference("ref", task), CopiesReference("x", task)
    run(Environment(task, extenders=[ext], runs_dir=tmp_path / "a"), [builder], runs=1)
    shutil.copytree(tmp_path / "a", tmp_path / "b")  # e.g. exported to the repo, restored elsewhere
    monkeypatch.setattr(Environment, "run_hint", property(lambda self: "/elsewhere/python etl_pipeline.py"))  # another venv
    graded = run(Environment(task, extenders=[ext], runs_dir=tmp_path / "b"), [builder], runs=1)["ref"]
    assert graded and (builder.runs, ext.runs) == (3, 3)  # nothing rebuilt or rerun
