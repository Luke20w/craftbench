"""Tests for etl_pipeline.py. Run with: python3 -m unittest discover tests"""
import json
import os
import subprocess
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from etl_pipeline import handle, parse_expression, ExprSyntaxError, main  # noqa: E402


def run(request):
    return handle(json.dumps(request))


def execute(request):
    return handle(json.dumps(request), execute=True)


def req(steps, dataset=None):
    return {"pipeline": {"steps": steps}, "dataset": [] if dataset is None else dataset}


class NormalizationTests(unittest.TestCase):
    def test_example_1_casing_and_rename(self):
        resp, code = run(req([
            {"op": "Select", "columns": ["id", "price", "category"]},
            {"op": "rename", "from": "price", "to": "usd_price"},
        ]))
        self.assertEqual(code, 0)
        self.assertEqual(resp, {"status": "ok", "normalized": {"steps": [
            {"op": "select", "columns": ["id", "price", "category"]},
            {"op": "rename", "mapping": {"price": "usd_price"}},
        ]}})

    def test_example_3_empty_pipeline(self):
        self.assertEqual(run(req([])), ({"status": "ok", "normalized": {"steps": []}}, 0))

    def test_trimming_and_key_order(self):
        resp, _ = run(req([{"op": " Map ", "as": " total ", "expr": " qty * price ", "zzz": 1}]))
        step = resp["normalized"]["steps"][0]
        self.assertEqual(list(step.keys()), ["op", "as", "expr"])
        self.assertEqual(step, {"op": "map", "as": "total", "expr": "qty * price"})

    def test_columns_and_mapping_preserved_exactly(self):
        resp, _ = run(req([
            {"op": "select", "columns": [" id "]},
            {"op": "rename", "mapping": {" a ": " b "}},
        ]))
        self.assertEqual(resp["normalized"]["steps"][0]["columns"], [" id "])
        self.assertEqual(resp["normalized"]["steps"][1]["mapping"], {" a ": " b "})

    def test_unknown_keys_ignored_at_top_level(self):
        resp, code = run({"pipeline": {"steps": []}, "dataset": [], "extra": 1})
        self.assertEqual(code, 0)


class ErrorTests(unittest.TestCase):
    def assert_error(self, request, code, path):
        resp, exit_code = run(request)
        self.assertEqual(exit_code, 1)
        self.assertEqual(resp["status"], "error")
        self.assertEqual(resp["error_code"], code)
        self.assertEqual(resp["path"], path)
        self.assertTrue(resp["message"].startswith("ETL_ERROR:"))

    def test_example_2_unknown_op(self):
        resp, code = run(req([{"op": "TRANSPOSE"}]))
        self.assertEqual(resp, {
            "status": "error", "error_code": "UNKNOWN_OP",
            "message": "ETL_ERROR: unsupported op 'transpose'",
            "path": "pipeline.steps[0].op",
        })

    def test_missing_fields(self):
        self.assert_error(req([{"op": "select"}]), "SCHEMA_VALIDATION_FAILED", "pipeline.steps[0].columns")
        self.assert_error(req([{"op": "filter"}]), "SCHEMA_VALIDATION_FAILED", "pipeline.steps[0].where")
        self.assert_error(req([{"op": "map", "as": "x"}]), "SCHEMA_VALIDATION_FAILED", "pipeline.steps[0].expr")
        self.assert_error(req([{"op": "limit"}]), "SCHEMA_VALIDATION_FAILED", "pipeline.steps[0].n")
        self.assert_error(req([{"columns": []}]), "SCHEMA_VALIDATION_FAILED", "pipeline.steps[0].op")

    def test_empty_after_trim(self):
        self.assert_error(req([{"op": "map", "as": "  ", "expr": "1"}]), "SCHEMA_VALIDATION_FAILED", "pipeline.steps[0].as")
        self.assert_error(req([{"op": "filter", "where": " "}]), "SCHEMA_VALIDATION_FAILED", "pipeline.steps[0].where")
        self.assert_error(req([{"op": "rename", "from": " ", "to": "b"}]), "SCHEMA_VALIDATION_FAILED", "pipeline.steps[0].from")

    def test_limit_validation(self):
        self.assert_error(req([{"op": "limit", "n": -1}]), "SCHEMA_VALIDATION_FAILED", "pipeline.steps[0].n")
        self.assert_error(req([{"op": "limit", "n": "3"}]), "SCHEMA_VALIDATION_FAILED", "pipeline.steps[0].n")
        self.assert_error(req([{"op": "limit", "n": True}]), "SCHEMA_VALIDATION_FAILED", "pipeline.steps[0].n")
        self.assertEqual(run(req([{"op": "limit", "n": 0}]))[1], 0)

    def test_bad_expressions(self):
        for expr in ["a ^^ b", "a * * b", "(a + 1", "a +", "1 2", "and a", "'open"]:
            self.assert_error(req([{"op": "filter", "where": expr}]), "BAD_EXPR", "pipeline.steps[0].where")
        self.assert_error(req([{"op": "map", "as": "x", "expr": "a ^ b"}]), "BAD_EXPR", "pipeline.steps[0].expr")

    def test_top_level_schema(self):
        self.assert_error({"pipeline": {"steps": []}}, "SCHEMA_VALIDATION_FAILED", "dataset")
        self.assert_error({"pipeline": {}, "dataset": []}, "SCHEMA_VALIDATION_FAILED", "pipeline.steps")
        self.assert_error({"dataset": []}, "SCHEMA_VALIDATION_FAILED", "pipeline")
        self.assert_error(req([], dataset=[1]), "SCHEMA_VALIDATION_FAILED", "dataset[0]")
        self.assert_error(req(["nope"]), "SCHEMA_VALIDATION_FAILED", "pipeline.steps[0]")

    def test_invalid_json(self):
        resp, code = handle("{not json")
        self.assertEqual(code, 1)
        self.assertEqual(resp["error_code"], "SCHEMA_VALIDATION_FAILED")


class ExpressionParserTests(unittest.TestCase):
    def test_precedence(self):
        self.assertEqual(parse_expression("a + b * c"),
                         ("binary", "+", ("ident", "a"), ("binary", "*", ("ident", "b"), ("ident", "c"))))
        self.assertEqual(parse_expression("not a and b"),
                         ("binary", "and", ("unary", "not", ("ident", "a")), ("ident", "b")))

    def test_literals(self):
        self.assertEqual(parse_expression("1.5e3"), ("num", 1500.0))
        self.assertEqual(parse_expression("'it\\'s'"), ("str", "it's"))
        self.assertEqual(parse_expression("TRUE"), ("const", True))

    def test_rejects(self):
        for text in ["", "()", "a b", "1..2", "a == == b"]:
            with self.assertRaises(ExprSyntaxError):
                parse_expression(text)


class ExecutionTests(unittest.TestCase):
    def eval_expr(self, expr, row):
        resp, code = execute(req([{"op": "map", "as": "r", "expr": expr}], [row]))
        self.assertEqual(code, 0, resp)
        return resp["data"][0]["r"]

    def test_example_1_pipeline(self):
        resp, code = execute(req([
            {"op": "select", "columns": ["id", "price", "qty"]},
            {"op": "map", "as": "total", "expr": "price * qty"},
            {"op": "filter", "where": "total >= 100"},
            {"op": "limit", "n": 2},
        ], [
            {"id": 1, "price": 12.5, "qty": 8},
            {"id": 2, "price": 5, "qty": 10},
            {"id": 3, "price": 40, "qty": 3},
            {"id": 4, "price": 20, "qty": 4},
        ]))
        self.assertEqual(code, 0)
        self.assertEqual(resp, {"status": "ok", "data": [
            {"id": 1, "price": 12.5, "qty": 8, "total": 100},
            {"id": 3, "price": 40, "qty": 3, "total": 120},
        ], "metrics": {"rows_in": 4, "rows_out": 2}})
        self.assertNotIn("normalized", resp)
        # integral float results serialise as integers
        self.assertIn('"total": 100}', json.dumps(resp))

    def test_example_2_missing_column(self):
        resp, code = execute(req([{"op": "select", "columns": ["id", "price", "missing"]}],
                                 [{"id": 1, "price": 9.5}]))
        self.assertEqual(code, 1)
        self.assertEqual(resp, {
            "status": "error", "error_code": "MISSING_COLUMN",
            "message": "ETL_ERROR: column 'missing' not found in row",
            "path": "pipeline.steps[0].columns[2]",
        })

    def test_example_3_bad_expr(self):
        resp, code = execute(req([{"op": "map", "as": "bad", "expr": "price ** qty"}],
                                 [{"price": 10, "qty": 2}]))
        self.assertEqual(resp, {
            "status": "error", "error_code": "BAD_EXPR",
            "message": "ETL_ERROR: unsupported operator '**'",
            "path": "pipeline.steps[0].expr",
        })
        for expr, op in [("a ^^ b", "^^"), ("a = b", "="), ("a <> b", "<>"), ("a & b", "&"), ("a === b", "===")]:
            resp, _ = run(req([{"op": "filter", "where": expr}]))
            self.assertEqual(resp["error_code"], "BAD_EXPR")
            self.assertEqual(resp["message"], f"ETL_ERROR: unsupported operator '{op}'")

    def test_not_executing_returns_normalized(self):
        resp, code = run(req([{"op": "select", "columns": ["missing"]}], [{"a": 1}]))
        self.assertEqual(code, 0)
        self.assertEqual(resp, {"status": "ok", "normalized": {"steps": [{"op": "select", "columns": ["missing"]}]}})

    def test_empty_pipeline_and_metrics(self):
        resp, _ = execute(req([], [{"a": 1}, {"a": 2}]))
        self.assertEqual(resp, {"status": "ok", "data": [{"a": 1}, {"a": 2}], "metrics": {"rows_in": 2, "rows_out": 2}})
        resp, _ = execute(req([{"op": "filter", "where": "a > 1"}], [{"a": 1}, {"a": 2}]))
        self.assertEqual(resp["metrics"], {"rows_in": 2, "rows_out": 1})
        resp, _ = execute(req([{"op": "select", "columns": ["nope"]}], []))
        self.assertEqual(resp["data"], [])

    def test_null_handling(self):
        row = {"a": 10, "b": 0, "n": None}
        self.assertIsNone(self.eval_expr("a / b", row))
        self.assertIsNone(self.eval_expr("a + n", row))
        self.assertIsNone(self.eval_expr("missing * 2", row))
        self.assertIsNone(self.eval_expr("-n", row))
        for expr in ["n == n", "n != 1", "n < 1", "a > n", "missing == missing"]:
            self.assertIs(self.eval_expr(expr, row), False, expr)
        self.assertIs(self.eval_expr("!n", row), True)
        self.assertIs(self.eval_expr("n || a", row), True)
        self.assertIs(self.eval_expr("n && a", row), False)

    def test_type_semantics(self):
        row = {"a": 10, "s": "x", "t": True}
        self.assertIs(self.eval_expr('a == "10"', row), False)
        self.assertIs(self.eval_expr('a != "10"', row), False)
        self.assertIs(self.eval_expr("t == 1", row), False)
        self.assertIs(self.eval_expr("a == 10.0", row), True)
        self.assertIs(self.eval_expr('a < "z"', row), False)
        self.assertIs(self.eval_expr('s < "z"', row), True)
        self.assertIs(self.eval_expr("a >= 10", row), True)
        self.assertIs(self.eval_expr('s == "x" && a > 5 || false', row), True)
        resp, code = execute(req([{"op": "map", "as": "r", "expr": "s * 2"}], [row]))
        self.assertEqual(code, 1)
        self.assertEqual(resp["error_code"], "EXECUTION_FAILED")
        self.assertEqual(resp["path"], "pipeline.steps[0].expr")
        resp, _ = execute(req([{"op": "filter", "where": "s + 1"}], [row]))
        self.assertEqual((resp["error_code"], resp["path"]), ("EXECUTION_FAILED", "pipeline.steps[0].where"))

    def test_arithmetic_and_precedence(self):
        row = {"a": 10, "b": 4}
        self.assertEqual(self.eval_expr("a + b * 2", row), 18)
        self.assertEqual(self.eval_expr("(a + b) * 2", row), 28)
        self.assertEqual(self.eval_expr("a / b", row), 2.5)
        self.assertEqual(self.eval_expr("a / 5", row), 2)
        self.assertEqual(self.eval_expr("a - -b", row), 14)
        self.assertEqual(self.eval_expr("!a == 10", row), False)   # (!a) == 10
        self.assertEqual(self.eval_expr("not a == 10", row), False)  # not (a == 10)
        self.assertEqual(self.eval_expr('"s"', row), "s")
        self.assertIsNone(self.eval_expr("1e308 * 10", row))

    def test_select_order_and_map_overwrite(self):
        resp, _ = execute(req([{"op": "select", "columns": ["b", "a"]}], [{"a": 1, "b": 2, "c": 3}]))
        self.assertEqual(list(resp["data"][0].items()), [("b", 2), ("a", 1)])
        resp, _ = execute(req([{"op": "map", "as": "a", "expr": "a + 1"}], [{"a": 1, "b": 2}]))
        self.assertEqual(list(resp["data"][0].items()), [("a", 2), ("b", 2)])
        resp, _ = execute(req([{"op": "select", "columns": ["a", "c"]}], [{"a": 1, "c": 1}, {"a": 2}]))
        self.assertEqual((resp["error_code"], resp["path"]), ("MISSING_COLUMN", "pipeline.steps[0].columns[1]"))

    def test_rename(self):
        resp, _ = execute(req([{"op": "rename", "mapping": {"a": "x", "b": "x"}}], [{"a": 1, "b": 2, "c": 3}]))
        self.assertEqual(resp["data"], [{"x": 2, "c": 3}])
        resp, _ = execute(req([{"op": "rename", "from": "a", "to": "b"}], [{"a": 1, "b": 2}]))
        self.assertEqual(resp["data"], [{"b": 1}])
        resp, _ = execute(req([{"op": "rename", "from": "zz", "to": "b"}], [{"a": 1}]))
        self.assertEqual((resp["error_code"], resp["path"]), ("MISSING_COLUMN", "pipeline.steps[0].from"))
        resp, _ = execute(req([{"op": "rename", "mapping": {"a": "q", "zz": "b"}}], [{"a": 1}]))
        self.assertEqual((resp["error_code"], resp["path"]), ("MISSING_COLUMN", "pipeline.steps[0].mapping.zz"))
        self.assertEqual(resp["message"], "ETL_ERROR: column 'zz' not found in row")

    def test_limit_and_filter(self):
        ds = [{"a": i} for i in range(5)]
        resp, _ = execute(req([{"op": "filter", "where": "a > 1"}, {"op": "limit", "n": 2}], ds))
        self.assertEqual(resp["data"], [{"a": 2}, {"a": 3}])
        resp, _ = execute(req([{"op": "limit", "n": 10}], ds))
        self.assertEqual(len(resp["data"]), 5)
        resp, _ = execute(req([{"op": "filter", "where": "missing"}], ds))
        self.assertEqual(resp["data"], [])
        resp, _ = execute(req([{"op": "filter", "where": "a"}], ds))  # 0 is falsy
        self.assertEqual(resp["metrics"]["rows_out"], 4)

    def test_input_dataset_not_mutated(self):
        request = req([{"op": "map", "as": "b", "expr": "1"}], [{"a": 1}])
        execute(request)
        self.assertEqual(request["dataset"], [{"a": 1}])


class CliTests(unittest.TestCase):
    def test_cli_roundtrip(self):
        proc = subprocess.run(
            [sys.executable, os.path.join(ROOT, "etl_pipeline.py")],
            input=json.dumps(req([{"op": "Select", "columns": ["a"]}])),
            capture_output=True, text=True,
        )
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(json.loads(proc.stdout)["status"], "ok")

    def test_cli_error_exit_code(self):
        proc = subprocess.run(
            [sys.executable, os.path.join(ROOT, "etl_pipeline.py")],
            input=json.dumps(req([{"op": "nope"}])),
            capture_output=True, text=True,
        )
        self.assertEqual(proc.returncode, 1)
        self.assertEqual(json.loads(proc.stdout)["error_code"], "UNKNOWN_OP")

    def run_cli(self, request, *flags):
        proc = subprocess.run(
            [sys.executable, os.path.join(ROOT, "etl_pipeline.py"), *flags],
            input=json.dumps(request), capture_output=True, text=True,
        )
        return json.loads(proc.stdout), proc.returncode

    def test_cli_execute_flag(self):
        request = req([{"op": "map", "as": "b", "expr": "a * 2"}], [{"a": 2}])
        resp, code = self.run_cli(request, "--execute")
        self.assertEqual((code, resp), (0, {"status": "ok", "data": [{"a": 2, "b": 4}],
                                            "metrics": {"rows_in": 1, "rows_out": 1}}))
        for flags in [(), ("--execute=false",), ("--execute", "false")]:
            resp, code = self.run_cli(request, *flags)
            self.assertEqual(code, 0)
            self.assertIn("normalized", resp)
            self.assertNotIn("data", resp)
        for flags in [("--execute=true",), ("--execute", "true")]:
            self.assertIn("data", self.run_cli(request, *flags)[0])
        resp, code = self.run_cli(req([{"op": "select", "columns": ["zz"]}], [{"a": 1}]), "--execute")
        self.assertEqual((code, resp["error_code"]), (1, "MISSING_COLUMN"))


if __name__ == "__main__":
    unittest.main()


def branch(branches, merge=None):
    step = {"op": "branch", "branches": branches}
    if merge is not None:
        step["merge"] = merge
    return step


class BranchTests(unittest.TestCase):
    def assert_error(self, resp_code, code, path, execute_mode=False):
        resp, exit_code = resp_code
        self.assertEqual(exit_code, 1)
        self.assertEqual(resp["error_code"], code)
        self.assertEqual(resp["path"], path)
        self.assertTrue(resp["message"].startswith("ETL_ERROR:"))

    def test_example_1_routing_with_otherwise(self):
        resp, code = execute(req([branch([
            {"id": "cheap", "when": "price < 20", "steps": [{"op": "map", "as": "tag", "expr": '"cheap"'}]},
            {"id": "otherwise", "when": "otherwise", "steps": [{"op": "map", "as": "tag", "expr": '"premium"'}]},
        ], {"strategy": "concat"})], [{"id": 1, "price": 10}, {"id": 2, "price": 25}, {"id": 3, "price": 5}]))
        self.assertEqual(code, 0)
        self.assertEqual(resp, {"status": "ok", "data": [
            {"id": 1, "price": 10, "tag": "cheap"},
            {"id": 3, "price": 5, "tag": "cheap"},
            {"id": 2, "price": 25, "tag": "premium"},
        ], "metrics": {"rows_in": 3, "rows_out": 3}})

    def test_example_2_error_path_inside_branch(self):
        self.assert_error(execute(req([branch([
            {"id": "s1", "when": "qty >= 1", "steps": [{"op": "select", "columns": ["id", "missing"]}]},
            {"id": "otherwise", "when": "otherwise", "steps": []},
        ], {"strategy": "concat"})], [{"id": 1, "qty": 2}])),
            "MISSING_COLUMN", "pipeline.steps[0].branches[0].steps[0].columns[1]")

    def test_normalized_shape_defaults_and_key_order(self):
        resp, code = run(req([{"op": " Branch ", "branches": [
            {"id": "a", "when": " x > 1 ", "steps": [{"op": "LIMIT", "n": 1}]},
            {"when": "Otherwise", "steps": []},
        ]}]))
        self.assertEqual(code, 0)
        step = resp["normalized"]["steps"][0]
        self.assertEqual(list(step.keys()), ["op", "branches", "merge"])
        self.assertEqual(step, {"op": "branch", "branches": [
            {"id": "a", "when": "x > 1", "steps": [{"op": "limit", "n": 1}]},
            {"when": "otherwise", "steps": []},
        ], "merge": {"strategy": "concat"}})

    def test_first_match_wins_and_unmatched_rows_dropped(self):
        ds = [{"a": 1}, {"a": 2}, {"a": 3}, {"a": 4}]
        resp, _ = execute(req([branch([
            {"when": "a > 2", "steps": [{"op": "map", "as": "t", "expr": '"hi"'}]},
            {"when": "a > 1", "steps": [{"op": "map", "as": "t", "expr": '"mid"'}]},
        ])], ds))
        self.assertEqual(resp["data"], [{"a": 3, "t": "hi"}, {"a": 4, "t": "hi"}, {"a": 2, "t": "mid"}])
        self.assertEqual(resp["metrics"], {"rows_in": 4, "rows_out": 3})

    def test_later_conditions_not_evaluated_for_claimed_rows(self):
        # Row 1 is claimed by the first branch, so the second branch's
        # condition (which would fail on a string) never runs for it.
        resp, code = execute(req([branch([
            {"when": "a == 1", "steps": []},
            {"when": "s * 2", "steps": []},
        ])], [{"a": 1, "s": "x"}]))
        self.assertEqual(code, 0)
        self.assertEqual(resp["data"], [{"a": 1, "s": "x"}])

    def test_nested_branch_and_paths(self):
        inner = branch([{"when": "a > 2", "steps": [{"op": "map", "as": "t", "expr": '"big"'}]}])
        resp, _ = execute(req([branch([{"when": "a > 1", "steps": [inner]}])], [{"a": 1}, {"a": 2}, {"a": 3}]))
        self.assertEqual(resp["data"], [{"a": 3, "t": "big"}])
        bad_inner = branch([{"when": "a ** 2", "steps": []}])
        self.assert_error(run(req([branch([{"when": "a > 1", "steps": [bad_inner]}])])),
                          "BAD_EXPR", "pipeline.steps[0].branches[0].steps[0].branches[0].when")
        self.assert_error(run(req([branch([{"when": "a", "steps": [{"op": "nope"}]}])])),
                          "UNKNOWN_OP", "pipeline.steps[0].branches[0].steps[0].op")
        self.assert_error(execute(req([branch([{"when": "a", "steps": [{"op": "rename", "from": "zz", "to": "b"}]}])],
                                      [{"a": 1}])),
                          "MISSING_COLUMN", "pipeline.steps[0].branches[0].steps[0].from")

    def test_when_evaluation_failure(self):
        self.assert_error(execute(req([branch([{"when": "s * 2", "steps": []}])], [{"s": "x"}])),
                          "EXECUTION_FAILED", "pipeline.steps[0].branches[0].when")

    def test_malformed_otherwise(self):
        self.assert_error(run(req([branch([{"when": "otherwise", "steps": []}, {"when": "otherwise", "steps": []}])])),
                          "MALFORMED_STEP", "pipeline.steps[0].branches")
        self.assert_error(run(req([{"op": "limit", "n": 1},
                                   branch([{"when": "otherwise", "steps": []}, {"when": "a > 1", "steps": []}])])),
                          "MALFORMED_STEP", "pipeline.steps[1].branches")

    def test_schema_errors(self):
        S = "SCHEMA_VALIDATION_FAILED"
        self.assert_error(run(req([{"op": "branch"}])), S, "pipeline.steps[0].branches")
        self.assert_error(run(req([branch([])])), S, "pipeline.steps[0].branches")
        self.assert_error(run(req([branch("x")])), S, "pipeline.steps[0].branches")
        self.assert_error(run(req([branch(["x"])])), S, "pipeline.steps[0].branches[0]")
        self.assert_error(run(req([branch([{"steps": []}])])), S, "pipeline.steps[0].branches[0].when")
        self.assert_error(run(req([branch([{"when": 1, "steps": []}])])), S, "pipeline.steps[0].branches[0].when")
        self.assert_error(run(req([branch([{"when": "a"}])])), S, "pipeline.steps[0].branches[0].steps")
        self.assert_error(run(req([branch([{"when": "a", "steps": {}}])])), S, "pipeline.steps[0].branches[0].steps")
        self.assert_error(run(req([branch([{"id": 3, "when": "a", "steps": []}])])), S, "pipeline.steps[0].branches[0].id")
        self.assert_error(run(req([branch([{"when": "a", "steps": []}], "concat")])), S, "pipeline.steps[0].merge")
        self.assert_error(run(req([branch([{"when": "a", "steps": []}], {"strategy": 1})])), S,
                          "pipeline.steps[0].merge.strategy")
        self.assert_error(run(req([branch([{"when": "a", "steps": []}], {"strategy": "union"})])), S,
                          "pipeline.steps[0].merge.strategy")

    def test_cli_roundtrip(self):
        request = req([branch([{"when": "otherwise", "steps": [{"op": "limit", "n": 1}]}])], [{"a": 1}, {"a": 2}])
        proc = subprocess.run([sys.executable, os.path.join(ROOT, "etl_pipeline.py"), "--execute"],
                              input=json.dumps(request), capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(json.loads(proc.stdout), {"status": "ok", "data": [{"a": 1}],
                                                   "metrics": {"rows_in": 2, "rows_out": 1}})
