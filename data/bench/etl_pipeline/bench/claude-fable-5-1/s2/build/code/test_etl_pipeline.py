"""CLI-level tests for etl_pipeline.py.

Run with:  python3 -m unittest -v test_etl_pipeline
"""

import json
import os
import subprocess
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ENTRY = os.path.join(HERE, "etl_pipeline.py")


def run_cli(payload, raw=None, args=()):
    text = raw if raw is not None else json.dumps(payload)
    proc = subprocess.run(
        [sys.executable, ENTRY, *args],
        input=text,
        capture_output=True,
        text=True,
        cwd=HERE,
    )
    return proc.returncode, json.loads(proc.stdout)


def request(steps, dataset=None, **extra):
    body = {"pipeline": {"steps": steps}, "dataset": dataset if dataset is not None else []}
    body.update(extra)
    return body


class SpecExamples(unittest.TestCase):
    def test_example_1_casing_and_rename(self):
        code, out = run_cli(request([
            {"op": "Select", "columns": ["id", "price", "category"]},
            {"op": "rename", "from": "price", "to": "usd_price"},
        ]))
        self.assertEqual(code, 0)
        self.assertEqual(out, {
            "status": "ok",
            "normalized": {"steps": [
                {"op": "select", "columns": ["id", "price", "category"]},
                {"op": "rename", "mapping": {"price": "usd_price"}},
            ]},
        })

    def test_example_2_unknown_op(self):
        code, out = run_cli(request([{"op": "TRANSPOSE"}]))
        self.assertEqual(code, 1)
        self.assertEqual(out, {
            "status": "error",
            "error_code": "UNKNOWN_OP",
            "message": "ETL_ERROR: unsupported op 'transpose'",
            "path": "pipeline.steps[0].op",
        })

    def test_example_3_empty_pipeline(self):
        code, out = run_cli(request([]))
        self.assertEqual(code, 0)
        self.assertEqual(out, {"status": "ok", "normalized": {"steps": []}})


class Normalization(unittest.TestCase):
    def test_trimming_and_key_order(self):
        code, out = run_cli(request([
            {"op": " Map ", "expr": " qty * price ", "as": " total ", "junk": 1},
            {"op": "FILTER", "where": "  total > 10 and not (qty == 0) ", "x": "y"},
            {"op": "limit", "n": 5, "extra": True},
        ]))
        self.assertEqual(code, 0)
        steps = out["normalized"]["steps"]
        self.assertEqual(steps[0], {"op": "map", "as": "total", "expr": "qty * price"})
        self.assertEqual(list(steps[0].keys()), ["op", "as", "expr"])
        self.assertEqual(steps[1], {"op": "filter", "where": "total > 10 and not (qty == 0)"})
        self.assertEqual(steps[2], {"op": "limit", "n": 5})

    def test_column_names_preserved_exactly(self):
        code, out = run_cli(request([{"op": "select", "columns": [" id ", "a b"]}]))
        self.assertEqual(code, 0)
        self.assertEqual(out["normalized"]["steps"][0]["columns"], [" id ", "a b"])

    def test_rename_from_to_trimmed_mapping_preserved(self):
        code, out = run_cli(request([
            {"op": "rename", "from": " a ", "to": " b "},
            {"op": "rename", "mapping": {" x ": " y "}},
        ]))
        self.assertEqual(code, 0)
        steps = out["normalized"]["steps"]
        self.assertEqual(steps[0], {"op": "rename", "mapping": {"a": "b"}})
        self.assertEqual(steps[1], {"op": "rename", "mapping": {" x ": " y "}})

    def test_unknown_top_level_keys_ignored(self):
        code, out = run_cli(request([], something="else", version=2))
        self.assertEqual(code, 0)
        self.assertEqual(out["status"], "ok")

    def test_limit_zero_ok(self):
        code, out = run_cli(request([{"op": "limit", "n": 0}]))
        self.assertEqual(code, 0)
        self.assertEqual(out["normalized"]["steps"][0], {"op": "limit", "n": 0})


class SchemaErrors(unittest.TestCase):
    def assert_error(self, payload, code, path, raw=None):
        rc, out = run_cli(payload, raw=raw)
        self.assertEqual(rc, 1, out)
        self.assertEqual(out["status"], "error")
        self.assertEqual(out["error_code"], code, out)
        self.assertEqual(out["path"], path, out)
        self.assertTrue(out["message"].startswith("ETL_ERROR: "), out)
        return out

    def test_invalid_json(self):
        self.assert_error(None, "SCHEMA_VALIDATION_FAILED", "", raw="{not json")

    def test_root_not_object(self):
        self.assert_error([], "SCHEMA_VALIDATION_FAILED", "")

    def test_missing_pipeline(self):
        self.assert_error({"dataset": []}, "SCHEMA_VALIDATION_FAILED", "pipeline")

    def test_steps_missing_or_not_array(self):
        self.assert_error({"pipeline": {}, "dataset": []},
                          "SCHEMA_VALIDATION_FAILED", "pipeline.steps")
        self.assert_error({"pipeline": {"steps": {}}, "dataset": []},
                          "SCHEMA_VALIDATION_FAILED", "pipeline.steps")

    def test_dataset_missing_or_bad(self):
        self.assert_error({"pipeline": {"steps": []}}, "SCHEMA_VALIDATION_FAILED", "dataset")
        self.assert_error({"pipeline": {"steps": []}, "dataset": {}},
                          "SCHEMA_VALIDATION_FAILED", "dataset")
        self.assert_error({"pipeline": {"steps": []}, "dataset": [{}, 1]},
                          "SCHEMA_VALIDATION_FAILED", "dataset[1]")

    def test_step_not_object(self):
        self.assert_error(request(["select"]), "SCHEMA_VALIDATION_FAILED", "pipeline.steps[0]")

    def test_missing_or_bad_op(self):
        self.assert_error(request([{"columns": ["a"]}]),
                          "SCHEMA_VALIDATION_FAILED", "pipeline.steps[0].op")
        self.assert_error(request([{"op": 3}]),
                          "SCHEMA_VALIDATION_FAILED", "pipeline.steps[0].op")
        self.assert_error(request([{"op": "   "}]),
                          "SCHEMA_VALIDATION_FAILED", "pipeline.steps[0].op")

    def test_select_columns_errors(self):
        self.assert_error(request([{"op": "select"}]),
                          "SCHEMA_VALIDATION_FAILED", "pipeline.steps[0].columns")
        self.assert_error(request([{"op": "select", "columns": "id"}]),
                          "SCHEMA_VALIDATION_FAILED", "pipeline.steps[0].columns")
        self.assert_error(request([{"op": "limit", "n": 1}, {"op": "select", "columns": ["id", 2]}]),
                          "SCHEMA_VALIDATION_FAILED", "pipeline.steps[1].columns")

    def test_filter_and_map_errors(self):
        self.assert_error(request([{"op": "filter"}]),
                          "SCHEMA_VALIDATION_FAILED", "pipeline.steps[0].where")
        self.assert_error(request([{"op": "filter", "where": "   "}]),
                          "SCHEMA_VALIDATION_FAILED", "pipeline.steps[0].where")
        self.assert_error(request([{"op": "map", "expr": "a + 1"}]),
                          "SCHEMA_VALIDATION_FAILED", "pipeline.steps[0].as")
        self.assert_error(request([{"op": "map", "as": " ", "expr": "a + 1"}]),
                          "SCHEMA_VALIDATION_FAILED", "pipeline.steps[0].as")
        self.assert_error(request([{"op": "map", "as": "t"}]),
                          "SCHEMA_VALIDATION_FAILED", "pipeline.steps[0].expr")

    def test_rename_errors(self):
        self.assert_error(request([{"op": "rename"}]),
                          "SCHEMA_VALIDATION_FAILED", "pipeline.steps[0]")
        self.assert_error(request([{"op": "rename", "from": "a"}]),
                          "SCHEMA_VALIDATION_FAILED", "pipeline.steps[0].to")
        self.assert_error(request([{"op": "rename", "from": " ", "to": "b"}]),
                          "SCHEMA_VALIDATION_FAILED", "pipeline.steps[0].from")
        self.assert_error(request([{"op": "rename", "mapping": []}]),
                          "SCHEMA_VALIDATION_FAILED", "pipeline.steps[0].mapping")
        self.assert_error(request([{"op": "rename", "mapping": {"a": 1}}]),
                          "SCHEMA_VALIDATION_FAILED", "pipeline.steps[0].mapping")

    def test_limit_errors(self):
        self.assert_error(request([{"op": "limit"}]),
                          "SCHEMA_VALIDATION_FAILED", "pipeline.steps[0].n")
        self.assert_error(request([{"op": "limit", "n": -1}]),
                          "SCHEMA_VALIDATION_FAILED", "pipeline.steps[0].n")
        self.assert_error(request([{"op": "limit", "n": "5"}]),
                          "SCHEMA_VALIDATION_FAILED", "pipeline.steps[0].n")
        self.assert_error(request([{"op": "limit", "n": 2.5}]),
                          "SCHEMA_VALIDATION_FAILED", "pipeline.steps[0].n")
        self.assert_error(request([{"op": "limit", "n": True}]),
                          "SCHEMA_VALIDATION_FAILED", "pipeline.steps[0].n")

    def test_first_error_wins(self):
        out = self.assert_error(request([{"op": "limit", "n": 1}, {"op": "nope"}, {"op": "limit"}]),
                                "UNKNOWN_OP", "pipeline.steps[1].op")
        self.assertEqual(out["message"], "ETL_ERROR: unsupported op 'nope'")


class Expressions(unittest.TestCase):
    def assert_ok(self, expr):
        code, out = run_cli(request([{"op": "filter", "where": expr}]))
        self.assertEqual(code, 0, out)

    def assert_bad(self, expr, field="where", op="filter"):
        step = {"op": op, field: expr}
        if op == "map":
            step["as"] = "x"
        code, out = run_cli(request([step]))
        self.assertEqual(code, 1, out)
        self.assertEqual(out["error_code"], "BAD_EXPR", out)
        self.assertEqual(out["path"], f"pipeline.steps[0].{field}", out)

    def test_valid_expressions(self):
        for expr in [
            "qty * price",
            "a + b - c / d",
            "(a + b) * (c - d)",
            "price >= 10 and qty < 5 or not active",
            "name == 'bob' and city != \"NYC\"",
            "-x + 1",
            "x == -1",
            "1.5 * qty",
            "not not a",
            "a == true or b == false",
            "((a))",
            "AND_x > 1",
            "a && b || !c",
            "!(a == b) && x > -1",
            "a>-1",
        ]:
            with self.subTest(expr=expr):
                self.assert_ok(expr)

    def test_bad_expressions(self):
        for expr in [
            "a ^^ b",
            "a ^ b",
            "a ** b",
            "a + * b",
            "a +",
            "* a",
            "(a + b",
            "a + b)",
            "a b",
            "a == == b",
            "a & b",
            "a || || b",
            "a = b",
            "a === b",
            "'unterminated",
            "a > > b",
            "and",
            "a and",
            "1.2.3",
            "a %% b",
        ]:
            with self.subTest(expr=expr):
                self.assert_bad(expr)

    def test_bad_map_expr_path(self):
        self.assert_bad("qty ^^ price", field="expr", op="map")


class MissingColumns(unittest.TestCase):
    DATA = [{"id": 1, "price": 2.0, "qty": 3}, {"id": 2, "price": 1.0, "qty": 1, "note": "x"}]

    def test_columns_checked_against_dataset(self):
        rc, out = run_cli(request([{"op": "select", "columns": ["id", "nope"]}], self.DATA))
        self.assertEqual(rc, 1)
        self.assertEqual(out["error_code"], "MISSING_COLUMN")
        self.assertEqual(out["path"], "pipeline.steps[0].columns")

    def test_columns_tracked_through_pipeline(self):
        rc, out = run_cli(request([
            {"op": "map", "as": "total", "expr": "price * qty"},
            {"op": "rename", "from": "total", "to": "amount"},
            {"op": "select", "columns": ["id", "amount", "note"]},
            {"op": "filter", "where": "amount > 1"},
        ], self.DATA))
        self.assertEqual(rc, 0, out)

    def test_selected_out_column_is_missing(self):
        rc, out = run_cli(request([
            {"op": "select", "columns": ["id"]},
            {"op": "filter", "where": "price > 1"},
        ], self.DATA))
        self.assertEqual(rc, 1)
        self.assertEqual(out["error_code"], "MISSING_COLUMN")
        self.assertEqual(out["path"], "pipeline.steps[1].where")

    def test_rename_unknown_source(self):
        rc, out = run_cli(request([{"op": "rename", "mapping": {"zzz": "y"}}], self.DATA))
        self.assertEqual(rc, 1)
        self.assertEqual(out["error_code"], "MISSING_COLUMN")
        self.assertEqual(out["path"], "pipeline.steps[0].mapping")

    def test_empty_dataset_skips_column_checks(self):
        rc, out = run_cli(request([{"op": "select", "columns": ["anything"]}], []))
        self.assertEqual(rc, 0)


def run_exec(steps, dataset):
    return run_cli(request(steps, dataset), args=["--execute"])


class ExecuteFlag(unittest.TestCase):
    STEPS = [{"op": "map", "as": "t", "expr": "a * 2"}]
    DATA = [{"a": 1}]

    def test_default_is_normalize_only(self):
        code, out = run_cli(request(self.STEPS, self.DATA))
        self.assertEqual(code, 0)
        self.assertIn("normalized", out)
        self.assertNotIn("data", out)

    def test_execute_false_values(self):
        for args in (["--execute=false"], ["--execute", "0"], ["--execute=no"]):
            with self.subTest(args=args):
                code, out = run_cli(request(self.STEPS, self.DATA), args=args)
                self.assertEqual(code, 0)
                self.assertIn("normalized", out)

    def test_execute_true_values(self):
        for args in (["--execute"], ["--execute=true"], ["--execute", "1"]):
            with self.subTest(args=args):
                code, out = run_cli(request(self.STEPS, self.DATA), args=args)
                self.assertEqual(code, 0, out)
                self.assertEqual(set(out), {"status", "data", "metrics"})
                self.assertEqual(out["data"], [{"a": 1, "t": 2}])
                self.assertEqual(out["metrics"], {"rows_in": 1, "rows_out": 1})


class ExecutionExamples(unittest.TestCase):
    def test_example_1_pipeline(self):
        code, out = run_exec([
            {"op": "select", "columns": ["id", "price", "qty"]},
            {"op": "map", "as": "total", "expr": "price * qty"},
            {"op": "filter", "where": "total >= 100"},
            {"op": "limit", "n": 2},
        ], [
            {"id": 1, "price": 12.5, "qty": 8},
            {"id": 2, "price": 5, "qty": 10},
            {"id": 3, "price": 40, "qty": 3},
            {"id": 4, "price": 20, "qty": 4},
        ])
        self.assertEqual(code, 0, out)
        self.assertEqual(out, {
            "status": "ok",
            "data": [
                {"id": 1, "price": 12.5, "qty": 8, "total": 100},
                {"id": 3, "price": 40, "qty": 3, "total": 120},
            ],
            "metrics": {"rows_in": 4, "rows_out": 2},
        })

    def test_example_2_missing_column(self):
        code, out = run_exec([{"op": "select", "columns": ["id", "price", "missing"]}],
                             [{"id": 1, "price": 9.5}])
        self.assertEqual(code, 1)
        self.assertEqual(out, {
            "status": "error",
            "error_code": "MISSING_COLUMN",
            "message": "ETL_ERROR: column 'missing' not found in row",
            "path": "pipeline.steps[0].columns[2]",
        })

    def test_example_3_bad_expr(self):
        code, out = run_exec([{"op": "map", "as": "bad", "expr": "price ** qty"}],
                             [{"price": 10, "qty": 2}])
        self.assertEqual(code, 1)
        self.assertEqual(out, {
            "status": "error",
            "error_code": "BAD_EXPR",
            "message": "ETL_ERROR: unsupported operator '**'",
            "path": "pipeline.steps[0].expr",
        })


class ExecutionSemantics(unittest.TestCase):
    def eval_expr(self, expr, row):
        code, out = run_exec([{"op": "map", "as": "r", "expr": expr}], [row])
        self.assertEqual(code, 0, out)
        return out["data"][0]["r"]

    def test_select_order_and_rows(self):
        code, out = run_exec([{"op": "select", "columns": ["b", "a"]}],
                             [{"a": 1, "b": 2, "c": 3}, {"a": 4, "b": 5}])
        self.assertEqual(code, 0)
        self.assertEqual([list(r) for r in out["data"]], [["b", "a"], ["b", "a"]])
        self.assertEqual(out["data"], [{"b": 2, "a": 1}, {"b": 5, "a": 4}])

    def test_select_checks_every_row(self):
        code, out = run_exec([{"op": "select", "columns": ["a"]}], [{"a": 1}, {"b": 2}])
        self.assertEqual(code, 1)
        self.assertEqual(out["error_code"], "MISSING_COLUMN")
        self.assertEqual(out["path"], "pipeline.steps[0].columns[0]")

    def test_map_overwrites_existing_field(self):
        code, out = run_exec([{"op": "map", "as": "a", "expr": "a + 1"}], [{"a": 1, "b": 0}])
        self.assertEqual(out["data"], [{"a": 2, "b": 0}])

    def test_rename_from_to_and_mapping(self):
        code, out = run_exec([
            {"op": "rename", "from": "a", "to": "x"},
            {"op": "rename", "mapping": {"b": "y", "c": "y"}},
        ], [{"a": 1, "b": 2, "c": 3}])
        self.assertEqual(code, 0, out)
        self.assertEqual(out["data"], [{"x": 1, "y": 3}])

    def test_rename_missing_source_paths(self):
        code, out = run_exec([{"op": "rename", "from": "zz", "to": "y"}], [{"a": 1}])
        self.assertEqual(out["error_code"], "MISSING_COLUMN")
        self.assertEqual(out["path"], "pipeline.steps[0].from")
        code, out = run_exec([{"op": "rename", "mapping": {"a": "x", "cost": "y"}}], [{"a": 1}])
        self.assertEqual(out["error_code"], "MISSING_COLUMN")
        self.assertEqual(out["message"], "ETL_ERROR: column 'cost' not found in row")
        self.assertEqual(out["path"], "pipeline.steps[0].mapping.cost")

    def test_limit_and_metrics(self):
        code, out = run_exec([{"op": "limit", "n": 0}], [{"a": 1}, {"a": 2}])
        self.assertEqual(out, {"status": "ok", "data": [], "metrics": {"rows_in": 2, "rows_out": 0}})
        code, out = run_exec([{"op": "limit", "n": 10}], [{"a": 1}, {"a": 2}])
        self.assertEqual(out["metrics"], {"rows_in": 2, "rows_out": 2})

    def test_empty_pipeline_passes_rows_through(self):
        code, out = run_exec([], [{"a": 1}])
        self.assertEqual(out, {"status": "ok", "data": [{"a": 1}], "metrics": {"rows_in": 1, "rows_out": 1}})

    def test_empty_dataset(self):
        code, out = run_exec([{"op": "select", "columns": ["anything"]}], [])
        self.assertEqual(out, {"status": "ok", "data": [], "metrics": {"rows_in": 0, "rows_out": 0}})

    def test_missing_identifier_is_null(self):
        self.assertIsNone(self.eval_expr("nope", {"a": 1}))
        self.assertIsNone(self.eval_expr("a + nope", {"a": 1}))

    def test_null_arithmetic_and_division_by_zero(self):
        self.assertIsNone(self.eval_expr("a / 0", {"a": 1}))
        self.assertIsNone(self.eval_expr("a * null", {"a": 1}))
        self.assertIsNone(self.eval_expr("-a", {"a": None}))

    def test_null_comparisons_false(self):
        row = {"a": None, "b": 1}
        for expr in ["a == null", "a != b", "a < b", "a >= b", "null == null"]:
            with self.subTest(expr=expr):
                self.assertIs(self.eval_expr(expr, row), False)

    def test_null_is_falsy(self):
        self.assertIs(self.eval_expr("!a", {"a": None}), True)
        self.assertIs(self.eval_expr("a || true", {"a": None}), True)
        self.assertIs(self.eval_expr("a && true", {"a": None}), False)
        code, out = run_exec([{"op": "filter", "where": "a"}], [{"a": None}, {"a": 1}, {"a": 0}])
        self.assertEqual(out["data"], [{"a": 1}])

    def test_type_mismatch_comparisons_false(self):
        row = {"n": 1, "s": "1", "b": True}
        for expr in ["n == s", "n < s", "b == n", "n == true", "b > false"]:
            with self.subTest(expr=expr):
                self.assertIs(self.eval_expr(expr, row), False)
        self.assertIs(self.eval_expr("n != s", row), False)
        self.assertIs(self.eval_expr("s == \"1\"", row), True)
        self.assertIs(self.eval_expr("s < \"2\"", row), True)

    def test_arithmetic_and_precedence(self):
        row = {"a": 2, "b": 3, "c": 4}
        self.assertEqual(self.eval_expr("a + b * c", row), 14)
        self.assertEqual(self.eval_expr("(a + b) * c", row), 20)
        self.assertEqual(self.eval_expr("c / a", row), 2)
        self.assertEqual(self.eval_expr("b / a", row), 1.5)
        self.assertEqual(self.eval_expr("12.5 * 8", row), 100)
        self.assertIs(self.eval_expr("a + b == 5 && c > 3", row), True)
        self.assertIs(self.eval_expr("a > b || c > b", row), True)
        self.assertIs(self.eval_expr("!(a > b) == true", row), True)
        self.assertEqual(self.eval_expr("\"x\" + \"y\"", row), "xy")

    def test_type_error_is_execution_failed(self):
        code, out = run_exec([{"op": "filter", "where": "s * 2 > 1"}], [{"s": "abc"}])
        self.assertEqual(code, 1)
        self.assertEqual(out["error_code"], "EXECUTION_FAILED")
        self.assertEqual(out["path"], "pipeline.steps[0].where")
        self.assertTrue(out["message"].startswith("ETL_ERROR: "))

    def test_input_dataset_not_mutated_between_steps(self):
        code, out = run_exec([
            {"op": "map", "as": "t", "expr": "a"},
            {"op": "select", "columns": ["t"]},
            {"op": "map", "as": "u", "expr": "a"},
        ], [{"a": 1}])
        self.assertEqual(out["data"], [{"t": 1, "u": None}])

    def test_schema_errors_still_reported_when_executing(self):
        code, out = run_exec([{"op": "limit", "n": -1}], [{"a": 1}])
        self.assertEqual(code, 1)
        self.assertEqual(out["error_code"], "SCHEMA_VALIDATION_FAILED")
        self.assertEqual(out["path"], "pipeline.steps[0].n")
        code, out = run_cli({"pipeline": {"steps": []}, "dataset": [1]}, args=["--execute"])
        self.assertEqual(out["path"], "dataset[0]")




class BranchStep(unittest.TestCase):
    EXAMPLE_1 = [{
        "op": "branch",
        "branches": [
            {"id": "cheap", "when": "price < 20",
             "steps": [{"op": "map", "as": "tag", "expr": '"cheap"'}]},
            {"id": "otherwise", "when": "otherwise",
             "steps": [{"op": "map", "as": "tag", "expr": '"premium"'}]},
        ],
        "merge": {"strategy": "concat"},
    }]
    EXAMPLE_1_DATA = [{"id": 1, "price": 10}, {"id": 2, "price": 25}, {"id": 3, "price": 5}]

    def assert_error(self, payload, code, path, args=()):
        rc, out = run_cli(payload, args=args)
        self.assertEqual(rc, 1, out)
        self.assertEqual(out["status"], "error")
        self.assertEqual(out["error_code"], code, out)
        self.assertEqual(out["path"], path, out)
        self.assertTrue(out["message"].startswith("ETL_ERROR: "), out)

    def test_example_1_routing_with_otherwise(self):
        code, out = run_cli(request(self.EXAMPLE_1, self.EXAMPLE_1_DATA), args=["--execute"])
        self.assertEqual(code, 0)
        self.assertEqual(out, {
            "status": "ok",
            "data": [
                {"id": 1, "price": 10, "tag": "cheap"},
                {"id": 3, "price": 5, "tag": "cheap"},
                {"id": 2, "price": 25, "tag": "premium"},
            ],
            "metrics": {"rows_in": 3, "rows_out": 3},
        })

    def test_example_2_error_path_inside_branch(self):
        steps = [{
            "op": "branch",
            "branches": [
                {"id": "s1", "when": "qty >= 1",
                 "steps": [{"op": "select", "columns": ["id", "missing"]}]},
                {"id": "otherwise", "when": "otherwise", "steps": []},
            ],
            "merge": {"strategy": "concat"},
        }]
        self.assert_error(request(steps, [{"id": 1, "qty": 2}]), "MISSING_COLUMN",
                          "pipeline.steps[0].branches[0].steps[0].columns[1]", args=["--execute"])
        # Normalize-only mode reports the containing field, as for top-level steps.
        self.assert_error(request(steps, [{"id": 1, "qty": 2}]), "MISSING_COLUMN",
                          "pipeline.steps[0].branches[0].steps[0].columns")

    def test_normalization(self):
        code, out = run_cli(request([{
            "op": " Branch ",
            "branches": [
                {"id": "cheap", "when": " price < 20 ",
                 "steps": [{"op": "MAP", "as": " tag ", "expr": '"cheap"', "x": 1}]},
                {"when": "Otherwise", "steps": []},
            ],
            "extra": True,
        }], [{"id": 1, "price": 10}]))
        self.assertEqual(code, 0)
        step = out["normalized"]["steps"][0]
        self.assertEqual(list(step.keys()), ["op", "branches", "merge"])
        self.assertEqual(step, {
            "op": "branch",
            "branches": [
                {"id": "cheap", "when": "price < 20",
                 "steps": [{"op": "map", "as": "tag", "expr": '"cheap"'}]},
                {"when": "otherwise", "steps": []},
            ],
            "merge": {"strategy": "concat"},
        })

    def test_rows_without_match_are_dropped(self):
        code, out = run_cli(request(
            [{"op": "branch", "branches": [{"when": "price < 20", "steps": []}]}],
            [{"id": 1, "price": 10}, {"id": 2, "price": 25}],
        ), args=["--execute"])
        self.assertEqual(code, 0)
        self.assertEqual(out["data"], [{"id": 1, "price": 10}])
        self.assertEqual(out["metrics"], {"rows_in": 2, "rows_out": 1})

    def test_first_match_wins_and_nested_branches(self):
        steps = [
            {"op": "branch", "branches": [
                {"when": "a > 1", "steps": [
                    {"op": "branch", "branches": [
                        {"when": "a > 5", "steps": [{"op": "map", "as": "t", "expr": '"big"'}]},
                        {"when": "a > 1", "steps": [{"op": "map", "as": "t", "expr": '"mid"'}]},
                        {"when": "otherwise", "steps": [{"op": "map", "as": "t", "expr": '"never"'}]},
                    ]},
                ]},
                {"when": "otherwise", "steps": [
                    {"op": "filter", "where": "a > 0"},
                    {"op": "map", "as": "t", "expr": '"small"'},
                ]},
            ]},
            {"op": "select", "columns": ["a", "t"]},
        ]
        code, out = run_cli(request(steps, [{"a": 3}, {"a": 9}, {"a": 1}, {"a": 0}, {"a": 7}]),
                            args=["--execute"])
        self.assertEqual(code, 0, out)
        self.assertEqual(out["data"], [
            {"a": 9, "t": "big"}, {"a": 7, "t": "big"},
            {"a": 3, "t": "mid"},
            {"a": 1, "t": "small"},
        ])

    def test_nested_error_paths(self):
        steps = [{"op": "branch", "branches": [
            {"when": "otherwise", "steps": [
                {"op": "branch", "branches": [{"when": "a > 1", "steps": [{"op": "zap"}]}]},
            ]},
        ]}]
        self.assert_error(request(steps), "UNKNOWN_OP",
                          "pipeline.steps[0].branches[0].steps[0].branches[0].steps[0].op")
        steps = [{"op": "branch", "branches": [{"when": "a * 2 > 1", "steps": []}]}]
        self.assert_error(request(steps, [{"a": "s"}]), "EXECUTION_FAILED",
                          "pipeline.steps[0].branches[0].when", args=["--execute"])
        steps = [{"op": "branch", "branches": [{"when": "a >> 1", "steps": []}]}]
        self.assert_error(request(steps), "BAD_EXPR", "pipeline.steps[0].branches[0].when")

    def test_otherwise_constraints(self):
        steps = [{"op": "branch", "branches": [
            {"when": "otherwise", "steps": []}, {"when": "otherwise", "steps": []}]}]
        self.assert_error(request(steps), "MALFORMED_STEP", "pipeline.steps[0].branches")
        steps = [{"op": "limit", "n": 1}, {"op": "branch", "branches": [
            {"when": "otherwise", "steps": []}, {"when": "x > 1", "steps": []}]}]
        self.assert_error(request(steps), "MALFORMED_STEP", "pipeline.steps[1].branches")
        self.assert_error(request(steps), "MALFORMED_STEP", "pipeline.steps[1].branches",
                          args=["--execute"])

    def test_schema_errors(self):
        base = "pipeline.steps[0]"
        self.assert_error(request([{"op": "branch"}]), "SCHEMA_VALIDATION_FAILED", base + ".branches")
        self.assert_error(request([{"op": "branch", "branches": {}}]),
                          "SCHEMA_VALIDATION_FAILED", base + ".branches")
        self.assert_error(request([{"op": "branch", "branches": []}]),
                          "SCHEMA_VALIDATION_FAILED", base + ".branches")
        self.assert_error(request([{"op": "branch", "branches": ["x"]}]),
                          "SCHEMA_VALIDATION_FAILED", base + ".branches[0]")
        self.assert_error(request([{"op": "branch", "branches": [{"steps": []}]}]),
                          "SCHEMA_VALIDATION_FAILED", base + ".branches[0].when")
        self.assert_error(request([{"op": "branch", "branches": [{"when": "  ", "steps": []}]}]),
                          "SCHEMA_VALIDATION_FAILED", base + ".branches[0].when")
        self.assert_error(request([{"op": "branch", "branches": [{"when": "otherwise"}]}]),
                          "SCHEMA_VALIDATION_FAILED", base + ".branches[0].steps")
        self.assert_error(request([{"op": "branch", "branches": [{"when": "otherwise", "steps": {}}]}]),
                          "SCHEMA_VALIDATION_FAILED", base + ".branches[0].steps")
        self.assert_error(request([{"op": "branch", "branches": [{"id": 3, "when": "otherwise", "steps": []}]}]),
                          "SCHEMA_VALIDATION_FAILED", base + ".branches[0].id")
        ok = [{"when": "otherwise", "steps": []}]
        self.assert_error(request([{"op": "branch", "branches": ok, "merge": "concat"}]),
                          "SCHEMA_VALIDATION_FAILED", base + ".merge")
        self.assert_error(request([{"op": "branch", "branches": ok, "merge": {"strategy": "union"}}]),
                          "SCHEMA_VALIDATION_FAILED", base + ".merge.strategy")
        self.assert_error(request([{"op": "branch", "branches": ok, "merge": {"strategy": 1}}]),
                          "SCHEMA_VALIDATION_FAILED", base + ".merge.strategy")

    def test_merge_defaults_to_concat(self):
        code, out = run_cli(request([{"op": "branch", "branches": [{"when": "otherwise", "steps": []}],
                                      "merge": {}}]))
        self.assertEqual(code, 0)
        self.assertEqual(out["normalized"]["steps"][0]["merge"], {"strategy": "concat"})

    def test_columns_tracked_through_branches_in_normalize_mode(self):
        # A column produced by any branch is available afterwards.
        code, out = run_cli(request([
            {"op": "branch", "branches": [
                {"when": "a > 1", "steps": [{"op": "map", "as": "t", "expr": "1"}]},
                {"when": "otherwise", "steps": []}]},
            {"op": "select", "columns": ["a", "t"]},
        ], [{"a": 3}]))
        self.assertEqual(code, 0, out)
        # Each branch starts from the columns available before the branch step.
        self.assert_error(request([
            {"op": "branch", "branches": [
                {"when": "a > 1", "steps": [{"op": "map", "as": "t", "expr": "1"}]},
                {"when": "otherwise", "steps": [{"op": "select", "columns": ["t"]}]}]},
        ], [{"a": 3}]), "MISSING_COLUMN", "pipeline.steps[0].branches[1].steps[0].columns")
        self.assert_error(request([
            {"op": "branch", "branches": [{"when": "nope > 1", "steps": []}]},
        ], [{"a": 3}]), "MISSING_COLUMN", "pipeline.steps[0].branches[0].when")

    def test_branch_steps_do_not_mutate_input_dataset(self):
        code, out = run_cli(request([
            {"op": "branch", "branches": [
                {"when": "otherwise", "steps": [{"op": "rename", "from": "a", "to": "b"}]}]},
            {"op": "select", "columns": ["b"]},
        ], [{"a": 1}]), args=["--execute"])
        self.assertEqual(code, 0, out)
        self.assertEqual(out["data"], [{"b": 1}])


if __name__ == "__main__":
    unittest.main()
