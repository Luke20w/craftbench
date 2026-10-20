"""Hidden tests: the `case` step. Crosses it with normalization, nesting, other steps and errors."""

import json
import subprocess

import pytest


def run(argv, payload, execute=False):
    cmd = [*argv, "--execute"] if execute else argv
    res = subprocess.run(cmd, input=json.dumps(payload), capture_output=True, text=True, timeout=10)
    return res.returncode, json.loads(res.stdout)


def req(*steps, dataset=None):
    return {"pipeline": {"steps": list(steps)}, "dataset": dataset if dataset is not None else []}


def case(as_="tier", cases=None, **extra):
    step = {"op": "case", "as": as_,
            "cases": cases if cases is not None else [{"when": "price < 20", "then": '"cheap"'}]}
    step.update(extra)
    return step


def branch(*branches):
    return {"op": "branch", "branches": list(branches)}


TIERS = [{"when": "price < 20", "then": '"cheap"'}, {"when": "price < 100", "then": '"mid"'}]
ROWS = [{"id": 1, "price": 10}, {"id": 2, "price": 50}, {"id": 3, "price": 500}]


def ok(argv, payload, execute=False):
    code, out = run(argv, payload, execute)
    assert code == 0, out
    assert out["status"] == "ok"
    return out


def err(argv, payload, execute=False):
    code, out = run(argv, payload, execute)
    assert code == 1, out
    assert out["status"] == "error"
    assert out["message"].startswith("ETL_ERROR: ")
    return out["error_code"], out["path"]


# ---------------------------------------------------------------- normalization

def test_normalize_trims_lowercases_and_drops_unknown(entrypoint_argv):
    step = {"op": " CASE ", "as": " tier ", "junk": 1, "else": ' "x" ',
            "cases": [{"when": " price < 20 ", "then": ' "cheap" ', "note": "drop me"}]}
    out = ok(entrypoint_argv, req(step))
    assert out["normalized"]["steps"] == [
        {"op": "case", "as": "tier", "cases": [{"then": '"cheap"', "when": "price < 20"}], "else": '"x"'}]
    assert list(out["normalized"]["steps"][0]) == ["op", "as", "cases", "else"]


def test_normalize_without_else_omits_it(entrypoint_argv):
    out = ok(entrypoint_argv, req(case(cases=TIERS)))
    assert out["normalized"]["steps"][0] == {"op": "case", "as": "tier", "cases": [
        {"then": '"cheap"', "when": "price < 20"}, {"then": '"mid"', "when": "price < 100"}]}


def test_normalize_inside_branch(entrypoint_argv):
    out = ok(entrypoint_argv, req(branch({"when": "otherwise", "steps": [case(" t ", [{"when": " a ", "then": " b "}])]})))
    inner = out["normalized"]["steps"][0]["branches"][0]["steps"][0]
    assert inner == {"op": "case", "as": "t", "cases": [{"then": "b", "when": "a"}]}


# ---------------------------------------------------------------- execution

def test_tiers_with_else(entrypoint_argv):
    out = ok(entrypoint_argv, req(case(cases=TIERS, **{"else": '"premium"'}), dataset=ROWS), execute=True)
    assert [r["tier"] for r in out["data"]] == ["cheap", "mid", "premium"]
    assert out["metrics"] == {"rows_in": 3, "rows_out": 3}


def test_no_match_without_else_is_null(entrypoint_argv):
    out = ok(entrypoint_argv, req(case(cases=TIERS), dataset=ROWS), execute=True)
    assert out["data"][2] == {"id": 3, "price": 500, "tier": None}


def test_first_match_wins(entrypoint_argv):
    cases = [{"when": "price < 1000", "then": "1"}, {"when": "price < 20", "then": "2"}]
    out = ok(entrypoint_argv, req(case("k", cases), dataset=ROWS), execute=True)
    assert [r["k"] for r in out["data"]] == [1, 1, 1]


def test_then_is_an_expression_over_the_row(entrypoint_argv):
    cases = [{"when": "qty > 1", "then": "price * qty"}]
    out = ok(entrypoint_argv, req(case("total", cases, **{"else": "price"}),
                                  dataset=[{"price": 3, "qty": 4}, {"price": 5, "qty": 1}]), execute=True)
    assert [r["total"] for r in out["data"]] == [12, 5]


def test_overwrites_existing_column(entrypoint_argv):
    out = ok(entrypoint_argv, req(case("price", [{"when": "price > 100", "then": "100"}], **{"else": "price"}),
                                  dataset=ROWS), execute=True)
    assert [r["price"] for r in out["data"]] == [10, 50, 100]
    assert list(out["data"][0]) == ["id", "price"]


def test_null_semantics(entrypoint_argv):
    cases = [{"when": "missing > 1", "then": '"a"'}, {"when": "price > 1", "then": "missing + 1"}]
    out = ok(entrypoint_argv, req(case("v", cases), dataset=[{"price": 5}]), execute=True)
    assert out["data"] == [{"price": 5, "v": None}]


def test_composes_with_map_filter_select(entrypoint_argv):
    steps = [{"op": "map", "as": "total", "expr": "price * 2"},
             case("tier", [{"when": "total >= 100", "then": '"big"'}], **{"else": '"small"'}),
             {"op": "filter", "where": 'tier == "big"'},
             {"op": "select", "columns": ["id", "tier"]}]
    out = ok(entrypoint_argv, req(*steps, dataset=ROWS), execute=True)
    assert out["data"] == [{"id": 2, "tier": "big"}, {"id": 3, "tier": "big"}]
    assert out["metrics"] == {"rows_in": 3, "rows_out": 2}


def test_inside_nested_branches(entrypoint_argv):
    inner = branch({"when": "price > 100", "steps": [case("tier", [{"when": "true", "then": '"huge"'}])]},
                   {"when": "otherwise", "steps": [case("tier", TIERS)]})
    out = ok(entrypoint_argv, req(branch({"when": "id > 1", "steps": [inner]},
                                         {"when": "otherwise", "steps": []}), dataset=ROWS), execute=True)
    assert out["data"] == [{"id": 3, "price": 500, "tier": "huge"}, {"id": 2, "price": 50, "tier": "mid"},
                           {"id": 1, "price": 10}]


# ---------------------------------------------------------------- validation errors

VALIDATION = {
    "as_missing": ({"op": "case", "cases": TIERS}, "SCHEMA_VALIDATION_FAILED", "pipeline.steps[0].as"),
    "as_empty": (case("  "), "SCHEMA_VALIDATION_FAILED", "pipeline.steps[0].as"),
    "cases_missing": ({"op": "case", "as": "t"}, "SCHEMA_VALIDATION_FAILED", "pipeline.steps[0].cases"),
    "cases_not_array": (case(cases={"when": "a", "then": "b"}), "SCHEMA_VALIDATION_FAILED", "pipeline.steps[0].cases"),
    "cases_empty": (case(cases=[]), "SCHEMA_VALIDATION_FAILED", "pipeline.steps[0].cases"),
    "case_not_object": (case(cases=[TIERS[0], "x"]), "SCHEMA_VALIDATION_FAILED", "pipeline.steps[0].cases[1]"),
    "then_missing": (case(cases=[{"when": "a"}]), "SCHEMA_VALIDATION_FAILED", "pipeline.steps[0].cases[0].then"),
    "when_not_string": (case(cases=[{"when": 3, "then": "1"}]), "SCHEMA_VALIDATION_FAILED",
                        "pipeline.steps[0].cases[0].when"),
    "then_empty": (case(cases=[{"when": "a", "then": "   "}]), "SCHEMA_VALIDATION_FAILED",
                   "pipeline.steps[0].cases[0].then"),
    "else_not_string": (case(**{"else": 5}), "SCHEMA_VALIDATION_FAILED", "pipeline.steps[0].else"),
    "bad_then": (case(cases=[TIERS[0], {"when": "a", "then": "1 ** 2"}]), "BAD_EXPR", "pipeline.steps[0].cases[1].then"),
    "bad_when": (case(cases=[{"when": "a >", "then": "1"}]), "BAD_EXPR", "pipeline.steps[0].cases[0].when"),
    "bad_else": (case(**{"else": "(1"}), "BAD_EXPR", "pipeline.steps[0].else"),
}


@pytest.mark.parametrize("name", sorted(VALIDATION))
def test_validation(entrypoint_argv, name):
    step, code, path = VALIDATION[name]
    assert err(entrypoint_argv, req(step)) == (code, path)


@pytest.mark.parametrize("name", ["bad_then", "cases_empty"])
def test_validation_with_execute(entrypoint_argv, name):
    step, code, path = VALIDATION[name]
    assert err(entrypoint_argv, req(step, dataset=ROWS), execute=True) == (code, path)


def test_validation_error_deep_in_branches(entrypoint_argv):
    payload = req({"op": "limit", "n": 1}, branch(
        {"when": "otherwise", "steps": [branch({"when": "x", "steps": [
            {"op": "limit", "n": 1}, case(cases=[TIERS[0], {"when": "a &", "then": "1"}])]})]}))
    assert err(entrypoint_argv, payload) == (
        "BAD_EXPR", "pipeline.steps[1].branches[0].steps[0].branches[0].steps[1].cases[1].when")


# ---------------------------------------------------------------- execution errors

def test_runtime_error_in_then(entrypoint_argv):
    payload = req(case("v", [{"when": "true", "then": "name * 2"}]), dataset=[{"name": "a"}])
    assert err(entrypoint_argv, payload, execute=True) == ("EXECUTION_FAILED", "pipeline.steps[0].cases[0].then")


def test_runtime_error_in_when(entrypoint_argv):
    payload = req(case("v", [TIERS[0], {"when": "-name", "then": "1"}]), dataset=[{"price": 50, "name": "a"}])
    assert err(entrypoint_argv, payload, execute=True) == ("EXECUTION_FAILED", "pipeline.steps[0].cases[1].when")


def test_runtime_error_in_else_inside_branch(entrypoint_argv):
    payload = req({"op": "limit", "n": 5}, branch({"when": "otherwise", "steps": [
        case("v", [{"when": "false", "then": "1"}], **{"else": "name - 1"})]}), dataset=[{"name": "a"}])
    assert err(entrypoint_argv, payload, execute=True) == (
        "EXECUTION_FAILED", "pipeline.steps[1].branches[0].steps[0].else")
