"""Hidden tests: execution trace."""

import json
import subprocess


def run(argv, payload, *flags):
    res = subprocess.run([*argv, *flags], input=json.dumps(payload), capture_output=True,
                         text=True, timeout=10)
    return res.returncode, json.loads(res.stdout)


def req(*steps, dataset=None):
    return {"pipeline": {"steps": list(steps)}, "dataset": dataset if dataset is not None else []}


def e(path, op, rows_in, rows_out):
    return {"path": path, "op": op, "rows_in": rows_in, "rows_out": rows_out}


ROWS = [{"id": i, "x": x} for i, x in enumerate([1, 7, -1, 3, 12])]


def test_linear_pipeline(entrypoint_argv):
    payload = req({"op": "filter", "where": "x > 0"},
                  {"op": "map", "as": "y", "expr": "x * 2"},
                  {"op": "rename", "from": "y", "to": "double"},
                  {"op": "select", "columns": ["id", "double"]},
                  {"op": "limit", "n": 2}, dataset=ROWS)
    code, out = run(entrypoint_argv, payload, "--execute", "--trace")
    assert code == 0, out
    assert out["data"] == [{"id": 0, "double": 2}, {"id": 1, "double": 14}]
    assert out["metrics"] == {"rows_in": 5, "rows_out": 2}
    assert out["trace"] == [
        e("pipeline.steps[0]", "filter", 5, 4),
        e("pipeline.steps[1]", "map", 4, 4),
        e("pipeline.steps[2]", "rename", 4, 4),
        e("pipeline.steps[3]", "select", 4, 4),
        e("pipeline.steps[4]", "limit", 4, 2),
    ]


def test_spec_example(entrypoint_argv):
    payload = req({"op": "filter", "where": "x > 0"},
                  {"op": "branch", "branches": [
                      {"when": "x > 5", "steps": [{"op": "map", "as": "big", "expr": "true"}]},
                      {"when": "x > 100", "steps": [{"op": "limit", "n": 1}]},
                      {"when": "otherwise", "steps": []}]},
                  {"op": "limit", "n": 2},
                  dataset=[{"x": 1}, {"x": 7}, {"x": -1}, {"x": 3}])
    code, out = run(entrypoint_argv, payload, "--execute", "--trace")
    assert code == 0, out
    assert out["data"] == [{"x": 7, "big": True}, {"x": 1}]
    assert out["trace"] == [
        e("pipeline.steps[0]", "filter", 4, 3),
        e("pipeline.steps[1]", "branch", 3, 3),
        e("pipeline.steps[1].branches[0].steps[0]", "map", 1, 1),
        e("pipeline.steps[1].branches[1].steps[0]", "limit", 0, 0),
        e("pipeline.steps[2]", "limit", 3, 2),
    ]


def test_nested_branches(entrypoint_argv):
    payload = req({"op": "branch", "branches": [
        {"when": "x > 5", "steps": [
            {"op": "branch", "branches": [
                {"when": "x > 10", "steps": [{"op": "map", "as": "tier", "expr": "2"}]},
                {"when": "otherwise", "steps": [{"op": "map", "as": "tier", "expr": "1"},
                                                {"op": "limit", "n": 5}]}]},
            {"op": "select", "columns": ["id", "tier"]}]},
        {"when": "otherwise", "steps": [{"op": "filter", "where": "x > 0"}]}]}, dataset=ROWS)
    code, out = run(entrypoint_argv, payload, "--execute", "--trace")
    assert code == 0, out
    assert out["data"] == [{"id": 4, "tier": 2}, {"id": 1, "tier": 1},
                           {"id": 0, "x": 1}, {"id": 3, "x": 3}]
    assert out["trace"] == [
        e("pipeline.steps[0]", "branch", 5, 4),
        e("pipeline.steps[0].branches[0].steps[0]", "branch", 2, 2),
        e("pipeline.steps[0].branches[0].steps[0].branches[0].steps[0]", "map", 1, 1),
        e("pipeline.steps[0].branches[0].steps[0].branches[1].steps[0]", "map", 1, 1),
        e("pipeline.steps[0].branches[0].steps[0].branches[1].steps[1]", "limit", 1, 1),
        e("pipeline.steps[0].branches[0].steps[1]", "select", 2, 2),
        e("pipeline.steps[0].branches[1].steps[0]", "filter", 3, 2),
    ]


def test_empty_branch_steps_still_listed(entrypoint_argv):
    payload = req({"op": "branch", "branches": [
        {"when": "x > 1000", "steps": [{"op": "map", "as": "y", "expr": "1"},
                                       {"op": "select", "columns": ["y"]}]},
        {"when": "otherwise", "steps": [{"op": "limit", "n": 1}]}]}, dataset=ROWS)
    code, out = run(entrypoint_argv, payload, "--execute", "--trace")
    assert code == 0, out
    assert out["trace"] == [
        e("pipeline.steps[0]", "branch", 5, 1),
        e("pipeline.steps[0].branches[0].steps[0]", "map", 0, 0),
        e("pipeline.steps[0].branches[0].steps[1]", "select", 0, 0),
        e("pipeline.steps[0].branches[1].steps[0]", "limit", 5, 1),
    ]


def test_op_names_normalized(entrypoint_argv):
    payload = req({"op": " FILTER ", "where": "x > 2"}, {"op": "Limit", "n": 10}, dataset=ROWS)
    code, out = run(entrypoint_argv, payload, "--execute", "--trace")
    assert code == 0, out
    assert out["trace"] == [e("pipeline.steps[0]", "filter", 5, 3),
                            e("pipeline.steps[1]", "limit", 3, 3)]


def test_empty_pipeline(entrypoint_argv):
    code, out = run(entrypoint_argv, req(dataset=ROWS), "--execute", "--trace")
    assert code == 0, out
    assert out["trace"] == []
    assert out["metrics"] == {"rows_in": 5, "rows_out": 5}


def test_execute_without_trace_unchanged(entrypoint_argv):
    code, out = run(entrypoint_argv, req({"op": "limit", "n": 1}, dataset=ROWS), "--execute")
    assert code == 0
    assert out == {"status": "ok", "data": [{"id": 0, "x": 1}],
                   "metrics": {"rows_in": 5, "rows_out": 1}}


def test_trace_without_execute_ignored(entrypoint_argv):
    code, out = run(entrypoint_argv, req({"op": "Limit", "n": 1}, dataset=ROWS), "--trace")
    assert code == 0
    assert out == {"status": "ok", "normalized": {"steps": [{"op": "limit", "n": 1}]}}


def test_error_has_no_trace(entrypoint_argv):
    payload = req({"op": "limit", "n": 3},
                  {"op": "branch", "branches": [
                      {"when": "otherwise", "steps": [{"op": "select", "columns": ["nope"]}]}]},
                  dataset=ROWS)
    code, out = run(entrypoint_argv, payload, "--execute", "--trace")
    assert code == 1
    assert out["status"] == "error"
    assert out["error_code"] == "MISSING_COLUMN"
    assert out["path"] == "pipeline.steps[1].branches[0].steps[0].columns[0]"
    assert "trace" not in out
