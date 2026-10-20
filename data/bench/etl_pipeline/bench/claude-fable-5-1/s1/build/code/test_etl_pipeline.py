"""Tests for etl_pipeline.py.

Run with:  python3 -m unittest -v test_etl_pipeline

Most tests drive the real CLI through a subprocess so they exercise exactly
what external callers see (stdout JSON + exit code). A few parser tests call
the module directly.
"""

from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

import etl_pipeline

SCRIPT = Path(__file__).with_name("etl_pipeline.py")


def run_cli(payload, *args: str) -> tuple[dict, int]:
    text = payload if isinstance(payload, str) else json.dumps(payload)
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        input=text,
        capture_output=True,
        text=True,
    )
    return json.loads(proc.stdout), proc.returncode


def request(steps, dataset=None):
    return {"pipeline": {"steps": steps}, "dataset": dataset or []}


def execute(steps, dataset, *args: str) -> tuple[dict, int]:
    return run_cli(request(steps, dataset), *(args or ("--execute",)))


class CliSuccessTests(unittest.TestCase):
    def test_spec_example_normalize_and_rename(self):
        body, code = run_cli(request([
            {"op": "Select", "columns": ["id", "price", "category"]},
            {"op": "rename", "from": "price", "to": "usd_price"},
        ]))
        self.assertEqual(code, 0)
        self.assertEqual(body, {
            "status": "ok",
            "normalized": {"steps": [
                {"op": "select", "columns": ["id", "price", "category"]},
                {"op": "rename", "mapping": {"price": "usd_price"}},
            ]},
        })

    def test_empty_pipeline_is_valid(self):
        body, code = run_cli(request([]))
        self.assertEqual(code, 0)
        self.assertEqual(body, {"status": "ok", "normalized": {"steps": []}})

    def test_trimming_and_key_ordering(self):
        body, code = run_cli(request([
            {"zzz": 1, "op": " Map ", "expr": " qty * price ", "as": " total "},
            {"op": "FILTER", "where": "  qty > 1 and (price < 10 or not flag) "},
            {"op": "limit", "n": 0, "junk": True},
        ]))
        self.assertEqual(code, 0)
        steps = body["normalized"]["steps"]
        self.assertEqual(steps[0], {"op": "map", "as": "total", "expr": "qty * price"})
        self.assertEqual(list(steps[0].keys()), ["op", "as", "expr"])
        self.assertEqual(steps[1], {"op": "filter", "where": "qty > 1 and (price < 10 or not flag)"})
        self.assertEqual(steps[2], {"op": "limit", "n": 0})
        self.assertEqual(list(steps[2].keys()), ["op", "n"])

    def test_column_names_and_mapping_preserved_exactly(self):
        body, code = run_cli(request([
            {"op": "select", "columns": [" id ", "Price"]},
            {"op": "rename", "mapping": {" id ": " ID "}},
        ]))
        self.assertEqual(code, 0)
        steps = body["normalized"]["steps"]
        self.assertEqual(steps[0]["columns"], [" id ", "Price"])
        self.assertEqual(steps[1]["mapping"], {" id ": " ID "})

    def test_rename_from_to_trimmed(self):
        body, _ = run_cli(request([{"op": "rename", "from": " a ", "to": " b "}]))
        self.assertEqual(body["normalized"]["steps"][0], {"op": "rename", "mapping": {"a": "b"}})

    def test_unknown_top_level_keys_ignored(self):
        payload = request([])
        payload["extra"] = {"anything": 1}
        body, code = run_cli(payload)
        self.assertEqual(code, 0)
        self.assertEqual(body["status"], "ok")

    def test_columns_tracked_through_steps_with_dataset(self):
        body, code = run_cli(request([
            {"op": "map", "as": "total", "expr": "qty * price"},
            {"op": "rename", "from": "total", "to": "amount"},
            {"op": "select", "columns": ["id", "amount"]},
            {"op": "filter", "where": "amount > 10"},
        ], dataset=[{"id": 1, "qty": 2, "price": 3}, {"id": 2, "qty": 1}]))
        self.assertEqual(code, 0, body)


class CliErrorTests(unittest.TestCase):
    def assert_error(self, payload, error_code, path):
        body, code = run_cli(payload)
        self.assertEqual(code, 1, body)
        self.assertEqual(body["status"], "error")
        self.assertEqual(body["error_code"], error_code, body)
        self.assertEqual(body["path"], path, body)
        self.assertTrue(body["message"].startswith("ETL_ERROR:"), body)
        return body

    def test_spec_example_unknown_op(self):
        body = self.assert_error(request([{"op": "TRANSPOSE"}]), "UNKNOWN_OP", "pipeline.steps[0].op")
        self.assertEqual(body["message"], "ETL_ERROR: unsupported op 'transpose'")

    def test_invalid_json(self):
        self.assert_error("{not json", "SCHEMA_VALIDATION_FAILED", "")

    def test_root_not_object(self):
        self.assert_error("[]", "SCHEMA_VALIDATION_FAILED", "")

    def test_missing_pipeline(self):
        self.assert_error({"dataset": []}, "SCHEMA_VALIDATION_FAILED", "pipeline")

    def test_steps_not_array(self):
        self.assert_error({"pipeline": {"steps": {}}, "dataset": []},
                          "SCHEMA_VALIDATION_FAILED", "pipeline.steps")

    def test_missing_dataset(self):
        self.assert_error({"pipeline": {"steps": []}}, "SCHEMA_VALIDATION_FAILED", "dataset")

    def test_dataset_row_not_object(self):
        self.assert_error(request([], dataset=[{"a": 1}, 5]), "SCHEMA_VALIDATION_FAILED", "dataset[1]")

    def test_step_not_object(self):
        self.assert_error(request(["select"]), "SCHEMA_VALIDATION_FAILED", "pipeline.steps[0]")

    def test_missing_op(self):
        self.assert_error(request([{"columns": ["a"]}]), "SCHEMA_VALIDATION_FAILED", "pipeline.steps[0].op")

    def test_blank_op(self):
        self.assert_error(request([{"op": "   "}]), "SCHEMA_VALIDATION_FAILED", "pipeline.steps[0].op")

    def test_select_missing_columns(self):
        self.assert_error(request([{"op": "select"}]), "SCHEMA_VALIDATION_FAILED", "pipeline.steps[0].columns")

    def test_select_columns_not_strings(self):
        self.assert_error(request([{"op": "select", "columns": ["a", 2]}]),
                          "SCHEMA_VALIDATION_FAILED", "pipeline.steps[0].columns[1]")

    def test_select_blank_column(self):
        self.assert_error(request([{"op": "select", "columns": ["a", "  "]}]),
                          "SCHEMA_VALIDATION_FAILED", "pipeline.steps[0].columns[1]")

    def test_filter_missing_where(self):
        self.assert_error(request([{"op": "filter"}]), "SCHEMA_VALIDATION_FAILED", "pipeline.steps[0].where")

    def test_filter_blank_where(self):
        self.assert_error(request([{"op": "filter", "where": "  "}]),
                          "SCHEMA_VALIDATION_FAILED", "pipeline.steps[0].where")

    def test_map_blank_as(self):
        self.assert_error(request([{"op": "map", "as": " ", "expr": "a"}]),
                          "SCHEMA_VALIDATION_FAILED", "pipeline.steps[0].as")

    def test_map_missing_expr(self):
        self.assert_error(request([{"op": "map", "as": "x"}]),
                          "SCHEMA_VALIDATION_FAILED", "pipeline.steps[0].expr")

    def test_bad_expression_consecutive_operators(self):
        self.assert_error(request([{"op": "filter", "where": "a ^^ b"}]), "BAD_EXPR", "pipeline.steps[0].where")
        self.assert_error(request([{"op": "map", "as": "x", "expr": "a + * b"}]), "BAD_EXPR", "pipeline.steps[0].expr")

    def test_bad_expression_unbalanced_parens(self):
        self.assert_error(request([{"op": "filter", "where": "(a > 1"}]), "BAD_EXPR", "pipeline.steps[0].where")

    def test_bad_expression_trailing_operator(self):
        self.assert_error(request([{"op": "filter", "where": "a >"}]), "BAD_EXPR", "pipeline.steps[0].where")

    def test_bad_expression_single_equals(self):
        self.assert_error(request([{"op": "filter", "where": "a = 1"}]), "BAD_EXPR", "pipeline.steps[0].where")

    def test_rename_missing_fields(self):
        self.assert_error(request([{"op": "rename"}]), "SCHEMA_VALIDATION_FAILED", "pipeline.steps[0]")

    def test_rename_from_without_to(self):
        self.assert_error(request([{"op": "rename", "from": "a"}]), "SCHEMA_VALIDATION_FAILED", "pipeline.steps[0].to")

    def test_rename_blank_to(self):
        self.assert_error(request([{"op": "rename", "from": "a", "to": " "}]),
                          "SCHEMA_VALIDATION_FAILED", "pipeline.steps[0].to")

    def test_rename_mapping_not_object(self):
        self.assert_error(request([{"op": "rename", "mapping": ["a", "b"]}]),
                          "SCHEMA_VALIDATION_FAILED", "pipeline.steps[0].mapping")

    def test_rename_mapping_non_string_value(self):
        self.assert_error(request([{"op": "rename", "mapping": {"a": 1}}]),
                          "SCHEMA_VALIDATION_FAILED", "pipeline.steps[0].mapping.a")

    def test_limit_missing_n(self):
        self.assert_error(request([{"op": "limit"}]), "SCHEMA_VALIDATION_FAILED", "pipeline.steps[0].n")

    def test_limit_negative(self):
        self.assert_error(request([{"op": "limit", "n": -1}]), "SCHEMA_VALIDATION_FAILED", "pipeline.steps[0].n")

    def test_limit_non_integer(self):
        for bad in (1.5, "3", True, None):
            with self.subTest(n=bad):
                self.assert_error(request([{"op": "limit", "n": bad}]),
                                  "SCHEMA_VALIDATION_FAILED", "pipeline.steps[0].n")

    def test_error_reported_for_first_bad_step(self):
        self.assert_error(request([
            {"op": "limit", "n": 1},
            {"op": "select", "columns": []},
            {"op": "bogus"},
        ]), "SCHEMA_VALIDATION_FAILED", "pipeline.steps[1].columns")

    def test_missing_column_in_select_with_dataset(self):
        self.assert_error(request([{"op": "select", "columns": ["id", "nope"]}], dataset=[{"id": 1}]),
                          "MISSING_COLUMN", "pipeline.steps[0].columns[1]")

    def test_missing_column_in_expression_with_dataset(self):
        self.assert_error(request([{"op": "filter", "where": "price > 1"}], dataset=[{"id": 1}]),
                          "MISSING_COLUMN", "pipeline.steps[0].where")

    def test_missing_column_after_select_narrows(self):
        self.assert_error(request([
            {"op": "select", "columns": ["id"]},
            {"op": "rename", "from": "price", "to": "p"},
        ], dataset=[{"id": 1, "price": 2}]), "MISSING_COLUMN", "pipeline.steps[1].from")

    def test_no_column_checks_with_empty_dataset(self):
        body, code = run_cli(request([{"op": "select", "columns": ["anything"]}]))
        self.assertEqual(code, 0, body)


class ExecuteModeTests(unittest.TestCase):
    DATASET = [
        {"id": 1, "price": 12.5, "qty": 8},
        {"id": 2, "price": 5, "qty": 10},
        {"id": 3, "price": 40, "qty": 3},
        {"id": 4, "price": 20, "qty": 4},
    ]

    def assert_error(self, body, code, error_code, path, message=None):
        self.assertEqual(code, 1, body)
        self.assertEqual(body["status"], "error")
        self.assertEqual(body["error_code"], error_code, body)
        self.assertEqual(body["path"], path, body)
        self.assertTrue(body["message"].startswith("ETL_ERROR:"), body)
        if message is not None:
            self.assertEqual(body["message"], message)

    def test_spec_example_pipeline(self):
        body, code = execute([
            {"op": "select", "columns": ["id", "price", "qty"]},
            {"op": "map", "as": "total", "expr": "price * qty"},
            {"op": "filter", "where": "total >= 100"},
            {"op": "limit", "n": 2},
        ], self.DATASET)
        self.assertEqual(code, 0, body)
        self.assertEqual(body, {
            "status": "ok",
            "data": [
                {"id": 1, "price": 12.5, "qty": 8, "total": 100},
                {"id": 3, "price": 40, "qty": 3, "total": 120},
            ],
            "metrics": {"rows_in": 4, "rows_out": 2},
        })
        self.assertNotIn("normalized", body)
        self.assertIsInstance(body["data"][0]["total"], int)

    def test_spec_example_missing_column(self):
        body, code = execute([{"op": "select", "columns": ["id", "price", "missing"]}],
                             [{"id": 1, "price": 9.5}])
        self.assert_error(body, code, "MISSING_COLUMN", "pipeline.steps[0].columns[2]",
                          "ETL_ERROR: column 'missing' not found in row")

    def test_spec_example_bad_expression(self):
        body, code = execute([{"op": "map", "as": "bad", "expr": "price ** qty"}],
                             [{"price": 10, "qty": 2}])
        self.assert_error(body, code, "BAD_EXPR", "pipeline.steps[0].expr",
                          "ETL_ERROR: unsupported operator '**'")

    def test_flag_forms(self):
        payload = request([], [{"a": 1}])
        for args, expect_execute in (
            ((), False),
            (("--execute",), True),
            (("--execute", "true"), True),
            (("--execute=true",), True),
            (("--execute", "false"), False),
            (("--execute=false",), False),
            (("--execute=1",), True),
            (("--execute=0",), False),
        ):
            with self.subTest(args=args):
                body, code = run_cli(payload, *args)
                self.assertEqual(code, 0, body)
                self.assertEqual("data" in body, expect_execute, body)
                self.assertEqual("normalized" in body, not expect_execute, body)

    def test_bad_flag_value_is_json_error(self):
        body, code = run_cli(request([], []), "--execute=maybe")
        self.assert_error(body, code, "SCHEMA_VALIDATION_FAILED", "")
        body, code = run_cli(request([], []), "--bogus")
        self.assert_error(body, code, "SCHEMA_VALIDATION_FAILED", "")

    def test_empty_pipeline_returns_dataset(self):
        body, code = execute([], self.DATASET)
        self.assertEqual(code, 0)
        self.assertEqual(body["data"], self.DATASET)
        self.assertEqual(body["metrics"], {"rows_in": 4, "rows_out": 4})

    def test_empty_dataset(self):
        body, code = execute([{"op": "select", "columns": ["nope"]}, {"op": "filter", "where": "x > 1"}], [])
        self.assertEqual(code, 0, body)
        self.assertEqual(body, {"status": "ok", "data": [], "metrics": {"rows_in": 0, "rows_out": 0}})

    def test_select_orders_columns_and_checks_every_row(self):
        body, code = execute([{"op": "select", "columns": ["b", "a"]}], [{"a": 1, "b": 2}])
        self.assertEqual(code, 0)
        self.assertEqual(list(body["data"][0].keys()), ["b", "a"])
        body, code = execute([{"op": "select", "columns": ["a", "b"]}], [{"a": 1, "b": 2}, {"a": 3}])
        self.assert_error(body, code, "MISSING_COLUMN", "pipeline.steps[0].columns[1]")

    def test_missing_identifier_in_expression_is_null(self):
        body, code = execute([
            {"op": "map", "as": "x", "expr": "price * nothere"},
            {"op": "map", "as": "y", "expr": "nothere == null"},
            {"op": "map", "as": "z", "expr": "nothere < 1"},
        ], [{"price": 2}])
        self.assertEqual(code, 0, body)
        self.assertEqual(body["data"], [{"price": 2, "x": None, "y": False, "z": False}])

    def test_null_arithmetic_and_division_by_zero(self):
        body, code = execute([
            {"op": "map", "as": "a", "expr": "n + 1"},
            {"op": "map", "as": "b", "expr": "-n"},
            {"op": "map", "as": "c", "expr": "price / 0"},
            {"op": "map", "as": "d", "expr": "price / 4"},
            {"op": "map", "as": "e", "expr": "price / 5"},
        ], [{"n": None, "price": 10}])
        self.assertEqual(code, 0, body)
        self.assertEqual(body["data"], [{"n": None, "price": 10, "a": None, "b": None, "c": None, "d": 2.5, "e": 2}])

    def test_comparison_type_mismatch_is_false(self):
        body, code = execute([
            {"op": "map", "as": "eq", "expr": "a == b"},
            {"op": "map", "as": "ne", "expr": "a != b"},
            {"op": "map", "as": "lt", "expr": "a < b"},
            {"op": "map", "as": "numeq", "expr": "a == 1.0"},
            {"op": "map", "as": "booleq", "expr": "t == 1"},
            {"op": "map", "as": "streq", "expr": "s == \"x\""},
            {"op": "map", "as": "strlt", "expr": "s < \"y\""},
        ], [{"a": 1, "b": "1", "t": True, "s": "x"}])
        self.assertEqual(code, 0, body)
        row = body["data"][0]
        self.assertEqual((row["eq"], row["ne"], row["lt"]), (False, False, False))
        self.assertEqual((row["numeq"], row["booleq"], row["streq"], row["strlt"]), (True, False, True, True))

    def test_boolean_operators_and_null_falsy(self):
        body, code = execute([{"op": "filter", "where": "!flag && (n > 0 || n == 0)"}], [
            {"flag": False, "n": 1},
            {"flag": True, "n": 1},
            {"flag": None, "n": 0},
            {"flag": None, "n": None},
        ])
        self.assertEqual(code, 0, body)
        self.assertEqual(body["data"], [{"flag": False, "n": 1}, {"flag": None, "n": 0}])
        self.assertEqual(body["metrics"], {"rows_in": 4, "rows_out": 2})

    def test_keyword_and_symbol_operators_mix(self):
        body, code = execute([{"op": "filter", "where": "not a or b && c"}],
                             [{"a": True, "b": True, "c": True}, {"a": True, "b": True, "c": False}, {"a": False}])
        self.assertEqual(code, 0, body)
        self.assertEqual(body["metrics"]["rows_out"], 2)

    def test_precedence_in_execution(self):
        body, code = execute([{"op": "map", "as": "x", "expr": "1 + 2 * 3 - 4 / 2"}], [{}])
        self.assertEqual(body["data"], [{"x": 5}])
        body, code = execute([{"op": "map", "as": "x", "expr": "(1 + 2) * 3"}], [{}])
        self.assertEqual(body["data"], [{"x": 9}])

    def test_short_circuit_avoids_evaluation_error(self):
        body, code = execute([{"op": "filter", "where": "false && (s * 2)"}], [{"s": "text"}])
        self.assertEqual(code, 0, body)
        self.assertEqual(body["data"], [])

    def test_arithmetic_on_non_numbers_is_execution_failed(self):
        body, code = execute([{"op": "map", "as": "x", "expr": "s * 2"}], [{"s": "text"}])
        self.assert_error(body, code, "EXECUTION_FAILED", "pipeline.steps[0].expr")
        body, code = execute([{"op": "filter", "where": "-s > 1"}], [{"s": "text"}])
        self.assert_error(body, code, "EXECUTION_FAILED", "pipeline.steps[0].where")

    def test_map_overwrites_existing_field_in_place(self):
        body, code = execute([{"op": "map", "as": "a", "expr": "a + 1"}], [{"a": 1, "b": 2}])
        self.assertEqual(code, 0)
        self.assertEqual(body["data"], [{"a": 2, "b": 2}])
        self.assertEqual(list(body["data"][0].keys()), ["a", "b"])

    def test_map_reads_previous_steps_output(self):
        body, code = execute([
            {"op": "map", "as": "total", "expr": "price * qty"},
            {"op": "rename", "from": "total", "to": "amount"},
            {"op": "filter", "where": "amount > 100"},
        ], self.DATASET)
        self.assertEqual(code, 0, body)
        self.assertEqual([r["id"] for r in body["data"]], [3])

    def test_rename_keeps_position_and_later_mapping_wins(self):
        body, code = execute([{"op": "rename", "from": "a", "to": "x"}], [{"a": 1, "b": 2}])
        self.assertEqual(body["data"], [{"x": 1, "b": 2}])
        self.assertEqual(list(body["data"][0].keys()), ["x", "b"])
        body, code = execute([{"op": "rename", "mapping": {"a": "c", "b": "c"}}], [{"a": 1, "b": 2, "z": 0}])
        self.assertEqual(code, 0, body)
        self.assertEqual(body["data"], [{"c": 2, "z": 0}])

    def test_rename_missing_source_paths(self):
        body, code = execute([{"op": "rename", "from": "nope", "to": "c"}], [{"a": 1}])
        self.assert_error(body, code, "MISSING_COLUMN", "pipeline.steps[0].from")
        body, code = execute([{"op": "rename", "mapping": {"a": "b", "nope": "c"}}], [{"a": 1}])
        self.assert_error(body, code, "MISSING_COLUMN", "pipeline.steps[0].mapping.nope")

    def test_limit(self):
        body, code = execute([{"op": "limit", "n": 0}], self.DATASET)
        self.assertEqual(body["data"], [])
        body, code = execute([{"op": "limit", "n": 99}], self.DATASET)
        self.assertEqual(body["metrics"], {"rows_in": 4, "rows_out": 4})

    def test_validation_errors_reported_before_execution(self):
        body, code = execute([
            {"op": "select", "columns": ["missing"]},
            {"op": "limit", "n": -1},
        ], [{"a": 1}])
        self.assert_error(body, code, "SCHEMA_VALIDATION_FAILED", "pipeline.steps[1].n")
        body, code = execute([{"op": "bogus"}], [{"a": 1}])
        self.assert_error(body, code, "UNKNOWN_OP", "pipeline.steps[0].op")

    def test_error_in_later_step_uses_its_index(self):
        body, code = execute([
            {"op": "limit", "n": 3},
            {"op": "select", "columns": ["id", "gone"]},
        ], self.DATASET)
        self.assert_error(body, code, "MISSING_COLUMN", "pipeline.steps[1].columns[1]")

    def test_normalize_mode_unchanged_by_execute_false(self):
        body, code = run_cli(request([{"op": "filter", "where": "price > 1"}], [{"id": 1}]), "--execute=false")
        self.assert_error(body, code, "MISSING_COLUMN", "pipeline.steps[0].where")


class ExpressionParserTests(unittest.TestCase):
    def test_precedence(self):
        ast = etl_pipeline.parse_expression("a + b * c > 1 and not d or e")
        self.assertEqual(ast[0], "or")
        self.assertEqual(ast[1][0], "and")
        self.assertEqual(ast[1][1], ("binop", ">", ("binop", "+", ("col", "a"), ("binop", "*", ("col", "b"), ("col", "c"))), ("num", 1.0)))
        self.assertEqual(ast[1][2], ("not", ("col", "d")))

    def test_literals(self):
        self.assertEqual(etl_pipeline.parse_expression("'x'"), ("str", "x"))
        self.assertEqual(etl_pipeline.parse_expression('"y"'), ("str", "y"))
        self.assertEqual(etl_pipeline.parse_expression("TRUE"), ("bool", True))
        self.assertEqual(etl_pipeline.parse_expression("null"), ("null", None))
        self.assertEqual(etl_pipeline.parse_expression("-2.5"), ("unary", "-", ("num", 2.5)))

    def test_c_style_operators(self):
        ast = etl_pipeline.parse_expression("!a == b && c || d")
        self.assertEqual(ast, ("or", ("and", ("binop", "==", ("not", ("col", "a")), ("col", "b")), ("col", "c")), ("col", "d")))
        self.assertEqual(etl_pipeline.parse_expression("a*-b"), ("binop", "*", ("col", "a"), ("unary", "-", ("col", "b"))))
        self.assertEqual(etl_pipeline.parse_expression("a>=-1"), ("binop", ">=", ("col", "a"), ("unary", "-", ("num", 1))))

    def test_integer_literals_stay_integers(self):
        self.assertEqual(etl_pipeline.parse_expression("3"), ("num", 3))
        self.assertIsInstance(etl_pipeline.parse_expression("3")[1], int)
        self.assertIsInstance(etl_pipeline.parse_expression("3.0")[1], float)
        self.assertIsInstance(etl_pipeline.parse_expression("1e3")[1], float)

    def test_unsupported_operator_message_names_whole_run(self):
        with self.assertRaises(etl_pipeline.ExprSyntaxError) as ctx:
            etl_pipeline.parse_expression("price ** qty")
        self.assertEqual(str(ctx.exception), "unsupported operator '**'")

    def test_columns_referenced(self):
        ast = etl_pipeline.parse_expression("(qty * price) > limit_ and flag")
        self.assertEqual(etl_pipeline.expression_columns(ast), ["qty", "price", "limit_", "flag"])

    def test_rejects(self):
        for text in ("", "a ^^ b", "a ** b", "a + * b", "(a", "a)", "a b", "1 2", "a & b", "a | b",
                     "a = b", "a <> b", "a % b", "'unterminated", "a == == b", "not", "3abc"):
            with self.subTest(expr=text):
                with self.assertRaises(etl_pipeline.ExprSyntaxError):
                    etl_pipeline.parse_expression(text)


def branch(branches, merge=None, **extra):
    step = {"op": "branch", "branches": branches, **extra}
    if merge is not None:
        step["merge"] = merge
    return step


class BranchTests(unittest.TestCase):
    PRICES = [{"id": 1, "price": 10}, {"id": 2, "price": 25}, {"id": 3, "price": 5}]

    def assert_error(self, body, code, error_code, path):
        self.assertEqual(code, 1, body)
        self.assertEqual(body["status"], "error")
        self.assertEqual(body["error_code"], error_code, body)
        self.assertEqual(body["path"], path, body)
        self.assertTrue(body["message"].startswith("ETL_ERROR:"), body)

    def test_spec_example_routing_with_otherwise(self):
        body, code = execute([branch([
            {"id": "cheap", "when": "price < 20", "steps": [{"op": "map", "as": "tag", "expr": '"cheap"'}]},
            {"id": "otherwise", "when": "otherwise", "steps": [{"op": "map", "as": "tag", "expr": '"premium"'}]},
        ], {"strategy": "concat"})], self.PRICES)
        self.assertEqual(code, 0, body)
        self.assertEqual(body, {
            "status": "ok",
            "data": [
                {"id": 1, "price": 10, "tag": "cheap"},
                {"id": 3, "price": 5, "tag": "cheap"},
                {"id": 2, "price": 25, "tag": "premium"},
            ],
            "metrics": {"rows_in": 3, "rows_out": 3},
        })

    def test_spec_example_error_path_inside_branch(self):
        body, code = execute([branch([
            {"id": "s1", "when": "qty >= 1", "steps": [{"op": "select", "columns": ["id", "missing"]}]},
            {"id": "otherwise", "when": "otherwise", "steps": []},
        ], {"strategy": "concat"})], [{"id": 1, "qty": 2}])
        self.assert_error(body, code, "MISSING_COLUMN", "pipeline.steps[0].branches[0].steps[0].columns[1]")

    def test_normalized_form_defaults_merge_and_sorts_keys(self):
        body, code = run_cli(request([branch([
            {"id": "a", "when": " price < 20 ", "steps": [{"op": " LIMIT ", "n": 1}]},
            {"when": "Otherwise", "steps": []},
        ], junk=1)], self.PRICES))
        self.assertEqual(code, 0, body)
        step = body["normalized"]["steps"][0]
        self.assertEqual(list(step.keys()), ["op", "branches", "merge"])
        self.assertEqual(step, {
            "op": "branch",
            "branches": [
                {"id": "a", "when": "price < 20", "steps": [{"op": "limit", "n": 1}]},
                {"when": "otherwise", "steps": []},
            ],
            "merge": {"strategy": "concat"},
        })
        self.assertEqual(list(step["branches"][0].keys()), ["id", "when", "steps"])

    def test_first_match_wins_and_unmatched_rows_dropped(self):
        body, code = execute([branch([
            {"when": "price < 20", "steps": [{"op": "map", "as": "tag", "expr": "'lt20'"}]},
            {"when": "price < 30", "steps": [{"op": "map", "as": "tag", "expr": "'lt30'"}]},
        ])], self.PRICES + [{"id": 4, "price": 100}])
        self.assertEqual(code, 0, body)
        self.assertEqual(body["data"], [
            {"id": 1, "price": 10, "tag": "lt20"},
            {"id": 3, "price": 5, "tag": "lt20"},
            {"id": 2, "price": 25, "tag": "lt30"},
        ])
        self.assertEqual(body["metrics"], {"rows_in": 4, "rows_out": 3})

    def test_branch_steps_only_see_their_rows_and_later_steps_see_merged(self):
        body, code = execute([
            branch([
                {"when": "price < 20", "steps": [{"op": "limit", "n": 1}]},
                {"when": "otherwise", "steps": [{"op": "select", "columns": ["id"]}]},
            ]),
            {"op": "map", "as": "seen", "expr": "price"},
        ], self.PRICES)
        self.assertEqual(code, 0, body)
        self.assertEqual(body["data"], [
            {"id": 1, "price": 10, "seen": 10},
            {"id": 2, "seen": None},
        ])

    def test_nested_branch_and_error_path(self):
        inner = branch([
            {"when": "id > 1", "steps": [{"op": "map", "as": "k", "expr": "id * 2"}]},
            {"when": "otherwise", "steps": [{"op": "map", "as": "k", "expr": "0"}]},
        ])
        outer = branch([
            {"when": "price < 20", "steps": [inner]},
            {"when": "otherwise", "steps": []},
        ])
        body, code = execute([outer], self.PRICES)
        self.assertEqual(code, 0, body)
        self.assertEqual(body["data"], [
            {"id": 3, "price": 5, "k": 6},
            {"id": 1, "price": 10, "k": 0},
            {"id": 2, "price": 25},
        ])

        bad_inner = branch([{"when": "id > 1", "steps": [{"op": "rename", "from": "nope", "to": "x"}]}])
        body, code = execute([branch([{"when": "otherwise", "steps": [{"op": "limit", "n": 5}, bad_inner]}])], self.PRICES)
        self.assert_error(body, code, "MISSING_COLUMN", "pipeline.steps[0].branches[0].steps[1].branches[0].steps[0].from")

    def test_when_errors_point_at_branch(self):
        body, code = run_cli(request([branch([{"when": "price **", "steps": []}])], self.PRICES))
        self.assert_error(body, code, "BAD_EXPR", "pipeline.steps[0].branches[0].when")
        body, code = run_cli(request([branch([{"when": "nope > 1", "steps": []}])], self.PRICES))
        self.assert_error(body, code, "MISSING_COLUMN", "pipeline.steps[0].branches[0].when")
        body, code = execute([branch([{"when": "price + 'x'", "steps": []}])], self.PRICES)
        self.assert_error(body, code, "EXECUTION_FAILED", "pipeline.steps[0].branches[0].when")

    def test_static_schema_after_branch_is_union_of_branch_outputs(self):
        steps = [
            branch([
                {"when": "price < 20", "steps": [{"op": "map", "as": "tag", "expr": "1"}]},
                {"when": "otherwise", "steps": [{"op": "select", "columns": ["id"]}]},
            ]),
            {"op": "select", "columns": ["id", "price", "tag"]},
        ]
        body, code = run_cli(request(steps, self.PRICES))
        self.assertEqual(code, 0, body)
        steps[1] = {"op": "select", "columns": ["id", "nope"]}
        body, code = run_cli(request(steps, self.PRICES))
        self.assert_error(body, code, "MISSING_COLUMN", "pipeline.steps[1].columns[1]")

    def test_malformed_otherwise(self):
        two = branch([{"when": "otherwise", "steps": []}, {"when": "otherwise", "steps": []}])
        body, code = run_cli(request([two], self.PRICES))
        self.assert_error(body, code, "MALFORMED_STEP", "pipeline.steps[0].branches")
        not_last = branch([{"when": "otherwise", "steps": []}, {"when": "price > 1", "steps": []}])
        body, code = run_cli(request([{"op": "limit", "n": 1}, not_last], self.PRICES))
        self.assert_error(body, code, "MALFORMED_STEP", "pipeline.steps[1].branches")
        body, code = execute([not_last], self.PRICES)
        self.assert_error(body, code, "MALFORMED_STEP", "pipeline.steps[0].branches")

    def test_schema_validation(self):
        cases = [
            ({"op": "branch"}, "pipeline.steps[0].branches"),
            (branch({}), "pipeline.steps[0].branches"),
            (branch([]), "pipeline.steps[0].branches"),
            (branch(["x"]), "pipeline.steps[0].branches[0]"),
            (branch([{"steps": []}]), "pipeline.steps[0].branches[0].when"),
            (branch([{"when": 5, "steps": []}]), "pipeline.steps[0].branches[0].when"),
            (branch([{"when": "  ", "steps": []}]), "pipeline.steps[0].branches[0].when"),
            (branch([{"when": "otherwise"}]), "pipeline.steps[0].branches[0].steps"),
            (branch([{"when": "otherwise", "steps": {}}]), "pipeline.steps[0].branches[0].steps"),
            (branch([{"id": 3, "when": "otherwise", "steps": []}]), "pipeline.steps[0].branches[0].id"),
            (branch([{"when": "otherwise", "steps": [{"op": "limit"}]}]), "pipeline.steps[0].branches[0].steps[0].n"),
            (branch([{"when": "otherwise", "steps": []}], "concat"), "pipeline.steps[0].merge"),
            (branch([{"when": "otherwise", "steps": []}], {"strategy": 1}), "pipeline.steps[0].merge.strategy"),
            (branch([{"when": "otherwise", "steps": []}], {"strategy": "union"}), "pipeline.steps[0].merge.strategy"),
        ]
        for step, path in cases:
            with self.subTest(step=step):
                body, code = run_cli(request([step], self.PRICES))
                self.assert_error(body, code, "SCHEMA_VALIDATION_FAILED", path)
        body, code = run_cli(request([branch([{"when": "otherwise", "steps": [{"op": "nope"}]}])]))
        self.assert_error(body, code, "UNKNOWN_OP", "pipeline.steps[0].branches[0].steps[0].op")

    def test_merge_defaults_and_empty_dataset(self):
        step = branch([{"when": "otherwise", "steps": []}], {})
        body, code = run_cli(request([step]))
        self.assertEqual(code, 0, body)
        self.assertEqual(body["normalized"]["steps"][0]["merge"], {"strategy": "concat"})
        body, code = execute([step], [])
        self.assertEqual(body, {"status": "ok", "data": [], "metrics": {"rows_in": 0, "rows_out": 0}})


if __name__ == "__main__":
    unittest.main()
