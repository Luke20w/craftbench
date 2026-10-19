from pathlib import Path

from craftbench.agents import parse_claude_transcript
from craftbench.grading import run_suite, run_suites
from craftbench.task import list_tasks, load_task

TASK = load_task("etl_pipeline")


def test_task_loads():
    assert "etl_pipeline" in list_tasks()
    assert [m.id for m in TASK.milestones] == ["m1_parse", "m2_execute", "m3_branch"]
    assert "SENTINEL" not in TASK.milestones[0].spec  # benchmark canary is not shown to agents
    assert {"dead_code", "duplicated", "golfed"} <= set(TASK.mutant_dirs())


def test_every_rollout_gets_the_same_independent_changes():
    assert [c.id for c in TASK.episode_changes()] == ["subpipelines", "limits", "trace"]
    assert TASK.episode_changes() == load_task("etl_pipeline").episode_changes()


def test_parse_transcript():
    calls, result = parse_claude_transcript((Path(__file__).parent / "fixtures" / "transcript.jsonl").read_text())
    assert [c.name for c in calls] == ["Read", "Edit", "Bash"]
    assert [c.result_chars for c in calls] == [40, len('[{"type": "text", "text": "ok"}]'), 0]
    assert result["total_cost_usd"] == 0.01


def test_reference_passes_milestones_but_not_changes():
    res = run_suites(TASK, TASK.reference, list(TASK.milestones))
    assert sum(len(r.passed) for r in res.values()) == 115
    assert sum(len(r.tests) for r in res.values()) == 117
    assert len(run_suite(TASK, TASK.reference, TASK.change("trace")).passed) <= 1
