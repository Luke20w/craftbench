import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def run(request, *args):
    raw = request if isinstance(request, str) else json.dumps(request)
    proc = subprocess.run(
        [sys.executable, "etl_pipeline.py", *args], input=raw, capture_output=True, text=True, cwd=ROOT
    )
    return proc.returncode, json.loads(proc.stdout)


def steps_request(*steps):
    return {"pipeline": {"steps": list(steps)}, "dataset": []}


class SuccessTests(unittest.TestCase):
    def test_spec_example_normalize_and_rename(self):
        code, out = run(steps_request(
            {"op": "Select", "columns": ["id", "price", "category"]},
            {"op": "rename", "from": "price", "to": "usd_price"},
        ))
        self.assertEqual(code, 0)
        self.assertEqual(out, {"status": "ok", "normalized": {"steps": [
            {"op": "select", "columns": ["id", "price", "category"]},
            {"op": "rename", "mapping": {"price": "usd_price"}},
        ]}})

    def test_empty_pipeline(self):
        self.assertEqual(run(steps_request()), (0, {"status": "ok", "normalized": {"steps": []}}))

    def test_trimming_ordering_and_unknown_keys(self):
        code, out = run(steps_request(
            {"op": " MAP ", "expr": " qty * price ", "as": " total ", "junk": 1},
            {"op": "filter", "where": " total >= 10 and not (qty == 0) "},
            {"op": "rename", "from": " a ", "to": " b "},
            {"op": "rename", "mapping": {" x ": " y "}},
            {"op": "select", "columns": [" spaced col "]},
            {"op": "limit", "n": 0},
        ))
        self.assertEqual(code, 0)
        steps = out["normalized"]["steps"]
        self.assertEqual(list(steps[0]), ["op", "as", "expr"])
        self.assertEqual(steps[0], {"op": "map", "as": "total", "expr": "qty * price"})
        self.assertEqual(steps[1]["where"], "total >= 10 and not (qty == 0)")
        self.assertEqual(steps[2]["mapping"], {"a": "b"})
        self.assertEqual(steps[3]["mapping"], {" x ": " y "})
        self.assertEqual(steps[4]["columns"], [" spaced col "])
        self.assertEqual(steps[5], {"op": "limit", "n": 0})

    def test_unknown_top_level_keys_ignored(self):
        req = steps_request()
        req["extra"] = True
        self.assertEqual(run(req)[0], 0)


class ErrorTests(unittest.TestCase):
    def assertError(self, request, code, path):
        exit_code, out = run(request)
        self.assertEqual(exit_code, 1)
        self.assertEqual(out["status"], "error")
        self.assertEqual(out["error_code"], code)
        self.assertEqual(out["path"], path)
        self.assertTrue(out["message"].startswith("ETL_ERROR:"))

    def test_unknown_op(self):
        exit_code, out = run(steps_request({"op": "TRANSPOSE"}))
        self.assertEqual(exit_code, 1)
        self.assertEqual(out, {
            "status": "error", "error_code": "UNKNOWN_OP",
            "message": "ETL_ERROR: unsupported op 'transpose'", "path": "pipeline.steps[0].op",
        })

    def test_schema_errors(self):
        S = "SCHEMA_VALIDATION_FAILED"
        cases = [
            ("not json", ""),
            ({"pipeline": {"steps": []}}, "dataset"),
            ({"pipeline": {"steps": []}, "dataset": [1]}, "dataset[0]"),
            ({"dataset": []}, "pipeline"),
            ({"pipeline": {}, "dataset": []}, "pipeline.steps"),
            (steps_request("select"), "pipeline.steps[0]"),
            (steps_request({"columns": []}), "pipeline.steps[0].op"),
            (steps_request({"op": "  "}), "pipeline.steps[0].op"),
            (steps_request({"op": "select"}), "pipeline.steps[0].columns"),
            (steps_request({"op": "select", "columns": ["a", 1]}), "pipeline.steps[0].columns"),
            (steps_request({"op": "filter", "where": "   "}), "pipeline.steps[0].where"),
            (steps_request({"op": "map", "as": " ", "expr": "a"}), "pipeline.steps[0].as"),
            (steps_request({"op": "rename", "from": "a"}), "pipeline.steps[0].to"),
            (steps_request({"op": "rename", "mapping": {"a": 1}}), "pipeline.steps[0].mapping"),
            (steps_request({"op": "rename"}), "pipeline.steps[0].mapping"),
            (steps_request({"op": "limit", "n": -1}), "pipeline.steps[0].n"),
            (steps_request({"op": "limit", "n": 1.5}), "pipeline.steps[0].n"),
            (steps_request({"op": "limit", "n": True}), "pipeline.steps[0].n"),
        ]
        for request, path in cases:
            with self.subTest(request=request):
                self.assertError(request, S, path)

    def test_bad_expressions(self):
        for expr in ["a ^^ b", "a +", "(a", "a)", "a * * b", "a > > b", "1 < a < 3", "a b"]:
            with self.subTest(expr=expr):
                self.assertError(
                    steps_request({"op": "select", "columns": ["a"]}, {"op": "filter", "where": expr}),
                    "BAD_EXPR", "pipeline.steps[1].where",
                )
        self.assertError(steps_request({"op": "map", "as": "x", "expr": "a ^^ b"}),
                         "BAD_EXPR", "pipeline.steps[0].expr")

    def test_valid_expressions(self):
        for expr in ["-a + 2.5 * (b - c) / d", "a != 'x' or b == \"y\"", "not a", "x == null", "flag == true"]:
            with self.subTest(expr=expr):
                self.assertEqual(run(steps_request({"op": "filter", "where": expr}))[0], 0)


def execute(dataset, *steps):
    return run({"pipeline": {"steps": list(steps)}, "dataset": dataset}, "--execute")


class ExecuteAssertions:
    def assertData(self, dataset, steps, expected):
        code, out = execute(dataset, *steps)
        self.assertEqual(code, 0, out)
        self.assertEqual(out["data"], expected)
        self.assertEqual(list(out), ["status", "data", "metrics"])
        self.assertEqual(out["metrics"], {"rows_in": len(dataset), "rows_out": len(expected)})

    def assertExecError(self, dataset, steps, code, path, message=None):
        exit_code, out = execute(dataset, *steps)
        self.assertEqual(exit_code, 1)
        self.assertEqual((out["error_code"], out["path"]), (code, path))
        self.assertTrue(out["message"].startswith("ETL_ERROR:"))
        if message is not None:
            self.assertEqual(out["message"], message)


class ExecuteTests(ExecuteAssertions, unittest.TestCase):

    def test_spec_example(self):
        self.assertData(
            [{"id": 1, "price": 12.5, "qty": 8}, {"id": 2, "price": 5, "qty": 10},
             {"id": 3, "price": 40, "qty": 3}, {"id": 4, "price": 20, "qty": 4}],
            [{"op": "select", "columns": ["id", "price", "qty"]},
             {"op": "map", "as": "total", "expr": "price * qty"},
             {"op": "filter", "where": "total >= 100"},
             {"op": "limit", "n": 2}],
            [{"id": 1, "price": 12.5, "qty": 8, "total": 100},
             {"id": 3, "price": 40, "qty": 3, "total": 120}],
        )

    def test_execute_flag_forms(self):
        req = steps_request()
        self.assertIn("normalized", run(req)[1])
        self.assertIn("normalized", run(req, "--execute", "false")[1])
        self.assertIn("data", run(req, "--execute=true")[1])

    def test_select_order_and_map_overwrite(self):
        code, out = execute([{"a": 1, "b": 2, "c": 3}], {"op": "select", "columns": ["c", "a"]},
                            {"op": "map", "as": "c", "expr": "c + a"})
        self.assertEqual(list(out["data"][0].items()), [("c", 4), ("a", 1)])

    def test_rename(self):
        self.assertData([{"a": 1, "b": 2, "c": 3}], [{"op": "rename", "mapping": {"a": "x", "b": "x"}}],
                        [{"x": 2, "c": 3}])
        self.assertData([{"a": 1, "b": 2}], [{"op": "rename", "from": "a", "to": "b"}], [{"b": 1}])

    def test_null_and_type_semantics(self):
        cases = {
            "m + 1": None, "a / 0": None, "-m": None, "a / 4": 0.25,
            "m == null": False, "m != 1": False, "a == \"1\"": False, "a != \"1\"": False,
            "a < \"z\"": False, "s < \"t\"": True, "!m": True, "m || a": True, "m && a": False,
            "1 + 2 * 3 - 4 / 2": 5, "(1 + 2) * 3": 9, "!(a > 1) && s == \"s\"": True, "a*-1": -1,
            "f == false": True, "a == 1.0": True,
        }
        for expr, expected in cases.items():
            with self.subTest(expr=expr):
                code, out = execute([{"a": 1, "s": "s", "f": False}], {"op": "map", "as": "r", "expr": expr})
                self.assertEqual(code, 0, out)
                self.assertEqual(out["data"][0]["r"], expected)

    def test_filter_falsy_null(self):
        self.assertData([{"v": None}, {"v": True}, {}], [{"op": "filter", "where": "v"}], [{"v": True}])

    def test_errors(self):
        self.assertExecError([{"id": 1, "price": 9.5}], [{"op": "select", "columns": ["id", "price", "missing"]}],
                             "MISSING_COLUMN", "pipeline.steps[0].columns[2]",
                             "ETL_ERROR: column 'missing' not found in row")
        self.assertExecError([{"a": 1}], [{"op": "rename", "mapping": {"a": "b", "cost": "c"}}],
                             "MISSING_COLUMN", "pipeline.steps[0].mapping.cost")
        self.assertExecError([{"price": 10, "qty": 2}], [{"op": "map", "as": "bad", "expr": "price ** qty"}],
                             "BAD_EXPR", "pipeline.steps[0].expr", "ETL_ERROR: unsupported operator '**'")
        self.assertExecError([{"a": "x"}], [{"op": "limit", "n": 5}, {"op": "filter", "where": "a * 2 > 1"}],
                             "EXECUTION_FAILED", "pipeline.steps[1].where")

    def test_empty_dataset_skips_row_checks(self):
        self.assertData([], [{"op": "select", "columns": ["nope"]}], [])


def branch(*branches, **extra):
    return {"op": "branch", "branches": list(branches), **extra}


class BranchTests(ExecuteAssertions, unittest.TestCase):
    def test_spec_example_routing(self):
        step = branch(
            {"id": "cheap", "when": "price < 20", "steps": [{"op": "map", "as": "tag", "expr": "\"cheap\""}]},
            {"id": "otherwise", "when": "otherwise", "steps": [{"op": "map", "as": "tag", "expr": "\"premium\""}]},
            merge={"strategy": "concat"},
        )
        self.assertData([{"id": 1, "price": 10}, {"id": 2, "price": 25}, {"id": 3, "price": 5}], [step], [
            {"id": 1, "price": 10, "tag": "cheap"}, {"id": 3, "price": 5, "tag": "cheap"},
            {"id": 2, "price": 25, "tag": "premium"},
        ])

    def test_first_match_wins_unmatched_dropped_and_nested(self):
        step = branch(
            {"when": "v > 1", "steps": [branch({"when": "v > 5", "steps": [{"op": "limit", "n": 1}]},
                                              {"when": "otherwise", "steps": []})]},
            {"when": "v > 0", "steps": [{"op": "map", "as": "low", "expr": "true"}]},
        )
        self.assertData([{"v": 9}, {"v": 0}, {"v": 1}, {"v": 7}, {"v": 2}], [step],
                        [{"v": 9}, {"v": 2}, {"v": 1, "low": True}])

    def test_normalization(self):
        code, out = run(steps_request(branch({"id": "a", "when": " otherwise ", "steps": [{"op": " LIMIT ", "n": 1}]})))
        self.assertEqual(code, 0)
        self.assertEqual(out["normalized"]["steps"], [{
            "op": "branch", "branches": [{"id": "a", "when": "otherwise", "steps": [{"op": "limit", "n": 1}]}],
            "merge": {"strategy": "concat"},
        }])

    def test_validation_errors(self):
        other = {"when": "otherwise", "steps": []}
        cases = [
            (branch(other, other), "MALFORMED_STEP", "pipeline.steps[0].branches"),
            (branch(other, {"when": "a", "steps": []}), "MALFORMED_STEP", "pipeline.steps[0].branches"),
            (branch(), "SCHEMA_VALIDATION_FAILED", "pipeline.steps[0].branches"),
            ({"op": "branch"}, "SCHEMA_VALIDATION_FAILED", "pipeline.steps[0].branches"),
            (branch({"when": "a"}), "SCHEMA_VALIDATION_FAILED", "pipeline.steps[0].branches[0].steps"),
            (branch({"steps": []}), "SCHEMA_VALIDATION_FAILED", "pipeline.steps[0].branches[0].when"),
            (branch({"when": "a", "steps": [], "id": 1}), "SCHEMA_VALIDATION_FAILED", "pipeline.steps[0].branches[0].id"),
            (branch(other, merge={"strategy": "zip"}), "SCHEMA_VALIDATION_FAILED", "pipeline.steps[0].merge.strategy"),
            (branch({"when": "a +", "steps": []}), "BAD_EXPR", "pipeline.steps[0].branches[0].when"),
            (branch({"when": "a", "steps": [{"op": "nope"}]}), "UNKNOWN_OP", "pipeline.steps[0].branches[0].steps[0].op"),
        ]
        for step, code, path in cases:
            with self.subTest(step=step):
                self.assertExecError([], [step], code, path)

    def test_execution_error_paths(self):
        step = branch({"id": "s1", "when": "qty >= 1", "steps": [{"op": "select", "columns": ["id", "missing"]}]},
                      {"id": "otherwise", "when": "otherwise", "steps": []})
        self.assertExecError([{"id": 1, "qty": 2}], [step], "MISSING_COLUMN",
                             "pipeline.steps[0].branches[0].steps[0].columns[1]")
        self.assertExecError([{"a": "x"}], [branch({"when": "a * 2", "steps": []})], "EXECUTION_FAILED",
                             "pipeline.steps[0].branches[0].when")


if __name__ == "__main__":
    unittest.main()
