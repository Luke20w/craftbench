"""Hidden tests: string field limits on every field of all 52 operations."""

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
    # milestones 4–7, first batch
    "drop_column": (req({"op": "drop", "columns": ["a", L65]}), "pipeline.steps[0].columns[1]"),
    "distinct_column": (req({"op": "distinct", "columns": [L65]}), "pipeline.steps[0].columns[0]"),
    "sort_by": (req({"op": "sort", "by": L65}), "pipeline.steps[0].by"),
    "fill_value": (req({"op": "fill", "column": "a", "value": LONG_EXPR}), "pipeline.steps[0].value"),
    "fill_column_ctrl": (req({"op": "fill", "column": "a\u0002", "value": "1"}), "pipeline.steps[0].column"),
    "cast_to": (req({"op": "cast", "column": "a", "to": "int" + " " * 70}), "pipeline.steps[0].to"),
    "round_column": (req({"op": "round", "column": L65}), "pipeline.steps[0].column"),
    "concat_sep_tab": (req({"op": "concat", "as": "k", "columns": ["a"], "sep": "\t"}), "pipeline.steps[0].sep"),
    "concat_as": (req({"op": "concat", "as": L65, "columns": ["a"]}), "pipeline.steps[0].as"),
    "split_into": (req({"op": "split", "column": "a", "sep": ",", "into": ["p", L65]}), "pipeline.steps[0].into[1]"),
    "split_sep": (req({"op": "split", "column": "a", "sep": "," * 65, "into": ["p"]}), "pipeline.steps[0].sep"),
    "text_fn": (req({"op": "text", "columns": ["a"], "fn": "upper\n"}), "pipeline.steps[0].fn"),
    "assert_message": (req({"op": "assert", "where": "x > 1", "message": "m" * 65}), "pipeline.steps[0].message"),
    "coalesce_expr": (req({"op": "coalesce", "as": "v", "exprs": ["a", LONG_EXPR]}), "pipeline.steps[0].exprs[1]"),
    "explode_column": (req({"op": "explode", "column": L65}), "pipeline.steps[0].column"),
    "nested_new_op": (req(branch({"when": "x > 1", "steps": [branch({"when": "otherwise", "steps": [
        {"op": "limit", "n": 1}, {"op": "text", "columns": ["ok", "b\u0007"], "fn": "trim"}]})]})),
        "pipeline.steps[0].branches[0].steps[0].branches[0].steps[1].columns[1]"),
    # milestones 4–7, second batch
    "group_count_by": (req({"op": "group_count", "by": ["a", L65], "as": "n"}), "pipeline.steps[0].by[1]"),
    "summarize_metric_as": (req({"op": "summarize", "metrics": [{"as": L65, "fn": "count"}]}), "pipeline.steps[0].metrics[0].as"),
    "summarize_metric_fn_ctrl": (req({"op": "summarize", "metrics": [{"as": "n", "fn": "count"}, {"as": "s", "fn": "sum\u0003"}]}),
                                 "pipeline.steps[0].metrics[1].fn"),
    "summarize_metric_column": (req({"op": "summarize", "metrics": [{"as": "s", "fn": "sum", "column": L65}]}),
                                "pipeline.steps[0].metrics[0].column"),
    "lookup_table_value": (req({"op": "lookup", "column": "c", "as": "d", "table": {"k": L65}}), "pipeline.steps[0].table.k"),
    "lookup_default": (req({"op": "lookup", "column": "c", "as": "d", "table": {}, "default": "x\ty"}), "pipeline.steps[0].default"),
    "set_value": (req({"op": "set", "column": "c", "value": L65}), "pipeline.steps[0].value"),
    "ensure_column": (req({"op": "ensure", "columns": [L65]}), "pipeline.steps[0].columns[0]"),
    "prefix_prefix": (req({"op": "prefix", "prefix": "p\n"}), "pipeline.steps[0].prefix"),
    "replace_with": (req({"op": "replace", "column": "c", "find": "a", "with": "b\u001f"}), "pipeline.steps[0].with"),
    "regex_pattern": (req({"op": "regex_extract", "column": "c", "pattern": "a?" * 33, "as": "x"}), "pipeline.steps[0].pattern"),
    "pad_side": (req({"op": "pad", "column": "c", "width": 3, "side": "left" + " " * 61}), "pipeline.steps[0].side"),
    "math_fn": (req({"op": "math", "column": "c", "fn": "abs\u007f"}), "pipeline.steps[0].fn"),
    "take_while_where": (req({"op": "take_while", "where": LONG_EXPR}), "pipeline.steps[0].where"),
    "lag_default": (req({"op": "lag", "column": "c", "as": "d", "default": L65}), "pipeline.steps[0].default"),
    "date_part_as": (req({"op": "date_part", "column": "c", "part": "year", "as": L65}), "pipeline.steps[0].as"),
    "nested_summarize": (req({"op": "limit", "n": 3}, branch({"when": "otherwise", "steps": [
        {"op": "summarize", "by": ["c"], "metrics": [{"as": "n", "fn": "count"}, {"as": "a\u0001", "fn": "count"}]}]})),
        "pipeline.steps[1].branches[0].steps[0].metrics[1].as"),
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


def test_new_ops_64_valid(entrypoint_argv):
    payload = req({"op": "concat", "as": "k" * 64, "columns": [L64], "sep": "-" * 64},
                  {"op": "assert", "where": EXPR_64, "message": "m" * 64},
                  {"op": "drop", "columns": [L64]}, dataset=[{L64: "v", "x": 2000}])
    code, out = run(entrypoint_argv, payload, execute=True)
    assert code == 0, out
    assert out["data"] == [{"x": 2000, "k" * 64: "v"}]


def test_keys_and_append_rows_not_limited(entrypoint_argv):
    payload = req({"op": "lookup", "column": "k", "as": "v", "table": {L65: "short"}},
                  {"op": "append", "rows": [{L65: "z" * 80}]}, dataset=[{"k": L65}])
    code, out = run(entrypoint_argv, payload, execute=True)
    assert code == 0, out
    assert out["data"] == [{"k": L65, "v": "short"}, {L65: "z" * 80}]


def test_new_ops_64_valid(entrypoint_argv):
    payload = req({"op": "set", "column": "s", "value": "v" * 64},
                  {"op": "summarize", "by": ["s"], "metrics": [{"as": "n" * 64, "fn": "count"}]}, dataset=[{"x": 1}])
    code, out = run(entrypoint_argv, payload, execute=True)
    assert code == 0, out
    assert out["data"] == [{"s": "v" * 64, "n" * 64: 1}]
