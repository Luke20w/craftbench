"""The effort rules in effort.py, each of which closes a gap an experiment found."""

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
    cat = ToolCall("Bash", {"command": "cat etl_pipeline.py"}, 4_000)  # printing code is reading it
    assert read_weight(cat, TASK.mutants / "golfed", PY) == pytest.approx(1.895, abs=0.01)
    # globs, directories and `cd` all lead to the code a command prints
    for command in ("cat *", "cd /x/code && grep -rn def .", "cd / && cat x/code/etl_pipeline.py | head"):
        assert read_weight(ToolCall("Bash", {"command": command}, 4_000), TASK.mutants / "golfed", PY) == \
            pytest.approx(1.895, abs=0.01)
    assert read_weight(ToolCall("Glob", {"pattern": "**/*"}, 4_000), TASK.mutants / "golfed", PY) == 1.0  # just names


def test_snapshots_skip_failed_calls():
    # Snapshot 2 is taken after the 2nd *successful* call, i.e. after transcript call 3.
    calls = [bash(400), ToolCall("Edit", {}, 400, is_error=True), bash(400), bash(400)]
    curve = Curve(("t",), (CurvePoint(2, frozenset(["t"]), OLD_TESTS),))
    assert change_effort(calls, curve, TASK.reference, PY, OLD_TESTS) == 300


def test_instruction_files_count_as_read(tmp_path):
    (tmp_path / "CLAUDE.md").write_text("x" * 4_000)  # loaded into the extender's context unasked
    curve = Curve(("t",), (CurvePoint(1, frozenset(["t"]), OLD_TESTS),))
    assert change_effort([bash(400)], curve, tmp_path, PY, OLD_TESTS) == 1_100


def test_tests_that_already_pass_are_not_charged():
    assert effort((2, ["a", "b"], 100), tests=("a", "b")) == 200
    curve = Curve(("a", "b"), (CurvePoint(2, frozenset(["a", "b"]), OLD_TESTS),))
    assert change_effort(CALLS, curve, TASK.reference, PY, OLD_TESTS, frozenset({"a"})) == 200
    # all of them already passing: the code anticipated a hidden change, which shouldn't pay
    assert change_effort(CALLS, curve, TASK.reference, PY, OLD_TESTS, frozenset({"a", "b"})) == FAILURE_TOKENS


def test_prose_and_padding_never_make_reading_cheaper(tmp_path):
    (tmp_path / "code.py").write_text((TASK.mutants / "golfed" / "etl_pipeline.py").read_text())
    (tmp_path / "manual.py").write_text('"""' + "How this works. " * 5_000 + '"""\n')  # no syntax nodes at all
    cat_manual = ToolCall("Bash", {"command": "cat manual.py"}, 4_000)
    cat_code = ToolCall("Bash", {"command": "cd /x/code && sed -n 1,200p code.py"}, 4_000)
    assert read_weight(cat_manual, tmp_path, PY) == 1.0  # docs cost their tokens, not nothing
    # weighted by the file it printed, not the codebase average the manual drags down
    assert read_weight(cat_code, tmp_path, PY) == pytest.approx(1.895, abs=0.01)
    assert read_weight(ToolCall("Grep", {"pattern": "def"}, 4_000), tmp_path, PY) == pytest.approx(1.895, abs=0.01)


def test_unparseable_source_still_counts_as_code(tmp_path):
    src = (TASK.mutants / "golfed" / "etl_pipeline.py").read_text()
    (tmp_path / "etl_pipeline.py").write_text("%% not python %%\n" + src)  # stripped at import by an import hook
    read = ToolCall("Read", {"file_path": "/x/code/etl_pipeline.py"}, 4_000)
    golfed = read_weight(read, TASK.mutants / "golfed", PY)
    assert read_weight(read, tmp_path, PY) == pytest.approx(golfed, rel=0.05)  # as dense as the code it hides


def test_code_is_code_whatever_the_file_is_called(tmp_path):
    (tmp_path / "logic.txt").write_text((TASK.mutants / "golfed" / "etl_pipeline.py").read_text())  # loaded by a hook
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "etl"\nversion = "1.0"\n')  # parses, but isn't code

    def read(name):
        return ToolCall("Read", {"file_path": f"/x/code/{name}"}, 4_000)

    assert read_weight(read("logic.txt"), tmp_path, PY) == pytest.approx(1.895, abs=0.01)
    assert read_weight(read("pyproject.toml"), tmp_path, PY) == 1.0
