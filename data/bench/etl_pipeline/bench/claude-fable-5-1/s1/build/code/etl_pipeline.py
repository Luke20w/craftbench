#!/usr/bin/env python3
"""ETL pipeline CLI.

Reads a JSON request from STDIN, validates and normalizes the pipeline
specification, and writes a JSON response to STDOUT.

    echo '{"pipeline":{"steps":[]},"dataset":[]}' | python3 etl_pipeline.py
    echo '{...}' | python3 etl_pipeline.py --execute

Without ``--execute`` the response carries the normalized pipeline. With
``--execute`` the pipeline is run over ``dataset`` and the response carries
``data`` (the resulting rows) and ``metrics`` (``rows_in``/``rows_out``).

Exit code 0 on success, 1 on error. Errors are reported as JSON on STDOUT
(never as a traceback) so callers can always parse the output.

Layout of this module:

    EtlError              -- the single exception type; carries code + path
    Expression parsing    -- tokenizer + recursive-descent parser producing an AST
    Expression evaluation -- evaluate(ast, row) with null/type semantics
    Step validators       -- validate_<op>(step, path, schema) -> normalized fields
    Step executors        -- execute_<op>(step, raw, path, rows) -> rows
    OPS registry          -- op name -> (validator, executor)
    Request handling      -- top-level shape checks, normalize, execute
    CLI entry point       -- parse_args(), run(), main()
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from typing import Any, Callable, NamedTuple

# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------

SCHEMA_VALIDATION_FAILED = "SCHEMA_VALIDATION_FAILED"
UNKNOWN_OP = "UNKNOWN_OP"
MISSING_COLUMN = "MISSING_COLUMN"
BAD_EXPR = "BAD_EXPR"
EXECUTION_FAILED = "EXECUTION_FAILED"
MALFORMED_STEP = "MALFORMED_STEP"

MESSAGE_PREFIX = "ETL_ERROR: "


class EtlError(Exception):
    """A validation or execution failure that maps onto the error response."""

    def __init__(self, code: str, message: str, path: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.path = path

    def to_response(self) -> dict[str, Any]:
        return {
            "status": "error",
            "error_code": self.code,
            "message": MESSAGE_PREFIX + self.message,
            "path": self.path,
        }


def schema_error(message: str, path: str) -> EtlError:
    return EtlError(SCHEMA_VALIDATION_FAILED, message, path)


# ---------------------------------------------------------------------------
# Expression parsing
# ---------------------------------------------------------------------------
#
# Grammar (lowest to highest precedence):
#
#   or_expr   := and_expr ( ( "or" | "||" ) and_expr )*
#   and_expr  := not_expr ( ( "and" | "&&" ) not_expr )*
#   not_expr  := "not" not_expr | comparison
#   comparison:= additive ( ( ">" | ">=" | "<" | "<=" | "==" | "!=" ) additive )*
#   additive  := term ( ( "+" | "-" ) term )*
#   term      := unary ( ( "*" | "/" ) unary )*
#   unary     := "-" unary | "!" unary | primary
#   primary   := NUMBER | STRING | IDENT | "true" | "false" | "null"
#              | "(" or_expr ")"
#
# ``!`` binds like a C-style unary operator (tighter than comparison), the
# ``not`` keyword binds like Python's (looser than comparison). Both produce
# the same ("not", node) AST node.
#
# The parser returns a small tuple-based AST that ``evaluate`` consumes:
#
#   ("num", 1.5) ("str", "x") ("bool", True) ("null", None) ("col", "qty")
#   ("unary", "-", node) ("not", node) ("binop", "+", left, right)
#   ("and", left, right) ("or", left, right)
#
# Number literals are ``int`` when written without a fraction/exponent and
# ``float`` otherwise, so integer arithmetic stays integral in the output.

KEYWORDS = {"and", "or", "not", "true", "false", "null"}
COMPARISON_OPS = {">", ">=", "<", "<=", "==", "!="}
ADDITIVE_OPS = {"+", "-"}
TERM_OPS = {"*", "/"}
ARITHMETIC_OPS = ADDITIVE_OPS | TERM_OPS

# Any run of these characters is one "operator run" that must split cleanly
# into KNOWN_OPERATORS, otherwise it is reported as an unsupported operator
# (so "**" is rejected as a whole rather than parsed as "*" "*").
OPERATOR_CHARS = set("*/+-=<>!&|^%~?:")
# Longest first so ">=" is matched before ">".
KNOWN_OPERATORS = (">=", "<=", "==", "!=", "&&", "||", ">", "<", "+", "-", "*", "/", "!")
# Operators allowed to follow another operator without whitespace, e.g. "a*-b".
UNARY_PREFIX_OPS = {"-", "!"}

Token = tuple[str, Any]  # (kind, value); kind in {num, str, ident, kw, punct, eof}


class ExprSyntaxError(ValueError):
    """Raised by the tokenizer/parser; converted to BAD_EXPR by callers."""


def split_operator_run(run: str) -> list[Token]:
    """Split a run of operator characters into known operator tokens.

    The first operator may be anything known; following ones must be unary
    prefixes ("-" or "!"). Anything else is an unsupported operator.
    """
    tokens: list[Token] = []
    rest = run
    while rest:
        for op in KNOWN_OPERATORS:
            if rest.startswith(op) and (not tokens or op in UNARY_PREFIX_OPS):
                tokens.append(("punct", op))
                rest = rest[len(op):]
                break
        else:
            raise ExprSyntaxError(f"unsupported operator '{run}'")
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
            is_float = False
            while i < n and text[i].isdigit():
                i += 1
            if i < n and text[i] == ".":
                is_float = True
                i += 1
                while i < n and text[i].isdigit():
                    i += 1
            if i < n and text[i] in "eE":
                j = i + 1
                if j < n and text[j] in "+-":
                    j += 1
                if j < n and text[j].isdigit():
                    is_float = True
                    i = j
                    while i < n and text[i].isdigit():
                        i += 1
            if i < n and (text[i].isalnum() or text[i] == "_"):
                raise ExprSyntaxError(f"invalid number at position {start}")
            literal = text[start:i]
            tokens.append(("num", float(literal) if is_float else int(literal)))
            continue
        if ch.isalpha() or ch == "_":
            start = i
            while i < n and (text[i].isalnum() or text[i] == "_"):
                i += 1
            word = text[start:i]
            if word.lower() in KEYWORDS:
                tokens.append(("kw", word.lower()))
            else:
                tokens.append(("ident", word))
            continue
        if ch in ("'", '"'):
            quote = ch
            i += 1
            buf = []
            while i < n and text[i] != quote:
                if text[i] == "\\" and i + 1 < n:
                    i += 1
                buf.append(text[i])
                i += 1
            if i >= n:
                raise ExprSyntaxError("unterminated string literal")
            i += 1
            tokens.append(("str", "".join(buf)))
            continue
        if ch in "()":
            tokens.append(("punct", ch))
            i += 1
            continue
        if ch in OPERATOR_CHARS:
            start = i
            while i < n and text[i] in OPERATOR_CHARS:
                i += 1
            tokens.extend(split_operator_run(text[start:i]))
            continue
        raise ExprSyntaxError(f"unexpected character '{ch}' at position {i}")
    tokens.append(("eof", None))
    return tokens


class Parser:
    def __init__(self, tokens: list[Token]) -> None:
        self.tokens = tokens
        self.pos = 0

    # -- helpers ----------------------------------------------------------
    def peek(self) -> Token:
        return self.tokens[self.pos]

    def advance(self) -> Token:
        tok = self.tokens[self.pos]
        self.pos += 1
        return tok

    def at(self, kind: str, value: Any = None) -> bool:
        tok = self.peek()
        return tok[0] == kind and (value is None or tok[1] == value)

    def at_punct_in(self, values: set[str]) -> bool:
        tok = self.peek()
        return tok[0] == "punct" and tok[1] in values

    def expect_punct(self, value: str) -> None:
        if not self.at("punct", value):
            raise ExprSyntaxError(f"expected '{value}' but found {self.describe()}")
        self.advance()

    def describe(self) -> str:
        kind, value = self.peek()
        if kind == "eof":
            return "end of expression"
        return f"'{value}'"

    # -- grammar ----------------------------------------------------------
    def parse(self) -> tuple:
        node = self.or_expr()
        if not self.at("eof"):
            raise ExprSyntaxError(f"unexpected {self.describe()}")
        return node

    def or_expr(self) -> tuple:
        node = self.and_expr()
        while self.at("kw", "or") or self.at("punct", "||"):
            self.advance()
            node = ("or", node, self.and_expr())
        return node

    def and_expr(self) -> tuple:
        node = self.not_expr()
        while self.at("kw", "and") or self.at("punct", "&&"):
            self.advance()
            node = ("and", node, self.not_expr())
        return node

    def not_expr(self) -> tuple:
        if self.at("kw", "not"):
            self.advance()
            return ("not", self.not_expr())
        return self.comparison()

    def comparison(self) -> tuple:
        node = self.additive()
        while self.at_punct_in(COMPARISON_OPS):
            op = self.advance()[1]
            node = ("binop", op, node, self.additive())
        return node

    def additive(self) -> tuple:
        node = self.term()
        while self.at_punct_in(ADDITIVE_OPS):
            op = self.advance()[1]
            node = ("binop", op, node, self.term())
        return node

    def term(self) -> tuple:
        node = self.unary()
        while self.at_punct_in(TERM_OPS):
            op = self.advance()[1]
            node = ("binop", op, node, self.unary())
        return node

    def unary(self) -> tuple:
        if self.at("punct", "-"):
            self.advance()
            return ("unary", "-", self.unary())
        if self.at("punct", "!"):
            self.advance()
            return ("not", self.unary())
        return self.primary()

    def primary(self) -> tuple:
        kind, value = self.peek()
        if kind == "num":
            self.advance()
            return ("num", value)
        if kind == "str":
            self.advance()
            return ("str", value)
        if kind == "ident":
            self.advance()
            return ("col", value)
        if kind == "kw" and value in ("true", "false"):
            self.advance()
            return ("bool", value == "true")
        if kind == "kw" and value == "null":
            self.advance()
            return ("null", None)
        if kind == "punct" and value == "(":
            self.advance()
            node = self.or_expr()
            self.expect_punct(")")
            return node
        raise ExprSyntaxError(f"unexpected {self.describe()}")


def parse_expression(text: str) -> tuple:
    """Parse an expression string into an AST; raises ExprSyntaxError."""
    return Parser(tokenize(text)).parse()


def expression_columns(node: tuple) -> list[str]:
    """Column names referenced by an AST, in first-seen order."""
    found: list[str] = []

    def walk(n: tuple) -> None:
        kind = n[0]
        if kind == "col":
            if n[1] not in found:
                found.append(n[1])
        elif kind in ("unary",):
            walk(n[2])
        elif kind == "not":
            walk(n[1])
        elif kind == "binop":
            walk(n[2])
            walk(n[3])
        elif kind in ("and", "or"):
            walk(n[1])
            walk(n[2])

    walk(node)
    return found


# ---------------------------------------------------------------------------
# Expression evaluation
# ---------------------------------------------------------------------------
#
# Value model (JSON values as decoded by ``json``):
#
#   null     -> None            number -> int | float (never bool)
#   bool     -> bool            string -> str
#   other    -> list | dict     (can appear in rows; only equality works)
#
# Semantics:
#   * Arithmetic with a null operand -> null. Division by zero -> null.
#     Non-finite results (overflow) -> null. Non-numeric operands -> error.
#   * Equality/ordering with a null operand or mismatched types -> false.
#   * Boolean operators use truthiness: null, false, 0, "", [] and {} are
#     falsy. ``&&``/``||`` short-circuit and return a bool.
#   * Missing identifiers resolve to null.


class ExprEvalError(ValueError):
    """Raised by ``evaluate``; converted to EXECUTION_FAILED by executors."""


def type_name(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, (int, float)):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    return type(value).__name__


def is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def normalize_number(value: int | float) -> int | float | None:
    """Collapse integral floats to int (12.5 * 8 -> 100); non-finite -> null."""
    if isinstance(value, float):
        if not math.isfinite(value):
            return None
        if value.is_integer() and abs(value) < 2**53:
            return int(value)
    return value


def truthy(value: Any) -> bool:
    return bool(value)


def apply_arithmetic(op: str, left: Any, right: Any) -> Any:
    if left is None or right is None:
        return None
    if not is_number(left) or not is_number(right):
        raise ExprEvalError(
            f"cannot apply '{op}' to {type_name(left)} and {type_name(right)}"
        )
    if op == "+":
        result = left + right
    elif op == "-":
        result = left - right
    elif op == "*":
        result = left * right
    else:  # "/"
        if right == 0:
            return None
        result = left / right
    return normalize_number(result)


def apply_comparison(op: str, left: Any, right: Any) -> bool:
    if left is None or right is None:
        return False
    if type_name(left) != type_name(right):
        return False
    if op == "==":
        return left == right
    if op == "!=":
        return left != right
    if type_name(left) not in ("number", "string", "bool"):
        return False
    if op == "<":
        return left < right
    if op == "<=":
        return left <= right
    if op == ">":
        return left > right
    return left >= right


def evaluate(node: tuple, row: dict[str, Any]) -> Any:
    """Evaluate an AST against a row; raises ExprEvalError on type errors."""
    kind = node[0]
    if kind in ("num", "str", "bool", "null"):
        return node[1]
    if kind == "col":
        return row.get(node[1])
    if kind == "unary":
        value = evaluate(node[2], row)
        if value is None:
            return None
        if not is_number(value):
            raise ExprEvalError(f"cannot negate {type_name(value)}")
        return normalize_number(-value)
    if kind == "not":
        return not truthy(evaluate(node[1], row))
    if kind == "and":
        return truthy(evaluate(node[1], row)) and truthy(evaluate(node[2], row))
    if kind == "or":
        return truthy(evaluate(node[1], row)) or truthy(evaluate(node[2], row))
    if kind == "binop":
        op = node[1]
        left = evaluate(node[2], row)
        right = evaluate(node[3], row)
        if op in ARITHMETIC_OPS:
            return apply_arithmetic(op, left, right)
        return apply_comparison(op, left, right)
    raise ExprEvalError(f"unknown AST node '{kind}'")


# ---------------------------------------------------------------------------
# Field helpers
# ---------------------------------------------------------------------------


def require_string(step: dict, field: str, path: str) -> str:
    """Return the raw string value of a required field (not trimmed)."""
    if field not in step:
        raise schema_error(f"missing required field '{field}'", f"{path}.{field}")
    value = step[field]
    if not isinstance(value, str):
        raise schema_error(f"field '{field}' must be a string", f"{path}.{field}")
    return value


def require_trimmed_string(step: dict, field: str, path: str) -> str:
    """Return the trimmed value of a required string field; reject empties."""
    value = require_string(step, field, path).strip()
    if not value:
        raise schema_error(
            f"field '{field}' must not be empty", f"{path}.{field}"
        )
    return value


def require_expression(step: dict, field: str, path: str, schema: "Schema") -> str:
    """Validate a trimmed expression field; returns the trimmed text."""
    text = require_trimmed_string(step, field, path)
    try:
        ast = parse_expression(text)
    except ExprSyntaxError as exc:
        raise EtlError(BAD_EXPR, str(exc), f"{path}.{field}")
    for column in expression_columns(ast):
        schema.require(column, f"{path}.{field}")
    return text


def is_integer(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


# ---------------------------------------------------------------------------
# Column schema tracking (static checks used in normalize mode)
# ---------------------------------------------------------------------------


class Schema:
    """Tracks the set of columns available to each step.

    When the dataset is empty there is nothing to infer, so column checks are
    skipped entirely (``known`` is None). Otherwise the starting columns are
    the union of keys across all rows and each step updates the set.

    ``Schema.disabled()`` is used in execute mode, where columns are checked
    per row by the executors instead and missing expression identifiers
    resolve to null.
    """

    def __init__(self, dataset: list[dict]) -> None:
        self.known: set[str] | None = None
        if dataset:
            self.known = set()
            for row in dataset:
                self.known.update(row.keys())

    @classmethod
    def disabled(cls) -> "Schema":
        return cls([])

    def copy(self) -> "Schema":
        clone = Schema([])
        clone.known = None if self.known is None else set(self.known)
        return clone

    def merge(self, others: list["Schema"]) -> None:
        """Replace the known set with the union of ``others`` (branch merge)."""
        if self.known is not None:
            self.known = set()
            for other in others:
                self.known.update(other.known or ())

    def require(self, column: str, path: str) -> None:
        if self.known is not None and column not in self.known:
            raise EtlError(MISSING_COLUMN, f"unknown column '{column}'", path)

    def restrict(self, columns: list[str]) -> None:
        if self.known is not None:
            self.known = set(columns)

    def add(self, column: str) -> None:
        if self.known is not None:
            self.known.add(column)

    def rename(self, mapping: dict[str, str]) -> None:
        if self.known is not None:
            for old, new in mapping.items():
                self.known.discard(old)
                self.known.add(new)


# ---------------------------------------------------------------------------
# Step validators
# ---------------------------------------------------------------------------
#
# Each validator receives the raw step object, the step's path, and the
# running column schema. It returns the normalized step *without* the "op"
# key; the caller prepends "op" and sorts the remaining keys alphabetically.


def validate_select(step: dict, path: str, schema: Schema) -> dict[str, Any]:
    field_path = f"{path}.columns"
    if "columns" not in step:
        raise schema_error("missing required field 'columns'", field_path)
    columns = step["columns"]
    if not isinstance(columns, list):
        raise schema_error("field 'columns' must be an array of strings", field_path)
    if not columns:
        raise schema_error("field 'columns' must not be empty", field_path)
    for i, column in enumerate(columns):
        if not isinstance(column, str):
            raise schema_error(f"column at index {i} must be a string", f"{field_path}[{i}]")
        if not column.strip():
            raise schema_error(f"column at index {i} must not be empty", f"{field_path}[{i}]")
        schema.require(column, f"{field_path}[{i}]")
    schema.restrict(columns)
    return {"columns": list(columns)}


def validate_filter(step: dict, path: str, schema: Schema) -> dict[str, Any]:
    where = require_expression(step, "where", path, schema)
    return {"where": where}


def validate_map(step: dict, path: str, schema: Schema) -> dict[str, Any]:
    alias = require_trimmed_string(step, "as", path)
    expr = require_expression(step, "expr", path, schema)
    schema.add(alias)
    return {"as": alias, "expr": expr}


def validate_rename(step: dict, path: str, schema: Schema) -> dict[str, Any]:
    has_pair = "from" in step or "to" in step
    has_mapping = "mapping" in step
    if has_pair and has_mapping:
        raise schema_error(
            "rename accepts either 'from'/'to' or 'mapping', not both", path
        )
    if has_pair:
        source = require_trimmed_string(step, "from", path)
        target = require_trimmed_string(step, "to", path)
        schema.require(source, f"{path}.from")
        mapping = {source: target}
    elif has_mapping:
        raw = step["mapping"]
        field_path = f"{path}.mapping"
        if not isinstance(raw, dict):
            raise schema_error("field 'mapping' must be an object", field_path)
        if not raw:
            raise schema_error("field 'mapping' must not be empty", field_path)
        for key, value in raw.items():
            if not key.strip():
                raise schema_error("mapping keys must not be empty", field_path)
            if not isinstance(value, str) or not value.strip():
                raise schema_error(
                    f"mapping value for '{key}' must be a non-empty string",
                    f"{field_path}.{key}",
                )
            schema.require(key, f"{field_path}.{key}")
        mapping = dict(raw)
    else:
        raise schema_error(
            "rename requires either 'from' and 'to' or 'mapping'", path
        )
    schema.rename(mapping)
    return {"mapping": mapping}


def validate_limit(step: dict, path: str, schema: Schema) -> dict[str, Any]:
    field_path = f"{path}.n"
    if "n" not in step:
        raise schema_error("missing required field 'n'", field_path)
    n = step["n"]
    if not is_integer(n):
        raise schema_error("field 'n' must be an integer", field_path)
    if n < 0:
        raise schema_error("field 'n' must be >= 0", field_path)
    return {"n": n}


OTHERWISE = "otherwise"
CONCAT = "concat"
MERGE_STRATEGIES = {CONCAT}


def is_otherwise(when: str) -> bool:
    return when.strip().lower() == OTHERWISE


def validate_merge(step: dict, path: str) -> dict[str, Any]:
    """Validate the optional ``merge`` object; returns the normalized form."""
    if "merge" not in step:
        return {"strategy": CONCAT}
    merge = step["merge"]
    merge_path = f"{path}.merge"
    if not isinstance(merge, dict):
        raise schema_error("field 'merge' must be an object", merge_path)
    if "strategy" not in merge:
        return {"strategy": CONCAT}
    strategy = merge["strategy"]
    strategy_path = f"{merge_path}.strategy"
    if not isinstance(strategy, str):
        raise schema_error("field 'strategy' must be a string", strategy_path)
    strategy = strategy.strip().lower()
    if strategy not in MERGE_STRATEGIES:
        raise schema_error(
            f"unsupported merge strategy '{strategy}' (expected 'concat')",
            strategy_path,
        )
    return {"strategy": strategy}


def validate_branch_shape(branch: Any, path: str) -> None:
    """Check the structure of one branch object (no expressions yet)."""
    if not isinstance(branch, dict):
        raise schema_error("branch must be an object", path)
    if "id" in branch and not isinstance(branch["id"], str):
        raise schema_error("field 'id' must be a string", f"{path}.id")
    require_trimmed_string(branch, "when", path)
    if "steps" not in branch:
        raise schema_error("missing required field 'steps'", f"{path}.steps")
    if not isinstance(branch["steps"], list):
        raise schema_error("field 'steps' must be an array", f"{path}.steps")


def validate_branch(step: dict, path: str, schema: Schema) -> dict[str, Any]:
    """Validate a branch step.

    Every ``when`` is checked against the schema as it stands *before* the
    branch step (routing happens before any sub-pipeline runs). Each branch's
    sub-pipeline is validated against its own copy of that schema, and the
    schema after the branch step is the union of all branch results, since a
    merged row may come from any branch.
    """
    branches_path = f"{path}.branches"
    if "branches" not in step:
        raise schema_error("missing required field 'branches'", branches_path)
    branches = step["branches"]
    if not isinstance(branches, list):
        raise schema_error("field 'branches' must be an array", branches_path)
    if not branches:
        raise schema_error("field 'branches' must not be empty", branches_path)
    for j, branch in enumerate(branches):
        validate_branch_shape(branch, f"{branches_path}[{j}]")

    otherwise_indices = [j for j, b in enumerate(branches) if is_otherwise(b["when"])]
    if len(otherwise_indices) > 1:
        raise EtlError(
            MALFORMED_STEP, "at most one 'otherwise' branch is allowed", branches_path
        )
    if otherwise_indices and otherwise_indices[0] != len(branches) - 1:
        raise EtlError(
            MALFORMED_STEP, "the 'otherwise' branch must be last", branches_path
        )

    merge = validate_merge(step, path)

    normalized_branches: list[dict[str, Any]] = []
    outputs: list[Schema] = []
    for j, branch in enumerate(branches):
        branch_path = f"{branches_path}[{j}]"
        if is_otherwise(branch["when"]):
            when = OTHERWISE
        else:
            when = require_expression(branch, "when", branch_path, schema)
        branch_schema = schema.copy()
        steps = [
            normalize_step(sub, k, branch_schema, f"{branch_path}.steps")
            for k, sub in enumerate(branch["steps"])
        ]
        outputs.append(branch_schema)
        normalized: dict[str, Any] = {}
        if "id" in branch:
            normalized["id"] = branch["id"]
        normalized["when"] = when
        normalized["steps"] = steps
        normalized_branches.append(normalized)
    schema.merge(outputs)
    return {"branches": normalized_branches, "merge": merge}


# ---------------------------------------------------------------------------
# Step executors
# ---------------------------------------------------------------------------
#
# Each executor receives the normalized step, the raw step as submitted (so
# error paths can point at the field the caller actually wrote, e.g. ``.from``
# vs ``.mapping.<key>``), the step path, and the current rows. It returns the
# new rows and must not mutate the rows it was given.

Rows = list[dict[str, Any]]


def missing_column(column: str, path: str) -> EtlError:
    return EtlError(MISSING_COLUMN, f"column '{column}' not found in row", path)


def compile_expression(text: str, path: str) -> tuple:
    """Parse an already-validated expression; any failure is reported as BAD_EXPR."""
    try:
        return parse_expression(text)
    except ExprSyntaxError as exc:
        raise EtlError(BAD_EXPR, str(exc), path)


def evaluate_or_fail(ast: tuple, row: dict[str, Any], path: str) -> Any:
    try:
        return evaluate(ast, row)
    except ExprEvalError as exc:
        raise EtlError(EXECUTION_FAILED, str(exc), path)


def execute_select(step: dict, raw: dict, path: str, rows: Rows) -> Rows:
    columns = step["columns"]
    out: Rows = []
    for row in rows:
        projected: dict[str, Any] = {}
        for i, column in enumerate(columns):
            if column not in row:
                raise missing_column(column, f"{path}.columns[{i}]")
            projected[column] = row[column]
        out.append(projected)
    return out


def execute_filter(step: dict, raw: dict, path: str, rows: Rows) -> Rows:
    field_path = f"{path}.where"
    ast = compile_expression(step["where"], field_path)
    return [row for row in rows if truthy(evaluate_or_fail(ast, row, field_path))]


def execute_map(step: dict, raw: dict, path: str, rows: Rows) -> Rows:
    field_path = f"{path}.expr"
    ast = compile_expression(step["expr"], field_path)
    alias = step["as"]
    out: Rows = []
    for row in rows:
        updated = dict(row)
        updated[alias] = evaluate_or_fail(ast, row, field_path)
        out.append(updated)
    return out


def rename_column(row: dict[str, Any], old: str, new: str) -> dict[str, Any]:
    """Return a copy of ``row`` with ``old`` renamed to ``new``.

    The renamed column keeps its position. If ``new`` already exists its
    value is replaced by the renamed one.
    """
    out: dict[str, Any] = {}
    for key, value in row.items():
        if key == old:
            out[new] = value
        elif key == new and new in out:
            continue  # already filled by the renamed column
        else:
            out[key] = value
    return out


def execute_rename(step: dict, raw: dict, path: str, rows: Rows) -> Rows:
    mapping = step["mapping"]
    uses_pair = "from" in raw
    out: Rows = []
    for row in rows:
        current = row
        for old, new in mapping.items():
            if old not in current:
                source_path = f"{path}.from" if uses_pair else f"{path}.mapping.{old}"
                raise missing_column(old, source_path)
            current = rename_column(current, old, new)
        out.append(current)
    return out


def execute_limit(step: dict, raw: dict, path: str, rows: Rows) -> Rows:
    return rows[: step["n"]]


def execute_branch(step: dict, raw: dict, path: str, rows: Rows) -> Rows:
    """Route each row to the first branch whose ``when`` is truthy, run each
    branch's sub-pipeline over its rows, and concatenate the results in branch
    order. Rows matching no branch are dropped."""
    branches = step["branches"]
    branches_path = f"{path}.branches"
    conditions: list[tuple | None] = []
    for j, branch in enumerate(branches):
        if branch["when"] == OTHERWISE:
            conditions.append(None)
        else:
            conditions.append(compile_expression(branch["when"], f"{branches_path}[{j}].when"))

    routed: list[Rows] = [[] for _ in branches]
    for row in rows:
        for j, ast in enumerate(conditions):
            if ast is None or truthy(evaluate_or_fail(ast, row, f"{branches_path}[{j}].when")):
                routed[j].append(row)
                break

    out: Rows = []
    for j, (branch, raw_branch) in enumerate(zip(branches, raw["branches"])):
        out.extend(
            execute_steps(
                branch["steps"], raw_branch["steps"], routed[j], f"{branches_path}[{j}].steps"
            )
        )
    return out


# ---------------------------------------------------------------------------
# Op registry
# ---------------------------------------------------------------------------

StepValidator = Callable[[dict, str, Schema], dict[str, Any]]
StepExecutor = Callable[[dict, dict, str, Rows], Rows]


class Op(NamedTuple):
    validate: StepValidator
    execute: StepExecutor


OPS: dict[str, Op] = {
    "select": Op(validate_select, execute_select),
    "filter": Op(validate_filter, execute_filter),
    "map": Op(validate_map, execute_map),
    "rename": Op(validate_rename, execute_rename),
    "limit": Op(validate_limit, execute_limit),
    "branch": Op(validate_branch, execute_branch),
}

TOP_LEVEL_STEPS = "pipeline.steps"


def step_path(index: int, prefix: str = TOP_LEVEL_STEPS) -> str:
    return f"{prefix}[{index}]"


def normalize_step(
    step: Any, index: int, schema: Schema, prefix: str = TOP_LEVEL_STEPS
) -> dict[str, Any]:
    """Validate one step and return its normalized form.

    ``prefix`` is the path of the containing steps array; nested steps (inside
    a branch) use ``pipeline.steps[i].branches[j].steps``.
    """
    path = step_path(index, prefix)
    if not isinstance(step, dict):
        raise schema_error("step must be an object", path)
    if "op" not in step:
        raise schema_error("missing required field 'op'", f"{path}.op")
    raw_op = step["op"]
    if not isinstance(raw_op, str):
        raise schema_error("field 'op' must be a string", f"{path}.op")
    op = raw_op.strip().lower()
    if not op:
        raise schema_error("field 'op' must not be empty", f"{path}.op")
    if op not in OPS:
        raise EtlError(UNKNOWN_OP, f"unsupported op '{op}'", f"{path}.op")
    fields = OPS[op].validate(step, path, schema)
    normalized: dict[str, Any] = {"op": op}
    for key in sorted(fields):
        normalized[key] = fields[key]
    return normalized


def execute_steps(
    normalized: list[dict], raw_steps: list[dict], dataset: Rows, prefix: str = TOP_LEVEL_STEPS
) -> Rows:
    """Run normalized steps in order over the dataset; returns the result rows.

    ``prefix`` is the path of the steps array, used for error paths. Branch
    sub-pipelines call this recursively with their own prefix.
    """
    rows: Rows = list(dataset)
    for index, (step, raw) in enumerate(zip(normalized, raw_steps)):
        path = step_path(index, prefix)
        try:
            rows = OPS[step["op"]].execute(step, raw, path, rows)
        except EtlError:
            raise
        except Exception as exc:  # defensive: never leak a traceback
            raise EtlError(EXECUTION_FAILED, f"{step['op']} failed: {exc}", path)
    return rows


# ---------------------------------------------------------------------------
# Request handling
# ---------------------------------------------------------------------------


def validate_dataset(request: dict) -> Rows:
    if "dataset" not in request:
        raise schema_error("missing required field 'dataset'", "dataset")
    dataset = request["dataset"]
    if not isinstance(dataset, list):
        raise schema_error("field 'dataset' must be an array", "dataset")
    for i, row in enumerate(dataset):
        if not isinstance(row, dict):
            raise schema_error(f"dataset row {i} must be an object", f"dataset[{i}]")
    return dataset


def validate_steps(request: dict) -> list:
    if "pipeline" not in request:
        raise schema_error("missing required field 'pipeline'", "pipeline")
    pipeline = request["pipeline"]
    if not isinstance(pipeline, dict):
        raise schema_error("field 'pipeline' must be an object", "pipeline")
    if "steps" not in pipeline:
        raise schema_error("missing required field 'steps'", "pipeline.steps")
    steps = pipeline["steps"]
    if not isinstance(steps, list):
        raise schema_error("field 'steps' must be an array", "pipeline.steps")
    return steps


def process_request(request: Any, execute: bool = False) -> dict[str, Any]:
    """Validate a parsed request and return the success response body.

    ``execute=False`` returns ``{"status": "ok", "normalized": {...}}``.
    ``execute=True`` runs the pipeline and returns ``data`` and ``metrics``.
    """
    if not isinstance(request, dict):
        raise schema_error("request body must be a JSON object", "")
    steps = validate_steps(request)
    dataset = validate_dataset(request)
    schema = Schema.disabled() if execute else Schema(dataset)
    normalized = [normalize_step(step, i, schema) for i, step in enumerate(steps)]
    if not execute:
        return {"status": "ok", "normalized": {"steps": normalized}}
    data = execute_steps(normalized, steps, dataset)
    return {
        "status": "ok",
        "data": data,
        "metrics": {"rows_in": len(dataset), "rows_out": len(data)},
    }


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

TRUE_WORDS = {"true", "1", "yes", "y", "on"}
FALSE_WORDS = {"false", "0", "no", "n", "off"}


def parse_bool(text: str, flag: str) -> bool:
    word = text.strip().lower()
    if word in TRUE_WORDS:
        return True
    if word in FALSE_WORDS:
        return False
    raise schema_error(f"invalid boolean value '{text}' for {flag}", "")


class CliArgumentParser(argparse.ArgumentParser):
    """argparse that reports usage errors as EtlError instead of exiting."""

    def error(self, message: str) -> None:  # type: ignore[override]
        raise schema_error(f"invalid arguments: {message}", "")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = CliArgumentParser(
        prog="etl_pipeline.py",
        description="Validate (and optionally execute) an ETL pipeline read as JSON on stdin.",
    )
    parser.add_argument(
        "--execute",
        nargs="?",
        const="true",
        default="false",
        metavar="BOOL",
        help="run the pipeline over the dataset and return data + metrics "
        "(bare flag means true; default: false)",
    )
    args = parser.parse_args(argv)
    args.execute = parse_bool(args.execute, "--execute")
    return args


def run(stdin_text: str, execute: bool = False) -> tuple[dict[str, Any], int]:
    """Return (response, exit_code) for the given request text."""
    try:
        try:
            request = json.loads(stdin_text)
        except ValueError as exc:
            raise schema_error(f"invalid JSON input: {exc}", "")
        return process_request(request, execute=execute), 0
    except EtlError as err:
        return err.to_response(), 1


def emit(response: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(response, ensure_ascii=False))
    sys.stdout.write("\n")
    sys.stdout.flush()


def main(argv: list[str] | None = None) -> int:
    try:
        args = parse_args(sys.argv[1:] if argv is None else argv)
    except EtlError as err:
        emit(err.to_response())
        return 1
    response, code = run(sys.stdin.read(), execute=args.execute)
    emit(response)
    return code


if __name__ == "__main__":
    sys.exit(main())
