#!/usr/bin/env python3
"""ETL pipeline CLI.

Reads a JSON request on STDIN, validates and normalizes the pipeline
specification, optionally executes it over the request's dataset, and writes
a JSON response to STDOUT.

Exit code 0 on success, 1 on error.

Usage::

    python3 etl_pipeline.py                 # validate + normalize (milestone 1)
    python3 etl_pipeline.py --execute       # validate + execute   (milestone 2)
    python3 etl_pipeline.py --execute=false # same as no flag

Steps are ``select``, ``filter``, ``map``, ``rename``, ``limit`` and
``branch`` (milestone 3). A ``branch`` step routes each row to the first of
its ``branches`` whose ``when`` expression is true (or to the trailing
``"otherwise"`` branch), runs that branch's own list of steps, and merges the
results by concatenating them in branch order. Branch step lists may contain
any step type, including further ``branch`` steps, so normalization and
execution are both recursive over a dotted path such as
``pipeline.steps[0].branches[1].steps[2]``.

Request shape::

    {"pipeline": {"steps": [...]}, "dataset": [...]}

Layout of this module:

* ``EtlError``      - the single exception type turned into an error response
* ``tokenize``/``Parser`` - expression syntax checker producing a small AST
* ``evaluate``      - evaluates an AST against a row (null/type semantics)
* ``normalize_*``   - one normalizer per supported op, registered in ``OP_NORMALIZERS``
* ``execute_*``     - one executor per supported op, registered in ``OP_EXECUTORS``
* ``validate_request`` / ``execute_pipeline`` / ``handle`` / ``main``
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import dataclass
from typing import Any, Callable

# --------------------------------------------------------------------------- #
# Errors
# --------------------------------------------------------------------------- #

SCHEMA_VALIDATION_FAILED = "SCHEMA_VALIDATION_FAILED"
UNKNOWN_OP = "UNKNOWN_OP"
MISSING_COLUMN = "MISSING_COLUMN"
BAD_EXPR = "BAD_EXPR"
EXECUTION_FAILED = "EXECUTION_FAILED"
MALFORMED_STEP = "MALFORMED_STEP"

ERROR_PREFIX = "ETL_ERROR: "


class EtlError(Exception):
    """Raised anywhere during validation/execution; converted to the error response."""

    def __init__(self, code: str, message: str, path: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.path = path

    def to_response(self) -> dict[str, Any]:
        return {
            "status": "error",
            "error_code": self.code,
            "message": ERROR_PREFIX + self.message,
            "path": self.path,
        }


def schema_error(message: str, path: str) -> EtlError:
    return EtlError(SCHEMA_VALIDATION_FAILED, message, path)


# --------------------------------------------------------------------------- #
# Expression syntax: tokenizer + recursive-descent parser
# --------------------------------------------------------------------------- #

@dataclass(frozen=True)
class Token:
    kind: str   # "num", "str", "ident", "op", "lparen", "rparen", "eof"
    value: Any
    pos: int


KEYWORDS = {"and", "or", "not", "true", "false", "null"}
COMPARISON_OPS = {">", ">=", "<", "<=", "==", "!="}
ARITHMETIC_OPS = {"+", "-", "*", "/"}
LOGICAL_OPS = {"&&", "||", "!"}
# Longest operators first so ">=" is matched before ">".
OPERATORS = sorted(COMPARISON_OPS | ARITHMETIC_OPS | LOGICAL_OPS, key=len, reverse=True)
# Characters that can form a symbolic operator. A run of these is split into
# known operators; anything that does not split cleanly is "unsupported".
OPERATOR_CHARS = set("=!<>&|*+-/^%~")
# Operators that may legally follow another operator (prefix operators).
PREFIX_OPS = {"-", "+", "!"}


class ExprSyntaxError(ValueError):
    """Expression failed to tokenize or parse; ``pos`` is the character offset."""

    def __init__(self, message: str, pos: int) -> None:
        super().__init__(message)
        self.pos = pos


def split_operator_run(run: str, pos: int) -> list[Token]:
    """Split a run of operator characters into known operator tokens.

    ``a == -1`` yields ``==`` then prefix ``-``; ``a ** b`` has two
    consecutive binary operators and is reported as an unsupported operator.
    """
    tokens: list[Token] = []
    i = 0
    while i < len(run):
        for op in OPERATORS:
            if run.startswith(op, i):
                if tokens and op not in PREFIX_OPS:
                    raise ExprSyntaxError(f"unsupported operator '{run}'", pos)
                tokens.append(Token("op", op, pos + i))
                i += len(op)
                break
        else:
            raise ExprSyntaxError(f"unsupported operator '{run}'", pos)
    return tokens


def tokenize(text: str) -> list[Token]:
    tokens: list[Token] = []
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        if ch.isspace():
            i += 1
            continue
        if ch.isdigit() or (ch == "." and i + 1 < n and text[i + 1].isdigit()):
            start = i
            while i < n and text[i].isdigit():
                i += 1
            if i < n and text[i] == ".":
                i += 1
                while i < n and text[i].isdigit():
                    i += 1
            if i < n and text[i] in "eE":
                j = i + 1
                if j < n and text[j] in "+-":
                    j += 1
                if j < n and text[j].isdigit():
                    i = j
                    while i < n and text[i].isdigit():
                        i += 1
                else:
                    raise ExprSyntaxError("malformed number", start)
            if i < n and (text[i].isalnum() or text[i] == "_"):
                raise ExprSyntaxError("malformed number", start)
            literal = text[start:i]
            value: Any = float(literal) if any(c in literal for c in ".eE") else int(literal)
            tokens.append(Token("num", value, start))
            continue
        if ch in "\"'":
            start = i
            quote = ch
            i += 1
            buf: list[str] = []
            while i < n and text[i] != quote:
                if text[i] == "\\" and i + 1 < n:
                    i += 1
                buf.append(text[i])
                i += 1
            if i >= n:
                raise ExprSyntaxError("unterminated string literal", start)
            i += 1  # closing quote
            tokens.append(Token("str", "".join(buf), start))
            continue
        if ch.isalpha() or ch == "_":
            start = i
            while i < n and (text[i].isalnum() or text[i] == "_"):
                i += 1
            word = text[start:i]
            lowered = word.lower()
            if lowered in KEYWORDS:
                tokens.append(Token("op", lowered, start))
            else:
                tokens.append(Token("ident", word, start))
            continue
        if ch == "(":
            tokens.append(Token("lparen", ch, i))
            i += 1
            continue
        if ch == ")":
            tokens.append(Token("rparen", ch, i))
            i += 1
            continue
        if ch in OPERATOR_CHARS:
            start = i
            while i < n and text[i] in OPERATOR_CHARS:
                i += 1
            tokens.extend(split_operator_run(text[start:i], start))
            continue
        raise ExprSyntaxError(f"unexpected character {ch!r}", i)
    tokens.append(Token("eof", None, n))
    return tokens


class Parser:
    """Recursive-descent parser producing a tuple-based AST.

    Grammar (lowest to highest precedence)::

        or_expr    := and_expr (("or" | "||") and_expr)*
        and_expr   := not_expr (("and" | "&&") not_expr)*
        not_expr   := "not" not_expr | comparison
        comparison := additive (CMP_OP additive)*
        additive   := term (("+" | "-") term)*
        term       := unary (("*" | "/") unary)*
        unary      := ("-" | "+" | "!") unary | primary
        primary    := NUMBER | STRING | IDENT | true | false | null | "(" or_expr ")"

    ``&&``/``||``/``!`` are the C-style spellings; ``and``/``or``/``not`` are
    kept for backwards compatibility. Note that ``!`` binds tightly (like C)
    while ``not`` binds loosely (like Python).

    AST nodes: ("num", v), ("str", v), ("ident", name), ("const", v),
    ("unary", op, node), ("binary", op, left, right). Logical ops are
    canonicalised to "and" / "or" / "not".
    """

    def __init__(self, tokens: list[Token]) -> None:
        self.tokens = tokens
        self.i = 0

    @property
    def cur(self) -> Token:
        return self.tokens[self.i]

    def advance(self) -> Token:
        tok = self.tokens[self.i]
        self.i += 1
        return tok

    def at_op(self, *ops: str) -> bool:
        return self.cur.kind == "op" and self.cur.value in ops

    def parse(self) -> tuple:
        node = self.or_expr()
        if self.cur.kind != "eof":
            raise ExprSyntaxError(f"unexpected token {self.cur.value!r}", self.cur.pos)
        return node

    def or_expr(self) -> tuple:
        node = self.and_expr()
        while self.at_op("or", "||"):
            self.advance()
            node = ("binary", "or", node, self.and_expr())
        return node

    def and_expr(self) -> tuple:
        node = self.not_expr()
        while self.at_op("and", "&&"):
            self.advance()
            node = ("binary", "and", node, self.not_expr())
        return node

    def not_expr(self) -> tuple:
        if self.at_op("not"):
            self.advance()
            return ("unary", "not", self.not_expr())
        return self.comparison()

    def comparison(self) -> tuple:
        node = self.additive()
        while self.at_op(*COMPARISON_OPS):
            op = self.advance().value
            node = ("binary", op, node, self.additive())
        return node

    def additive(self) -> tuple:
        node = self.term()
        while self.at_op("+", "-"):
            op = self.advance().value
            node = ("binary", op, node, self.term())
        return node

    def term(self) -> tuple:
        node = self.unary()
        while self.at_op("*", "/"):
            op = self.advance().value
            node = ("binary", op, node, self.unary())
        return node

    def unary(self) -> tuple:
        if self.at_op("-", "+"):
            op = self.advance().value
            return ("unary", op, self.unary())
        if self.at_op("!"):
            self.advance()
            return ("unary", "not", self.unary())
        return self.primary()

    def primary(self) -> tuple:
        tok = self.cur
        if tok.kind == "num":
            self.advance()
            return ("num", tok.value)
        if tok.kind == "str":
            self.advance()
            return ("str", tok.value)
        if tok.kind == "ident":
            self.advance()
            return ("ident", tok.value)
        if tok.kind == "op" and tok.value in ("true", "false", "null"):
            self.advance()
            return ("const", {"true": True, "false": False, "null": None}[tok.value])
        if tok.kind == "lparen":
            self.advance()
            node = self.or_expr()
            if self.cur.kind != "rparen":
                raise ExprSyntaxError("expected ')'", self.cur.pos)
            self.advance()
            return node
        if tok.kind == "eof":
            raise ExprSyntaxError("unexpected end of expression", tok.pos)
        raise ExprSyntaxError(f"unexpected token {tok.value!r}", tok.pos)


def parse_expression(text: str) -> tuple:
    """Parse an expression string into an AST; raises ExprSyntaxError."""
    return Parser(tokenize(text)).parse()


# --------------------------------------------------------------------------- #
# Expression evaluation
# --------------------------------------------------------------------------- #

class EvalError(ValueError):
    """Runtime failure while evaluating an expression (e.g. arithmetic on a string)."""


def is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def type_name(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if is_number(value):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    return type(value).__name__


def truthy(value: Any) -> bool:
    """JSON truthiness: null, false, 0, "", [] and {} are falsy."""
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    if is_number(value):
        return value != 0
    return bool(value)


def normalize_number(value: Any) -> Any:
    """Collapse integral floats to ints and non-finite floats to null.

    ``12.5 * 8`` should serialise as ``100``, not ``100.0``; infinities and
    NaN are not representable in JSON so they become ``null``.
    """
    if isinstance(value, float):
        if not math.isfinite(value):
            return None
        if value.is_integer() and abs(value) < 2 ** 53:
            return int(value)
    return value


def arithmetic(op: str, left: Any, right: Any) -> Any:
    if left is None or right is None:
        return None
    if not is_number(left) or not is_number(right):
        raise EvalError(f"operator '{op}' requires numeric operands, "
                        f"got {type_name(left)} and {type_name(right)}")
    try:
        if op == "+":
            result = left + right
        elif op == "-":
            result = left - right
        elif op == "*":
            result = left * right
        else:  # "/"
            if right == 0:
                return None
            if isinstance(left, int) and isinstance(right, int) and left % right == 0:
                result = left // right
            else:
                result = left / right
    except OverflowError:
        return None
    return normalize_number(result)


def equals(left: Any, right: Any) -> bool:
    """``==``: false when either side is null or the types differ."""
    if left is None or right is None:
        return False
    if is_number(left) and is_number(right):
        return left == right
    if type(left) is not type(right):
        return False
    return left == right


def not_equals(left: Any, right: Any) -> bool:
    """``!=``: like ``==``, null or type mismatch yields false (not true)."""
    if left is None or right is None:
        return False
    if is_number(left) and is_number(right):
        return left != right
    if type(left) is not type(right):
        return False
    return left != right


def ordering(op: str, left: Any, right: Any) -> bool:
    """``<``/``<=``/``>``/``>=``: only numbers with numbers or strings with strings."""
    if left is None or right is None:
        return False
    both_numbers = is_number(left) and is_number(right)
    both_strings = isinstance(left, str) and isinstance(right, str)
    if not (both_numbers or both_strings):
        return False
    if op == "<":
        return left < right
    if op == "<=":
        return left <= right
    if op == ">":
        return left > right
    return left >= right


def evaluate(node: tuple, row: dict) -> Any:
    """Evaluate an AST node against a row; raises EvalError on type failures."""
    kind = node[0]
    if kind in ("num", "str", "const"):
        return node[1]
    if kind == "ident":
        return row.get(node[1])  # missing identifiers resolve to null
    if kind == "unary":
        _, op, operand = node
        value = evaluate(operand, row)
        if op == "not":
            return not truthy(value)
        if value is None:
            return None
        if not is_number(value):
            raise EvalError(f"unary '{op}' requires a numeric operand, got {type_name(value)}")
        return normalize_number(-value if op == "-" else value)
    # binary
    _, op, left_node, right_node = node
    if op == "and":
        return truthy(evaluate(left_node, row)) and truthy(evaluate(right_node, row))
    if op == "or":
        return truthy(evaluate(left_node, row)) or truthy(evaluate(right_node, row))
    left = evaluate(left_node, row)
    right = evaluate(right_node, row)
    if op in ARITHMETIC_OPS:
        return arithmetic(op, left, right)
    if op == "==":
        return equals(left, right)
    if op == "!=":
        return not_equals(left, right)
    return ordering(op, left, right)


# --------------------------------------------------------------------------- #
# Step normalization
# --------------------------------------------------------------------------- #

def require_trimmed_string(step: dict, field: str, path: str) -> str:
    """Fetch a required string field, trim it, reject if empty."""
    field_path = f"{path}.{field}"
    if field not in step:
        raise schema_error(f"missing required field '{field}'", field_path)
    value = step[field]
    if not isinstance(value, str):
        raise schema_error(f"field '{field}' must be a string", field_path)
    trimmed = value.strip()
    if not trimmed:
        raise schema_error(f"field '{field}' must not be empty", field_path)
    return trimmed


def require_expression(step: dict, field: str, path: str) -> str:
    text = require_trimmed_string(step, field, path)
    try:
        parse_expression(text)
    except ExprSyntaxError as exc:
        raise EtlError(BAD_EXPR, str(exc), f"{path}.{field}") from None
    return text


def normalize_select(step: dict, path: str) -> dict:
    field_path = f"{path}.columns"
    if "columns" not in step:
        raise schema_error("missing required field 'columns'", field_path)
    columns = step["columns"]
    if not isinstance(columns, list):
        raise schema_error("field 'columns' must be an array of strings", field_path)
    for idx, col in enumerate(columns):
        if not isinstance(col, str):
            raise schema_error("column names must be strings", f"{field_path}[{idx}]")
        if col == "":
            raise schema_error("column names must not be empty", f"{field_path}[{idx}]")
    return {"op": "select", "columns": list(columns)}


def normalize_filter(step: dict, path: str) -> dict:
    return {"op": "filter", "where": require_expression(step, "where", path)}


def normalize_map(step: dict, path: str) -> dict:
    as_name = require_trimmed_string(step, "as", path)
    expr = require_expression(step, "expr", path)
    return {"op": "map", "as": as_name, "expr": expr}


def normalize_rename(step: dict, path: str) -> dict:
    has_pair = "from" in step or "to" in step
    has_mapping = "mapping" in step
    if has_pair and has_mapping:
        raise schema_error("rename accepts either 'from'/'to' or 'mapping', not both", path)
    if has_pair:
        src = require_trimmed_string(step, "from", path)
        dst = require_trimmed_string(step, "to", path)
        return {"op": "rename", "mapping": {src: dst}}
    if not has_mapping:
        raise schema_error("rename requires 'from'/'to' or 'mapping'", path)
    field_path = f"{path}.mapping"
    mapping = step["mapping"]
    if not isinstance(mapping, dict):
        raise schema_error("field 'mapping' must be an object", field_path)
    if not mapping:
        raise schema_error("field 'mapping' must not be empty", field_path)
    for key, value in mapping.items():
        if key == "":
            raise schema_error("mapping keys must not be empty", field_path)
        if not isinstance(value, str):
            raise schema_error("mapping values must be strings", f"{field_path}.{key}")
        if value == "":
            raise schema_error("mapping values must not be empty", f"{field_path}.{key}")
    return {"op": "rename", "mapping": dict(mapping)}


def normalize_limit(step: dict, path: str) -> dict:
    field_path = f"{path}.n"
    if "n" not in step:
        raise schema_error("missing required field 'n'", field_path)
    n = step["n"]
    if isinstance(n, bool) or not isinstance(n, int):
        raise schema_error("field 'n' must be an integer", field_path)
    if n < 0:
        raise schema_error("field 'n' must be >= 0", field_path)
    return {"op": "limit", "n": n}


OTHERWISE = "otherwise"
MERGE_STRATEGIES = {"concat"}


def normalize_branch_entry(entry: Any, path: str) -> dict:
    """Normalize one element of ``branches``: ``{id?, when, steps}``."""
    if not isinstance(entry, dict):
        raise schema_error("branch must be an object", path)
    out: dict = {}
    if "id" in entry:
        if not isinstance(entry["id"], str):
            raise schema_error("field 'id' must be a string", f"{path}.id")
        out["id"] = entry["id"]
    when = require_trimmed_string(entry, "when", path)
    if when.lower() == OTHERWISE:
        out["when"] = OTHERWISE
    else:
        out["when"] = require_expression(entry, "when", path)
    steps_path = f"{path}.steps"
    if "steps" not in entry:
        raise schema_error("missing required field 'steps'", steps_path)
    if not isinstance(entry["steps"], list):
        raise schema_error("field 'steps' must be an array", steps_path)
    out["steps"] = normalize_steps(entry["steps"], steps_path)
    return out


def normalize_merge(step: dict, path: str) -> dict:
    """Normalize ``merge``; absent merge or strategy defaults to ``concat``."""
    merge_path = f"{path}.merge"
    merge = step.get("merge", {})
    if merge is None:
        merge = {}
    if not isinstance(merge, dict):
        raise schema_error("field 'merge' must be an object", merge_path)
    strategy = merge.get("strategy", "concat")
    if strategy is None:
        strategy = "concat"
    if not isinstance(strategy, str):
        raise schema_error("field 'strategy' must be a string", f"{merge_path}.strategy")
    strategy = strategy.strip().lower()
    if strategy not in MERGE_STRATEGIES:
        raise schema_error(f"unsupported merge strategy '{strategy}'", f"{merge_path}.strategy")
    return {"strategy": strategy}


def normalize_branch(step: dict, path: str) -> dict:
    branches_path = f"{path}.branches"
    if "branches" not in step:
        raise schema_error("missing required field 'branches'", branches_path)
    branches = step["branches"]
    if not isinstance(branches, list):
        raise schema_error("field 'branches' must be an array", branches_path)
    if not branches:
        raise schema_error("field 'branches' must not be empty", branches_path)
    normalized = [normalize_branch_entry(entry, f"{branches_path}[{idx}]")
                  for idx, entry in enumerate(branches)]
    otherwise_positions = [idx for idx, b in enumerate(normalized) if b["when"] == OTHERWISE]
    if len(otherwise_positions) > 1:
        raise EtlError(MALFORMED_STEP, "at most one 'otherwise' branch is allowed", branches_path)
    if otherwise_positions and otherwise_positions[0] != len(normalized) - 1:
        raise EtlError(MALFORMED_STEP, "the 'otherwise' branch must be last", branches_path)
    return {"op": "branch", "branches": normalized, "merge": normalize_merge(step, path)}


OP_NORMALIZERS: dict[str, Callable[[dict, str], dict]] = {
    "select": normalize_select,
    "filter": normalize_filter,
    "map": normalize_map,
    "rename": normalize_rename,
    "limit": normalize_limit,
    "branch": normalize_branch,
}


def order_step_keys(step: dict) -> dict:
    """Return the step with 'op' first and remaining keys alphabetical."""
    ordered = {"op": step["op"]}
    for key in sorted(k for k in step if k != "op"):
        ordered[key] = step[key]
    return ordered


def normalize_step(step: Any, path: str) -> dict:
    """Normalize one step; ``path`` is where it lives (e.g. ``pipeline.steps[2]``)."""
    if not isinstance(step, dict):
        raise schema_error("step must be an object", path)
    if "op" not in step:
        raise schema_error("missing required field 'op'", f"{path}.op")
    op = step["op"]
    if not isinstance(op, str):
        raise schema_error("field 'op' must be a string", f"{path}.op")
    op = op.strip().lower()
    if not op:
        raise schema_error("field 'op' must not be empty", f"{path}.op")
    normalizer = OP_NORMALIZERS.get(op)
    if normalizer is None:
        raise EtlError(UNKNOWN_OP, f"unsupported op '{op}'", f"{path}.op")
    return order_step_keys(normalizer(step, path))


def normalize_steps(steps: list, path: str) -> list[dict]:
    """Normalize a list of steps located at ``path`` (e.g. ``pipeline.steps``)."""
    return [normalize_step(step, f"{path}[{idx}]") for idx, step in enumerate(steps)]


# --------------------------------------------------------------------------- #
# Step execution
# --------------------------------------------------------------------------- #
#
# Each executor takes (normalized_step, raw_step, path, rows) and returns the
# new list of rows. ``raw_step`` is the step as written in the request; it is
# only needed to build error paths that refer to the original spelling
# (e.g. ``rename`` written with from/to rather than mapping). Rows are never
# shared with the input dataset, so executors may mutate them in place.

Rows = list[dict]


def missing_column(column: str, path: str) -> EtlError:
    return EtlError(MISSING_COLUMN, f"column '{column}' not found in row", path)


def compile_expression(text: str, path: str) -> tuple:
    try:
        return parse_expression(text)
    except ExprSyntaxError as exc:  # already validated; defensive
        raise EtlError(BAD_EXPR, str(exc), path) from None


def evaluate_or_fail(ast: tuple, text: str, row: dict, path: str) -> Any:
    try:
        return evaluate(ast, row)
    except EvalError as exc:
        raise EtlError(EXECUTION_FAILED, f"failed to evaluate '{text}': {exc}", path) from None


def execute_select(step: dict, raw_step: dict, path: str, rows: Rows) -> Rows:
    columns = step["columns"]
    result: Rows = []
    for row in rows:
        out: dict = {}
        for idx, col in enumerate(columns):
            if col not in row:
                raise missing_column(col, f"{path}.columns[{idx}]")
            out[col] = row[col]
        result.append(out)
    return result


def execute_filter(step: dict, raw_step: dict, path: str, rows: Rows) -> Rows:
    where = step["where"]
    field_path = f"{path}.where"
    ast = compile_expression(where, field_path)
    return [row for row in rows if truthy(evaluate_or_fail(ast, where, row, field_path))]


def execute_map(step: dict, raw_step: dict, path: str, rows: Rows) -> Rows:
    expr = step["expr"]
    target = step["as"]
    field_path = f"{path}.expr"
    ast = compile_expression(expr, field_path)
    for row in rows:
        row[target] = evaluate_or_fail(ast, expr, row, field_path)
    return rows


def rename_column(row: dict, src: str, dst: str) -> dict:
    """Rename ``src`` to ``dst`` keeping its position; an existing ``dst`` is replaced."""
    if src == dst:
        return row
    out: dict = {}
    for key, value in row.items():
        if key == src:
            out[dst] = value
        elif key != dst:
            out[key] = value
    return out


def execute_rename(step: dict, raw_step: dict, path: str, rows: Rows) -> Rows:
    uses_pair = "from" in raw_step
    for src, dst in step["mapping"].items():
        source_path = f"{path}.from" if uses_pair else f"{path}.mapping.{src}"
        for idx, row in enumerate(rows):
            if src not in row:
                raise missing_column(src, source_path)
            rows[idx] = rename_column(row, src, dst)
    return rows


def execute_limit(step: dict, raw_step: dict, path: str, rows: Rows) -> Rows:
    return rows[: step["n"]]


def execute_branch(step: dict, raw_step: dict, path: str, rows: Rows) -> Rows:
    """Route each row to the first branch whose ``when`` holds, run that
    branch's steps over its rows, then concatenate the results in branch order.

    Rows matching no branch are dropped. ``when`` conditions are evaluated
    lazily, so a later branch's condition is never evaluated for a row that
    an earlier branch already claimed.
    """
    branches = step["branches"]
    conditions: list[tuple | None] = []  # None marks the "otherwise" branch
    for idx, branch in enumerate(branches):
        when = branch["when"]
        conditions.append(None if when == OTHERWISE
                          else compile_expression(when, f"{path}.branches[{idx}].when"))

    buckets: list[Rows] = [[] for _ in branches]
    for row in rows:
        for idx, (branch, ast) in enumerate(zip(branches, conditions)):
            when_path = f"{path}.branches[{idx}].when"
            if ast is None or truthy(evaluate_or_fail(ast, branch["when"], row, when_path)):
                buckets[idx].append(row)
                break

    merged: Rows = []
    for idx, (branch, bucket) in enumerate(zip(branches, buckets)):
        raw_branch_steps = raw_step["branches"][idx]["steps"]
        merged.extend(execute_steps(branch["steps"], raw_branch_steps,
                                    f"{path}.branches[{idx}].steps", bucket))
    return merged  # merge.strategy is always "concat" (normalizer enforces it)


OP_EXECUTORS: dict[str, Callable[[dict, dict, str, Rows], Rows]] = {
    "select": execute_select,
    "filter": execute_filter,
    "map": execute_map,
    "rename": execute_rename,
    "limit": execute_limit,
    "branch": execute_branch,
}


def execute_steps(steps: list[dict], raw_steps: list, path: str, rows: Rows) -> Rows:
    """Run normalized ``steps`` (located at ``path``) over ``rows`` in order."""
    for idx, step in enumerate(steps):
        step_path = f"{path}[{idx}]"
        executor = OP_EXECUTORS.get(step["op"])
        if executor is None:  # normalizer guarantees a known op; defensive
            raise EtlError(UNKNOWN_OP, f"unsupported op '{step['op']}'", f"{step_path}.op")
        rows = executor(step, raw_steps[idx], step_path, rows)
    return rows


def execute_pipeline(steps: list[dict], raw_steps: list, dataset: list[dict]) -> tuple[Rows, dict]:
    """Run normalized top-level ``steps`` over ``dataset``; return (rows, metrics)."""
    rows = execute_steps(steps, raw_steps, "pipeline.steps", [dict(row) for row in dataset])
    return rows, {"rows_in": len(dataset), "rows_out": len(rows)}


# --------------------------------------------------------------------------- #
# Request handling
# --------------------------------------------------------------------------- #

def validate_dataset(dataset: Any) -> list[dict]:
    if not isinstance(dataset, list):
        raise schema_error("'dataset' must be an array of objects", "dataset")
    for idx, row in enumerate(dataset):
        if not isinstance(row, dict):
            raise schema_error("dataset rows must be objects", f"dataset[{idx}]")
    return dataset


def validate_request(request: Any) -> tuple[list[dict], list, list[dict]]:
    """Validate the top-level request; return (normalized_steps, raw_steps, dataset)."""
    if not isinstance(request, dict):
        raise schema_error("request must be a JSON object", "")
    if "pipeline" not in request:
        raise schema_error("missing required field 'pipeline'", "pipeline")
    pipeline = request["pipeline"]
    if not isinstance(pipeline, dict):
        raise schema_error("'pipeline' must be an object", "pipeline")
    if "steps" not in pipeline:
        raise schema_error("missing required field 'steps'", "pipeline.steps")
    steps = pipeline["steps"]
    if not isinstance(steps, list):
        raise schema_error("'pipeline.steps' must be an array", "pipeline.steps")
    if "dataset" not in request:
        raise schema_error("missing required field 'dataset'", "dataset")
    dataset = validate_dataset(request["dataset"])
    normalized = normalize_steps(steps, "pipeline.steps")
    return normalized, steps, dataset


def handle(raw_input: str, execute: bool = False) -> tuple[dict, int]:
    """Process raw STDIN text; return (response_object, exit_code).

    With ``execute=False`` the response carries the normalized pipeline; with
    ``execute=True`` it carries the transformed ``data`` and ``metrics``.
    """
    try:
        try:
            request = json.loads(raw_input)
        except json.JSONDecodeError as exc:
            raise schema_error(f"invalid JSON input: {exc.msg}", "") from None
        steps, raw_steps, dataset = validate_request(request)
        if not execute:
            return {"status": "ok", "normalized": {"steps": steps}}, 0
        data, metrics = execute_pipeline(steps, raw_steps, dataset)
    except EtlError as err:
        return err.to_response(), 1
    return {"status": "ok", "data": data, "metrics": metrics}, 0


def parse_bool_flag(text: str) -> bool:
    lowered = text.strip().lower()
    if lowered in ("1", "true", "yes", "y", "on"):
        return True
    if lowered in ("0", "false", "no", "n", "off"):
        return False
    raise argparse.ArgumentTypeError(f"expected a boolean, got {text!r}")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="etl_pipeline.py",
        description="Validate, normalize and optionally execute an ETL pipeline read from STDIN.",
    )
    parser.add_argument(
        "--execute",
        nargs="?", const=True, default=False, type=parse_bool_flag, metavar="BOOL",
        help="execute the pipeline over the dataset and return data + metrics "
             "(default: false; return the normalized pipeline)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    response, code = handle(sys.stdin.read(), execute=args.execute)
    sys.stdout.write(json.dumps(response))
    sys.stdout.write("\n")
    sys.stdout.flush()
    return code


if __name__ == "__main__":
    sys.exit(main())
