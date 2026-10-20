"""End-to-end tests that drive etl_pipeline.py through stdin/stdout.

Run with: python -m unittest discover tests
"""

import json
import subprocess
import sys
import unittest
from pathlib import Path

ENTRYPOINT = Path(__file__).resolve().parent.parent / "etl_pipeline.py"


def run_cli(payload, *args):
    text = payload if isinstance(payload, str) else json.dumps(payload)
    proc = subprocess.run(
        [sys.executable, str(ENTRYPOINT), *args], input=text, capture_output=True, text=True
    )
    return json.loads(proc.stdout), proc.returncode


def request(*steps, dataset=None):
    return {"pipeline": {"steps": list(steps)}, "dataset": [] if dataset is None else dataset}


class SuccessTests(unittest.TestCase):
    def assert_ok(self, req, expected_steps):
        out, code = run_cli(req)
        self.assertEqual(code, 0, out)
        self.assertEqual(out, {"status": "ok", "normalized": {"steps": expected_steps}})
        return out

    def test_spec_example_1(self):
        self.assert_ok(
            request(
                {"op": "Select", "columns": ["id", "price", "category"]},
                {"op": "rename", "from": "price", "to": "usd_price"},
            ),
            [
                {"op": "select", "columns": ["id", "price", "category"]},
                {"op": "rename", "mapping": {"price": "usd_price"}},
            ],
        )

    def test_empty_pipeline(self):
        self.assert_ok(request(), [])

    def test_trimming_and_key_order(self):
        out = self.assert_ok(
            request(
                {"op": " MAP ", "expr": " qty * price ", "as": " total ", "extra": 1},
                {"op": "filter", "where": "  total > 10 and not (qty == 0) "},
                {"op": "rename", "from": " a ", "to": " b "},
                {"op": "rename", "mapping": {" x ": " y "}},
                {"op": "select", "columns": [" spaced col", "id"]},
                {"op": "limit", "n": 0},
            ),
            [
                {"op": "map", "as": "total", "expr": "qty * price"},
                {"op": "filter", "where": "total > 10 and not (qty == 0)"},
                {"op": "rename", "mapping": {"a": "b"}},
                {"op": "rename", "mapping": {" x ": " y "}},
                {"op": "select", "columns": [" spaced col", "id"]},
                {"op": "limit", "n": 0},
            ],
        )
        self.assertEqual(list(out["normalized"]["steps"][0]), ["op", "as", "expr"])

    def test_unknown_top_level_keys_ignored(self):
        req = request({"op": "limit", "n": 3}, dataset=[{"a": 1}])
        req["meta"] = {"anything": True}
        self.assert_ok(req, [{"op": "limit", "n": 3}])

    def test_valid_expressions(self):
        for e in ["-a + 3.5 / (b - 1)", "a != 'x' or b <= 2", "flag == true", "not not a", "x == null"]:
            with self.subTest(e=e):
                self.assert_ok(request({"op": "filter", "where": e}), [{"op": "filter", "where": e}])


class ErrorTests(unittest.TestCase):
    def assert_error(self, req, code, path):
        out, exit_code = run_cli(req)
        self.assertEqual(exit_code, 1, out)
        self.assertEqual(out["status"], "error")
        self.assertEqual(out["error_code"], code, out)
        self.assertEqual(out["path"], path, out)
        self.assertTrue(out["message"].startswith("ETL_ERROR:"))

    def test_unknown_op(self):
        out, _ = run_cli(request({"op": "TRANSPOSE"}))
        self.assertEqual(
            out,
            {
                "status": "error",
                "error_code": "UNKNOWN_OP",
                "message": "ETL_ERROR: unsupported op 'transpose'",
                "path": "pipeline.steps[0].op",
            },
        )

    def test_bad_expressions(self):
        for e in ["a ^^ b", "a + * b", "(a > 1", "a > 1)", "a b", "a = 1", "a < b < c", "a &&& b", "3abc", "a ** b", "a <> b", "a !== b", "a % b"]:
            with self.subTest(e=e):
                self.assert_error(
                    request({"op": "limit", "n": 1}, {"op": "filter", "where": e}),
                    "BAD_EXPR",
                    "pipeline.steps[1].where",
                )
        self.assert_error(request({"op": "map", "as": "t", "expr": "a +"}), "BAD_EXPR", "pipeline.steps[0].expr")

    def test_schema_errors(self):
        cases = [
            ("not json", ""),
            ([], ""),
            ({"dataset": []}, "pipeline"),
            ({"pipeline": {}, "dataset": []}, "pipeline.steps"),
            ({"pipeline": {"steps": {}}, "dataset": []}, "pipeline.steps"),
            ({"pipeline": {"steps": []}}, "dataset"),
            ({"pipeline": {"steps": []}, "dataset": [1]}, "dataset[0]"),
            (request("select"), "pipeline.steps[0]"),
            (request({"columns": []}), "pipeline.steps[0].op"),
            (request({"op": "   "}), "pipeline.steps[0].op"),
            (request({"op": "select"}), "pipeline.steps[0].columns"),
            (request({"op": "select", "columns": "id"}), "pipeline.steps[0].columns"),
            (request({"op": "select", "columns": ["id", 3]}), "pipeline.steps[0].columns[1]"),
            (request({"op": "filter", "where": "  "}), "pipeline.steps[0].where"),
            (request({"op": "filter", "where": 5}), "pipeline.steps[0].where"),
            (request({"op": "map", "expr": "a"}), "pipeline.steps[0].as"),
            (request({"op": "map", "as": " ", "expr": "a"}), "pipeline.steps[0].as"),
            (request({"op": "rename", "from": "a"}), "pipeline.steps[0].to"),
            (request({"op": "rename", "from": " ", "to": "b"}), "pipeline.steps[0].from"),
            (request({"op": "rename"}), "pipeline.steps[0].mapping"),
            (request({"op": "rename", "mapping": {"a": 1}}), "pipeline.steps[0].mapping.a"),
            (request({"op": "limit", "n": -1}), "pipeline.steps[0].n"),
            (request({"op": "limit", "n": 1.5}), "pipeline.steps[0].n"),
            (request({"op": "limit", "n": True}), "pipeline.steps[0].n"),
            (request({"op": "limit", "n": "3"}), "pipeline.steps[0].n"),
        ]
        for req, path in cases:
            with self.subTest(req=req):
                self.assert_error(req, "SCHEMA_VALIDATION_FAILED", path)

    def test_first_error_wins(self):
        self.assert_error(
            request({"op": "limit", "n": 1}, {"op": "nope"}, {"op": "limit", "n": -1}),
            "UNKNOWN_OP",
            "pipeline.steps[1].op",
        )


class ExecuteTests(unittest.TestCase):
    def execute(self, *steps, dataset):
        out, code = run_cli(request(*steps, dataset=dataset), "--execute")
        self.assertEqual(code, 0, out)
        self.assertEqual(set(out), {"status", "data", "metrics"})
        self.assertEqual(out["metrics"], {"rows_in": len(dataset), "rows_out": len(out["data"])})
        return out["data"]

    def eval_expr(self, expression, row):
        return self.execute({"op": "map", "as": "r", "expr": expression}, dataset=[row])[0]["r"]

    def assert_exec_error(self, req, code, path, message=None):
        out, exit_code = run_cli(req, "--execute")
        self.assertEqual(exit_code, 1, out)
        self.assertEqual((out["status"], out["error_code"], out["path"]), ("error", code, path), out)
        if message is not None:
            self.assertEqual(out["message"], "ETL_ERROR: " + message)

    def test_spec_example(self):
        data = self.execute(
            {"op": "select", "columns": ["id", "price", "qty"]},
            {"op": "map", "as": "total", "expr": "price * qty"},
            {"op": "filter", "where": "total >= 100"},
            {"op": "limit", "n": 2},
            dataset=[
                {"id": 1, "price": 12.5, "qty": 8, "x": 0},
                {"id": 2, "price": 5, "qty": 10},
                {"id": 3, "price": 40, "qty": 3},
                {"id": 4, "price": 20, "qty": 4},
            ],
        )
        self.assertEqual(
            data,
            [{"id": 1, "price": 12.5, "qty": 8, "total": 100}, {"id": 3, "price": 40, "qty": 3, "total": 120}],
        )

    def test_execute_flag_forms(self):
        req = request({"op": "limit", "n": 1}, dataset=[{"a": 1}, {"a": 2}])
        for args in [(), ("--execute=false",), ("--execute", "false")]:
            self.assertIn("normalized", run_cli(req, *args)[0])
        for args in [("--execute",), ("--execute=true",), ("--execute", "true")]:
            self.assertEqual(run_cli(req, *args)[0]["data"], [{"a": 1}])

    def test_select_order_and_map_overwrite(self):
        data = self.execute(
            {"op": "select", "columns": ["b", "a"]},
            {"op": "map", "as": "a", "expr": "a + 1"},
            dataset=[{"a": 1, "b": 2, "c": 3}],
        )
        self.assertEqual(data, [{"b": 2, "a": 2}])
        self.assertEqual(list(data[0]), ["b", "a"])

    def test_rename(self):
        data = self.execute(
            {"op": "rename", "mapping": {"a": "x", "b": "x"}},
            {"op": "rename", "from": "c", "to": "d"},
            dataset=[{"a": 1, "b": 2, "c": 3}],
        )
        self.assertEqual(data, [{"x": 2, "d": 3}])

    def test_null_and_type_semantics(self):
        row = {"n": None, "i": 4, "s": "a"}
        cases = {
            "n + 1": None, "i / 0": None, "missing * 2": None, "i / 8": 0.5,
            "n == null": False, "n != 1": False, "i == \"4\"": False, "i != \"4\"": False,
            "s < 1": False, "s < \"b\"": True, "i == 4.0": True,
            "!n": True, "n || true": True, "n && true": False, "!i == false": True,
            "1 + 2 * 3 - 4 / 2": 5, "(1 + 2) * 3": 9, "true || false && false": True,
            "-i + +2": -2, "s + \"b\"": "ab",
        }
        for expression, expected in cases.items():
            with self.subTest(expr=expression):
                result = self.eval_expr(expression, row)
                self.assertEqual(result, expected)
                self.assertIs(type(result), type(expected))

    def test_filter_drops_null_and_false(self):
        data = self.execute(
            {"op": "filter", "where": "v"}, dataset=[{"v": None}, {"v": False}, {"v": 1}, {}]
        )
        self.assertEqual(data, [{"v": 1}])

    def test_errors(self):
        self.assert_exec_error(
            request({"op": "select", "columns": ["id", "price", "missing"]}, dataset=[{"id": 1, "price": 9.5}]),
            "MISSING_COLUMN", "pipeline.steps[0].columns[2]", "column 'missing' not found in row",
        )
        self.assert_exec_error(
            request({"op": "map", "as": "bad", "expr": "price ** qty"}, dataset=[{"price": 10}]),
            "BAD_EXPR", "pipeline.steps[0].expr", "unsupported operator '**'",
        )
        self.assert_exec_error(
            request({"op": "limit", "n": 5}, {"op": "rename", "mapping": {"a": "b", "cost": "c"}}, dataset=[{"a": 1}]),
            "MISSING_COLUMN", "pipeline.steps[1].mapping.cost",
        )
        self.assert_exec_error(
            request({"op": "rename", "from": "z", "to": "y"}, dataset=[{"a": 1}]),
            "MISSING_COLUMN", "pipeline.steps[0].from",
        )
        self.assert_exec_error(
            request({"op": "filter", "where": "a * \"x\" > 1"}, dataset=[{"a": 1}]),
            "EXECUTION_FAILED", "pipeline.steps[0].where",
        )

    def test_missing_column_not_raised_for_filtered_out_rows(self):
        data = self.execute(
            {"op": "filter", "where": "keep"},
            {"op": "select", "columns": ["x"]},
            dataset=[{"keep": True, "x": 1}, {"keep": False}],
        )
        self.assertEqual(data, [{"x": 1}])


def branch(*branches, **extra):
    return {"op": "branch", "branches": [{"when": w, "steps": list(st)} for w, *st in branches], **extra}


class BranchTests(unittest.TestCase):
    execute = ExecuteTests.execute
    assert_exec_error = ExecuteTests.assert_exec_error

    def test_routing_and_concat_order(self):
        data = self.execute(
            branch(
                ("price < 20", {"op": "map", "as": "tag", "expr": "\"cheap\""}),
                ("otherwise", {"op": "map", "as": "tag", "expr": "\"premium\""}),
            ),
            dataset=[{"id": 1, "price": 10}, {"id": 2, "price": 25}, {"id": 3, "price": 5}],
        )
        self.assertEqual([(r["id"], r["tag"]) for r in data], [(1, "cheap"), (3, "cheap"), (2, "premium")])

    def test_first_match_wins_and_unmatched_dropped(self):
        data = self.execute(
            branch(("a > 1",), ("a > 0", {"op": "map", "as": "b", "expr": "a"}), ("a > 2",)),
            {"op": "select", "columns": ["a"]},
            dataset=[{"a": 3}, {"a": 1}, {"a": 0}, {"a": 2}],
        )
        self.assertEqual(data, [{"a": 3}, {"a": 2}, {"a": 1}])

    def test_nested_branch(self):
        data = self.execute(
            branch(("a > 0", branch(("a > 5", {"op": "limit", "n": 1})))),
            dataset=[{"a": 7}, {"a": 9}, {"a": 1}],
        )
        self.assertEqual(data, [{"a": 7}])

    def test_normalized(self):
        out, code = run_cli(request({"op": "BRANCH", "branches": [
            {"id": "x", "when": " a ", "steps": [{"op": "Limit", "n": 1}]},
            {"when": " otherwise ", "steps": []},
        ]}))
        self.assertEqual(code, 0, out)
        self.assertEqual(out["normalized"]["steps"], [{
            "op": "branch",
            "branches": [
                {"id": "x", "when": "a", "steps": [{"op": "limit", "n": 1}]},
                {"when": "otherwise", "steps": []},
            ],
            "merge": {"strategy": "concat"},
        }])

    def test_errors(self):
        self.assert_exec_error(
            request(branch(("qty >= 1", {"op": "select", "columns": ["id", "missing"]}), ("otherwise",)),
                    dataset=[{"id": 1, "qty": 2}]),
            "MISSING_COLUMN", "pipeline.steps[0].branches[0].steps[0].columns[1]",
        )
        for branches in ([("otherwise",), ("a",)], [("a",), ("otherwise",), ("otherwise",)]):
            self.assert_exec_error(request(branch(*branches)), "MALFORMED_STEP", "pipeline.steps[0].branches")
        self.assert_exec_error(request(branch()), "SCHEMA_VALIDATION_FAILED", "pipeline.steps[0].branches")
        self.assert_exec_error(
            request(branch(("a",), merge={"strategy": "union"})),
            "SCHEMA_VALIDATION_FAILED", "pipeline.steps[0].merge.strategy",
        )
        self.assert_exec_error(
            request({"op": "branch", "branches": [{"when": "a"}]}),
            "SCHEMA_VALIDATION_FAILED", "pipeline.steps[0].branches[0].steps",
        )
        self.assert_exec_error(
            request(branch(("a", branch(("b +",))))),
            "BAD_EXPR", "pipeline.steps[0].branches[0].steps[0].branches[0].when",
        )
        self.assert_exec_error(
            request(branch(("a * \"x\"",)), dataset=[{"a": 1}]),
            "EXECUTION_FAILED", "pipeline.steps[0].branches[0].when",
        )


if __name__ == "__main__":
    unittest.main()
