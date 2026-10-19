"""Hidden tests: string field limits."""

import json
import subprocess

import pytest

L65 = "c" * 65
L64 = "c" * 64


def run(argv, payload, execute=False):
    cmd = [*argv, "--execute"] if execute else argv
    res = subprocess.run(cmd, input=json.dumps(payload), capture_output=True, text=True, timeout=10)
    return res.returncode, json.loads(res.stdout)


def req(*steps, dataset=None):
    return {"pipeline": {"steps": list(steps)}, "dataset": dataset or []}


def branch(*branches, **extra):
    return {"op": "branch", "branches": list(branches), **extra}


# A valid expression longer than 64 characters.
LONG_EXPR = "x + x + x + x + x + x + x + x + x + x + x + x + x + x + x + x + x > 0"
# A valid expression of exactly 64 characters.
EXPR_64 = "x + " * 14 + "x > 1000"
assert len(LONG_EXPR) > 64 and len(EXPR_64) == 64

CASES = {
    "select_column": (req({"op": "select", "columns": ["id", L65]}), "pipeline.steps[0].columns[1]"),
    "filter_where": (req({"op": "filter", "where": LONG_EXPR}), "pipeline.steps[0].where"),
    "map_as": (req({"op": "map", "as": L65, "expr": "1"}), "pipeline.steps[0].as"),
    "map_expr": (req({"op": "select", "columns": ["x"]}, {"op": "map", "as": "y", "expr": LONG_EXPR}),
                 "pipeline.steps[1].expr"),
    "rename_from": (req({"op": "rename", "from": L65, "to": "b"}), "pipeline.steps[0].from"),
    "rename_to": (req({"op": "rename", "from": "a", "to": L65}), "pipeline.steps[0].to"),
    "rename_mapping_value": (req({"op": "rename", "mapping": {"a": L65}}), "pipeline.steps[0].mapping.a"),
    "op_too_long": (req({"op": L65}), "pipeline.steps[0].op"),
    "branch_id": (req(branch({"id": L65, "when": "x > 1", "steps": []})), "pipeline.steps[0].branches[0].id"),
    "branch_when": (req(branch({"when": "x > 1", "steps": []}, {"when": LONG_EXPR, "steps": []})),
                    "pipeline.steps[0].branches[1].when"),
    "merge_strategy": (req(branch({"when": "x > 1", "steps": []}, merge={"strategy": L65})),
                       "pipeline.steps[0].merge.strategy"),
    "nested_map_as": (req({"op": "limit", "n": 5},
                          branch({"when": "x > 1", "steps": []},
                                 {"when": "otherwise", "steps": [{"op": "limit", "n": 1},
                                                                  {"op": "map", "as": L65, "expr": "1"}]})),
                      "pipeline.steps[1].branches[1].steps[1].as"),
    "deeply_nested_column": (req(branch({"when": "x > 1", "steps": [
        branch({"when": "x > 2", "steps": [{"op": "select", "columns": [L65]}]})]})),
        "pipeline.steps[0].branches[0].steps[0].branches[0].steps[0].columns[0]"),
    "control_char_as": (req({"op": "map", "as": "a\u0001b", "expr": "1"}), "pipeline.steps[0].as"),
    "control_char_newline_where": (req({"op": "filter", "where": "x > 1\n"}), "pipeline.steps[0].where"),
    "control_char_tab_column": (req({"op": "select", "columns": ["a\tb"]}), "pipeline.steps[0].columns[0]"),
    "control_char_del_rename": (req({"op": "rename", "mapping": {"a": "b\u007f"}}), "pipeline.steps[0].mapping.a"),
}


@pytest.mark.parametrize("name", sorted(CASES))
def test_violation(entrypoint_argv, name):
    payload, path = CASES[name]
    code, out = run(entrypoint_argv, payload)
    assert code == 1
    assert out["status"] == "error"
    assert out["error_code"] == "SCHEMA_VALIDATION_FAILED"
    assert out["path"] == path
    assert out["message"].startswith("ETL_ERROR: ")


def test_violation_with_execute(entrypoint_argv):
    payload, path = CASES["nested_map_as"]
    code, out = run(entrypoint_argv, payload, execute=True)
    assert code == 1
    assert (out["error_code"], out["path"]) == ("SCHEMA_VALIDATION_FAILED", path)


def test_exactly_64_is_valid(entrypoint_argv):
    payload = req({"op": "select", "columns": [L64]},
                  {"op": "rename", "mapping": {L64: "y" * 64}},
                  dataset=[{L64: 5}])
    code, out = run(entrypoint_argv, payload, execute=True)
    assert code == 0, out
    assert out["data"] == [{"y" * 64: 5}]


def test_64_char_expression_valid(entrypoint_argv):
    payload = req({"op": "map", "as": "z", "expr": EXPR_64}, dataset=[{"x": 100}])
    code, out = run(entrypoint_argv, payload, execute=True)
    assert code == 0, out
    assert out["data"] == [{"x": 100, "z": True}]
