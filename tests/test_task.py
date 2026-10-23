"""Tasks load from their folders, and the hidden tests grade the reference."""

from craftbench.grading import run_suite, run_suites
from craftbench.task import list_tasks, load_task

TASK = load_task("etl_pipeline")


def test_task_loads():
    assert "etl_pipeline" in list_tasks()
    assert [m.id for m in TASK.milestones] == ["m1_parse", "m2_execute", "m3_branch"]
    assert "SENTINEL" not in TASK.milestones[0].spec  # benchmark canary is not shown to agents
    assert {"dead_code", "duplicated", "golfed"} <= set(TASK.mutant_dirs())


def test_every_shipped_task_is_complete():
    for task in map(load_task, list_tasks()):
        suites = task.milestones + task.changes
        assert task.reference.is_dir() and task.mutant_dirs(), task.id
        assert all(s.spec and all((task.tests_dir / f).exists() for f in s.tests) for s in suites), task.id


def test_every_rollout_gets_the_same_independent_changes():
    assert [c.id for c in TASK.episode_changes()] == ["subpipelines", "limits", "trace"]
    assert TASK.change("libraries").requires == ("subpipelines",)  # chained, so left out


def test_reference_passes_milestones_but_not_changes():
    res = run_suites(TASK, TASK.reference, list(TASK.milestones))
    assert sum(len(r.passed) for r in res.values()) == 115
    assert sum(len(r.tests) for r in res.values()) == 117
    assert len(run_suite(TASK, TASK.reference, TASK.change("trace")).passed) <= 1
