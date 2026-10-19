import pytest

from craftbench.agents import ToolCall
from craftbench.analysis import PythonAnalyzer
from craftbench.effort import FAILURE_TOKENS, change_effort, read_weight
from craftbench.grading import Curve, CurvePoint
from craftbench.task import load_task

TASK = load_task("etl_pipeline")
PY = PythonAnalyzer()
OLD_TESTS = 100


def bash(chars):  # a tool call that isn't reading code, so weight 1
    return ToolCall("Bash", {"command": "pytest -q"}, chars)


CALLS = [bash(400)] * 5  # 100 tokens read per call


def effort(*points, tests=("t",)):
    curve = Curve(tests, tuple(CurvePoint(call, frozenset(new), reg) for call, new, reg in points))
    return change_effort(CALLS, curve, TASK.reference, PY, OLD_TESTS)


def test_charged_from_the_start_of_the_final_passing_streak():
    assert effort((1, [], 100), (2, ["t"], 100), (4, ["t"], 100)) == 200


def test_passing_then_breaking_counts_as_failure():
    assert effort((2, ["t"], 100), (4, [], 100)) == FAILURE_TOKENS


def test_only_counts_once_old_tests_are_intact():
    assert effort((2, ["t"], 50), (3, ["t"], 100)) == 300


def test_averaged_over_tests():
    assert effort((2, ["a"], 100), (4, ["a", "b"], 100), tests=("a", "b")) == 300


def test_reading_dense_code_costs_more():
    read = ToolCall("Read", {"file_path": "/x/code/etl_pipeline.py"}, 4_000)
    assert read_weight(read, TASK.reference, PY) == pytest.approx(1.0, abs=0.01)  # clean code ≈ 1
    assert read_weight(read, TASK.mutants / "golfed", PY) == pytest.approx(1.895, abs=0.01)
    assert read_weight(bash(4_000), TASK.mutants / "golfed", PY) == 1.0  # not code
    cat = ToolCall("Bash", {"command": "cat etl_pipeline.py"}, 4_000)
    assert read_weight(cat, TASK.mutants / "golfed", PY) == pytest.approx(1.895, abs=0.01)  # printing code is reading it


def test_snapshots_skip_failed_calls():
    # Snapshot 2 is taken after the 2nd *successful* call, i.e. after transcript call 3.
    calls = [bash(400), ToolCall("Edit", {}, 400, is_error=True), bash(400), bash(400)]
    curve = Curve(("t",), (CurvePoint(2, frozenset(["t"]), OLD_TESTS),))
    assert change_effort(calls, curve, TASK.reference, PY, OLD_TESTS) == 300


def test_instruction_files_count_as_read(tmp_path):
    (tmp_path / "CLAUDE.md").write_text("x" * 4_000)  # loaded into the extender's context unasked
    curve = Curve(("t",), (CurvePoint(1, frozenset(["t"]), OLD_TESTS),))
    assert change_effort([bash(400)], curve, tmp_path, PY, OLD_TESTS) == 1_100
