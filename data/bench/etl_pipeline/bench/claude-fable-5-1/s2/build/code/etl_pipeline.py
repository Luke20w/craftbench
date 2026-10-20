#!/usr/bin/env python3
"""ETL pipeline CLI.

Reads a JSON request on STDIN, validates and normalizes the pipeline
specification and - with ``--execute`` - runs it over the request's dataset.
Writes a JSON response to STDOUT.

    $ python3 etl_pipeline.py < request.json            # normalize only
    $ python3 etl_pipeline.py --execute < request.json  # run the pipeline

Exit code 0 on success, 1 on any error. Every error is reported as a JSON
object on STDOUT of the form::

    {"status": "error", "error_code": "...", "message": "ETL_ERROR: ...",
     "path": "pipeline.steps[0].columns[2]"}

Module layout (top to bottom):

* ``EtlError``          - the single exception type used for all failures.
* ``expressions``       - tokenizer + recursive-descent parser that turns a
                          ``where``/``expr`` string into an AST, plus
                          ``evaluate`` which runs an AST against a row.
* ``validation``        - request/step validation and normalization. Each op
                          has its own ``_normalize_<op>`` function registered
                          in ``OP_NORMALIZERS``; add new ops there.
* ``execution``         - one ``_exec_<op>`` function per op registered in
                          ``OP_EXECUTORS``; ``execute_pipeline`` drives them.
* ``main``              - argument parsing and I/O glue.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Callable

# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------

SCHEMA_VALIDATION_FAILED = "SCHEMA_VALIDATION_FAILED"
UNKNOWN_OP = "UNKNOWN_OP"
MISSING_COLUMN = "MISSING_COLUMN"
BAD_EXPR = "BAD_EXPR"
EXECUTION_FAILED = "EXECUTION_FAILED"


class EtlError(Exception):
    """A user-facing error with a code, a message and a JSON path."""

    def __init__(self, code: str, message: str, path: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.path = path

    def to_response(self) -> dict[str, Any]:
        return {
            "status": "error",
            "error_code": self.code,
            "message": f"ETL_ERROR: {self.message}",
            "path": self.path,
        }


# ---------------------------------------------------------------------------
# Expressions: tokenizer
# ---------------------------------------------------------------------------

# Token kinds
T_NUMBER = "number"
T_STRING = "string"
T_IDENT = "ident"
T_OP = "op"
T_LPAREN = "("
T_RPAREN = ")"
T_EOF = "eof"

# Every character that may start/continue a punctuation operator. A maximal
# run of these characters is matched against ``_OPERATORS``; anything else
# is reported as an unsupported operator (``**``, ``^^``, ``=``, ...).
_OPERATOR_CHARS = set("*/+-<>=!&|^%~?:")
# Longest operators first so that ">=" wins over ">".
_OPERATORS = (">=", "<=", "==", "!=", "&&", "||", "+", "-", "*", "/", ">", "<", "!")
# Operators that may legally start a unary sub-expression, so a run such as
# ">-" is split into ">" followed by "-".
_UNARY_PREFIX_OPS = ("-", "+", "!")
_KEYWORDS = {"and", "or", "not", "true", "false", "null"}
_COMPARISON_OPS = {">", ">=", "<", "<=", "==", "!="}


class Token:
    __slots__ = ("kind", "value", "pos")

    def __init__(self, kind: str, value: Any, pos: int) -> None:
        self.kind = kind
        self.value = value
        self.pos = pos

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"Token({self.kind!r}, {self.value!r}, {self.pos})"


class ExpressionSyntaxError(ValueError):
    """Raised by the tokenizer/parser; converted to BAD_EXPR by the caller."""


def _match_operator(run: str) -> str | None:
    """Return the operator token to emit for the start of ``run``.

    ``run`` is a maximal sequence of operator characters. It is accepted when
    it is a known operator, or when a known operator is followed by something
    that can start a unary expression (``a>-1`` tokenizes as ``>`` ``-``).
    Returns ``None`` for unsupported combinations such as ``**`` or ``^^``.
    """
    for op in _OPERATORS:
        if run == op:
            return op
        if run.startswith(op) and run[len(op):].startswith(_UNARY_PREFIX_OPS):
            return op
    return None


def tokenize(text: str) -> list[Token]:
    tokens: list[Token] = []
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        if ch.isspace():
            i += 1
            continue

        # Numbers: 12, 3.5, .5 ; a trailing exponent is accepted too.
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
            if i < n and (text[i].isalnum() or text[i] == "_" or text[i] == "."):
                raise ExpressionSyntaxError(f"malformed number at position {start}")
            literal = text[start:i]
            value: Any = float(literal) if any(c in literal for c in ".eE") else int(literal)
            tokens.append(Token(T_NUMBER, value, start))
            continue

        # Identifiers and keywords.
        if ch.isalpha() or ch == "_":
            start = i
            while i < n and (text[i].isalnum() or text[i] == "_"):
                i += 1
            word = text[start:i]
            lowered = word.lower()
            if lowered in _KEYWORDS:
                tokens.append(Token(T_OP, lowered, start))
            else:
                tokens.append(Token(T_IDENT, word, start))
            continue

        # String literals in single or double quotes with backslash escapes.
        if ch in ("'", '"'):
            quote = ch
            start = i
            i += 1
            buf: list[str] = []
            closed = False
            while i < n:
                c = text[i]
                if c == "\\":
                    if i + 1 >= n:
                        break
                    buf.append(text[i + 1])
                    i += 2
                    continue
                if c == quote:
                    closed = True
                    i += 1
                    break
                buf.append(c)
                i += 1
            if not closed:
                raise ExpressionSyntaxError(f"unterminated string at position {start}")
            tokens.append(Token(T_STRING, "".join(buf), start))
            continue

        if ch == "(":
            tokens.append(Token(T_LPAREN, ch, i))
            i += 1
            continue
        if ch == ")":
            tokens.append(Token(T_RPAREN, ch, i))
            i += 1
            continue

        if ch in _OPERATOR_CHARS:
            start = i
            while i < n and text[i] in _OPERATOR_CHARS:
                i += 1
            run = text[start:i]
            op = _match_operator(run)
            if op is None:
                raise ExpressionSyntaxError(f"unsupported operator '{run}'")
            tokens.append(Token(T_OP, op, start))
            i = start + len(op)
            continue

        raise ExpressionSyntaxError(f"unexpected character {ch!r} at position {i}")

    tokens.append(Token(T_EOF, None, n))
    return tokens


# ---------------------------------------------------------------------------
# Expressions: parser
# ---------------------------------------------------------------------------


class Parser:
    """Recursive-descent parser.

    Grammar (lowest to highest precedence)::

        or_expr    := and_expr (("or" | "||") and_expr)*
        and_expr   := not_expr (("and" | "&&") not_expr)*
        not_expr   := "not" not_expr | comparison
        comparison := additive (CMP_OP additive)*
        additive   := term (("+" | "-") term)*
        term       := unary (("*" | "/") unary)*
        unary      := ("-" | "+" | "!") unary | primary
        primary    := NUMBER | STRING | IDENT | true | false | null
                    | "(" or_expr ")"

    ``not`` is a low-precedence keyword (Python style) while ``!`` is a
    high-precedence unary operator (C style); both produce a ``not`` node.

    AST nodes are tuples:
        ("num", value) ("str", value) ("col", name) ("bool", value) ("null",)
        ("neg", node) ("not", node) ("bin", op, left, right)
    where the binary ``op`` is one of
        "or" "and" "==" "!=" "<" "<=" ">" ">=" "+" "-" "*" "/"
    """

    def __init__(self, tokens: list[Token]) -> None:
        self.tokens = tokens
        self.i = 0

    # -- helpers -----------------------------------------------------------
    @property
    def cur(self) -> Token:
        return self.tokens[self.i]

    def _advance(self) -> Token:
        tok = self.tokens[self.i]
        self.i += 1
        return tok

    def _is_op(self, *values: str) -> bool:
        return self.cur.kind == T_OP and self.cur.value in values

    def _fail(self, what: str) -> ExpressionSyntaxError:
        tok = self.cur
        if tok.kind == T_EOF:
            return ExpressionSyntaxError(f"unexpected end of expression, expected {what}")
        return ExpressionSyntaxError(
            f"unexpected {tok.kind} {tok.value!r} at position {tok.pos}, expected {what}"
        )

    # -- grammar -----------------------------------------------------------
    def parse(self) -> tuple:
        node = self.parse_or()
        if self.cur.kind != T_EOF:
            raise self._fail("end of expression")
        return node

    def parse_or(self) -> tuple:
        node = self.parse_and()
        while self._is_op("or", "||"):
            self._advance()
            node = ("bin", "or", node, self.parse_and())
        return node

    def parse_and(self) -> tuple:
        node = self.parse_not()
        while self._is_op("and", "&&"):
            self._advance()
            node = ("bin", "and", node, self.parse_not())
        return node

    def parse_not(self) -> tuple:
        if self._is_op("not"):
            self._advance()
            return ("not", self.parse_not())
        return self.parse_comparison()

    def parse_comparison(self) -> tuple:
        node = self.parse_additive()
        while self.cur.kind == T_OP and self.cur.value in _COMPARISON_OPS:
            op = self._advance().value
            node = ("bin", op, node, self.parse_additive())
        return node

    def parse_additive(self) -> tuple:
        node = self.parse_term()
        while self._is_op("+", "-"):
            op = self._advance().value
            node = ("bin", op, node, self.parse_term())
        return node

    def parse_term(self) -> tuple:
        node = self.parse_unary()
        while self._is_op("*", "/"):
            op = self._advance().value
            node = ("bin", op, node, self.parse_unary())
        return node

    def parse_unary(self) -> tuple:
        if self._is_op("-"):
            self._advance()
            return ("neg", self.parse_unary())
        if self._is_op("+"):
            self._advance()
            return self.parse_unary()
        if self._is_op("!"):
            self._advance()
            return ("not", self.parse_unary())
        return self.parse_primary()

    def parse_primary(self) -> tuple:
        tok = self.cur
        if tok.kind == T_NUMBER:
            self._advance()
            return ("num", tok.value)
        if tok.kind == T_STRING:
            self._advance()
            return ("str", tok.value)
        if tok.kind == T_IDENT:
            self._advance()
            return ("col", tok.value)
        if tok.kind == T_OP and tok.value in ("true", "false"):
            self._advance()
            return ("bool", tok.value == "true")
        if tok.kind == T_OP and tok.value == "null":
            self._advance()
            return ("null",)
        if tok.kind == T_LPAREN:
            self._advance()
            node = self.parse_or()
            if self.cur.kind != T_RPAREN:
                raise self._fail("')'")
            self._advance()
            return node
        raise self._fail("a value")


def parse_expression(text: str) -> tuple:
    """Parse ``text`` into an AST, raising ``ExpressionSyntaxError`` on failure."""
    return Parser(tokenize(text)).parse()


def expression_columns(node: tuple) -> list[str]:
    """Return column names referenced by an AST, in first-seen order."""
    found: list[str] = []

    def walk(n: tuple) -> None:
        kind = n[0]
        if kind == "col":
            if n[1] not in found:
                found.append(n[1])
        elif kind in ("neg", "not"):
            walk(n[1])
        elif kind == "bin":
            walk(n[2])
            walk(n[3])

    walk(node)
    return found


# ---------------------------------------------------------------------------
# Expressions: evaluation
# ---------------------------------------------------------------------------


class ExpressionRuntimeError(ValueError):
    """Raised by ``evaluate``; converted to EXECUTION_FAILED by the caller."""


def _is_number(value: Any) -> bool:
    # ``bool`` is a subclass of ``int`` in Python but a distinct JSON type.
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _type_name(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if _is_number(value):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    return type(value).__name__


def _same_type(a: Any, b: Any) -> bool:
    return _type_name(a) == _type_name(b)


def _normalize_number(value: float | int) -> float | int:
    """Collapse integral floats (``100.0``) to ints so JSON output is ``100``."""
    if isinstance(value, float) and value.is_integer() and abs(value) < 2**53:
        return int(value)
    return value


def truthy(value: Any) -> bool:
    """Truthiness used by ``and``/``or``/``not`` and ``filter``.

    ``null``, ``false``, ``0``, ``""`` and empty containers are falsy.
    """
    if value is None:
        return False
    return bool(value)


def _arith(op: str, left: Any, right: Any) -> Any:
    if left is None or right is None:
        return None
    if _is_number(left) and _is_number(right):
        if op == "+":
            return _normalize_number(left + right)
        if op == "-":
            return _normalize_number(left - right)
        if op == "*":
            return _normalize_number(left * right)
        if right == 0:
            return None
        return _normalize_number(left / right)
    if op == "+" and isinstance(left, str) and isinstance(right, str):
        return left + right
    raise ExpressionRuntimeError(
        f"cannot apply '{op}' to {_type_name(left)} and {_type_name(right)}"
    )


def _compare(op: str, left: Any, right: Any) -> bool:
    if left is None or right is None:
        return False
    if not _same_type(left, right):
        return False
    if op == "==":
        return left == right
    if op == "!=":
        return left != right
    # Ordering is only defined for numbers and strings.
    if not (_is_number(left) or isinstance(left, str)):
        return False
    if op == "<":
        return left < right
    if op == "<=":
        return left <= right
    if op == ">":
        return left > right
    return left >= right


def evaluate(node: tuple, row: dict) -> Any:
    """Evaluate an AST against ``row``. Unknown identifiers resolve to null."""
    kind = node[0]
    if kind in ("num", "str", "bool"):
        return node[1]
    if kind == "null":
        return None
    if kind == "col":
        return row.get(node[1])
    if kind == "neg":
        value = evaluate(node[1], row)
        if value is None:
            return None
        if not _is_number(value):
            raise ExpressionRuntimeError(f"cannot negate {_type_name(value)}")
        return _normalize_number(-value)
    if kind == "not":
        return not truthy(evaluate(node[1], row))

    op = node[1]
    if op == "and":
        return truthy(evaluate(node[2], row)) and truthy(evaluate(node[3], row))
    if op == "or":
        return truthy(evaluate(node[2], row)) or truthy(evaluate(node[3], row))
    left = evaluate(node[2], row)
    right = evaluate(node[3], row)
    if op in _COMPARISON_OPS:
        return _compare(op, left, right)
    return _arith(op, left, right)


# ---------------------------------------------------------------------------
# Validation and normalization
# ---------------------------------------------------------------------------

STEPS_PATH = "pipeline.steps"
MALFORMED_STEP = "MALFORMED_STEP"
OTHERWISE = "otherwise"
CONCAT = "concat"


def _sub(path: str, *fields: str) -> str:
    """Append ``.field`` segments to a JSON path (``_sub("a", "b", "c[1]")``)."""
    for field in fields:
        path += f".{field}"
    return path


def _item(path: str, index: int) -> str:
    """``path[index]``."""
    return f"{path}[{index}]"


def _schema_error(message: str, path: str) -> EtlError:
    return EtlError(SCHEMA_VALIDATION_FAILED, message, path)


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _require_trimmed_string(step: dict, field: str, path: str) -> str:
    """Fetch ``field`` from ``step``, trim it and reject missing/empty values."""
    if field not in step:
        raise _schema_error(f"missing required field '{field}'", path)
    value = step[field]
    if not isinstance(value, str):
        raise _schema_error(f"field '{field}' must be a string", path)
    trimmed = value.strip()
    if not trimmed:
        raise _schema_error(f"field '{field}' must not be empty", path)
    return trimmed


def _parse_expression_text(text: str, path: str) -> tuple:
    try:
        return parse_expression(text)
    except ExpressionSyntaxError as exc:
        raise EtlError(BAD_EXPR, str(exc), path) from None


def _parse_expression_field(step: dict, field: str, path: str) -> tuple[str, tuple]:
    text = _require_trimmed_string(step, field, path)
    return text, _parse_expression_text(text, path)


class ColumnTracker:
    """Tracks the set of columns available to each step (normalize-only mode).

    Columns are only tracked when the dataset is non-empty; with an empty
    dataset there is nothing to check against, so every reference is allowed.
    When executing, the tracker is disabled: the executor reports missing
    columns itself with row-level accuracy and element-level paths, and
    unknown identifiers inside expressions evaluate to null.

    Branches ``fork()`` the tracker (one copy per branch) and ``merge()`` the
    results back: after a branch step a column counts as available when any
    branch produces it, so later steps are not rejected for columns that only
    some rows carry (execution reports those per row).
    """

    def __init__(self, dataset: list[dict], enabled: bool = True) -> None:
        self.enabled = enabled and bool(dataset)
        self.columns: set[str] = set()
        for row in dataset:
            self.columns.update(row.keys())

    def fork(self) -> "ColumnTracker":
        copy = ColumnTracker([], enabled=False)
        copy.enabled = self.enabled
        copy.columns = set(self.columns)
        return copy

    def merge(self, forks: list["ColumnTracker"]) -> None:
        if self.enabled:
            self.columns = set().union(*(f.columns for f in forks))

    def require(self, names: list[str], path: str) -> None:
        if not self.enabled:
            return
        for name in names:
            if name not in self.columns:
                raise EtlError(MISSING_COLUMN, f"unknown column '{name}'", path)

    def select(self, names: list[str]) -> None:
        if self.enabled:
            self.columns = set(names)

    def add(self, name: str) -> None:
        if self.enabled:
            self.columns.add(name)

    def rename(self, mapping: dict[str, str]) -> None:
        if self.enabled:
            self.columns = {mapping.get(c, c) for c in self.columns}


# A normalizer receives the raw step, the JSON path of the step
# (``pipeline.steps[0]`` or, inside a branch,
# ``pipeline.steps[0].branches[1].steps[2]``) and the column tracker, and
# returns the normalized step.
Normalizer = Callable[[dict, str, ColumnTracker], dict]


def _normalize_select(step: dict, step_path: str, tracker: ColumnTracker) -> dict:
    path = _sub(step_path, "columns")
    if "columns" not in step:
        raise _schema_error("missing required field 'columns'", path)
    columns = step["columns"]
    if not isinstance(columns, list):
        raise _schema_error("field 'columns' must be an array of strings", path)
    if not columns:
        raise _schema_error("field 'columns' must not be empty", path)
    for col in columns:
        if not isinstance(col, str):
            raise _schema_error("field 'columns' must contain only strings", path)
        if col == "":
            raise _schema_error("column names must not be empty", path)
    tracker.require(columns, path)
    tracker.select(columns)
    return {"op": "select", "columns": list(columns)}


def _normalize_filter(step: dict, step_path: str, tracker: ColumnTracker) -> dict:
    path = _sub(step_path, "where")
    where, ast = _parse_expression_field(step, "where", path)
    tracker.require(expression_columns(ast), path)
    return {"op": "filter", "where": where}


def _normalize_map(step: dict, step_path: str, tracker: ColumnTracker) -> dict:
    as_name = _require_trimmed_string(step, "as", _sub(step_path, "as"))
    expr_path = _sub(step_path, "expr")
    expr, ast = _parse_expression_field(step, "expr", expr_path)
    tracker.require(expression_columns(ast), expr_path)
    tracker.add(as_name)
    return {"op": "map", "as": as_name, "expr": expr}


def _rename_uses_mapping(step: dict) -> bool:
    """``mapping`` wins over ``from``/``to`` when both are present."""
    return "mapping" in step


def _normalize_rename(step: dict, step_path: str, tracker: ColumnTracker) -> dict:
    if _rename_uses_mapping(step):
        path = _sub(step_path, "mapping")
        mapping = step["mapping"]
        if not isinstance(mapping, dict):
            raise _schema_error("field 'mapping' must be an object", path)
        if not mapping:
            raise _schema_error("field 'mapping' must not be empty", path)
        for key, value in mapping.items():
            if not isinstance(value, str):
                raise _schema_error("field 'mapping' values must be strings", path)
            if key == "" or value == "":
                raise _schema_error("field 'mapping' keys and values must not be empty", path)
        normalized = dict(mapping)
        tracker.require(list(normalized), path)
    else:
        from_path = _sub(step_path, "from")
        if "from" not in step and "to" not in step:
            raise _schema_error(
                "rename requires either 'mapping' or both 'from' and 'to'",
                step_path,
            )
        src = _require_trimmed_string(step, "from", from_path)
        dst = _require_trimmed_string(step, "to", _sub(step_path, "to"))
        normalized = {src: dst}
        tracker.require([src], from_path)
    tracker.rename(normalized)
    return {"op": "rename", "mapping": normalized}


def _normalize_limit(step: dict, step_path: str, tracker: ColumnTracker) -> dict:
    path = _sub(step_path, "n")
    if "n" not in step:
        raise _schema_error("missing required field 'n'", path)
    n = step["n"]
    if not _is_int(n):
        raise _schema_error("field 'n' must be an integer", path)
    if n < 0:
        raise _schema_error("field 'n' must be >= 0", path)
    return {"op": "limit", "n": n}


def _is_otherwise(when: str) -> bool:
    return when.strip().lower() == OTHERWISE


def _validate_branch_shape(branch: Any, path: str) -> dict:
    """Type-check one branch (``id``/``when``/``steps``) without recursing.

    Returns the branch header: ``{"id": ..., "when": ...}`` (``id`` only when
    given) with ``when`` trimmed and ``"otherwise"`` lower-cased.
    """
    if not isinstance(branch, dict):
        raise _schema_error("branch must be an object", path)
    header: dict = {}
    if "id" in branch:
        if not isinstance(branch["id"], str):
            raise _schema_error("field 'id' must be a string", _sub(path, "id"))
        header["id"] = branch["id"]
    when_path = _sub(path, "when")
    when = _require_trimmed_string(branch, "when", when_path)
    if _is_otherwise(when):
        when = OTHERWISE
    else:
        _parse_expression_text(when, when_path)
    header["when"] = when
    steps_path = _sub(path, "steps")
    if "steps" not in branch:
        raise _schema_error("missing required field 'steps'", steps_path)
    if not isinstance(branch["steps"], list):
        raise _schema_error("field 'steps' must be an array", steps_path)
    return header


def _normalize_merge(step: dict, step_path: str) -> dict:
    path = _sub(step_path, "merge")
    merge = step.get("merge", {})
    if not isinstance(merge, dict):
        raise _schema_error("field 'merge' must be an object", path)
    strategy_path = _sub(path, "strategy")
    strategy = merge.get("strategy", CONCAT)
    if not isinstance(strategy, str):
        raise _schema_error("field 'strategy' must be a string", strategy_path)
    strategy = strategy.strip().lower()
    if strategy != CONCAT:
        raise _schema_error(
            f"unsupported merge strategy '{strategy}' (expected '{CONCAT}')", strategy_path
        )
    return {"strategy": CONCAT}


def _normalize_branch(step: dict, step_path: str, tracker: ColumnTracker) -> dict:
    branches_path = _sub(step_path, "branches")
    if "branches" not in step:
        raise _schema_error("missing required field 'branches'", branches_path)
    branches = step["branches"]
    if not isinstance(branches, list):
        raise _schema_error("field 'branches' must be an array", branches_path)
    if not branches:
        raise _schema_error("field 'branches' must not be empty", branches_path)

    # 1. Shape of every branch (types, parseable ``when``), in order.
    headers = [
        _validate_branch_shape(branch, _item(branches_path, j))
        for j, branch in enumerate(branches)
    ]
    merge = _normalize_merge(step, step_path)

    # 2. At most one "otherwise", and it must be the last branch.
    otherwise_positions = [j for j, h in enumerate(headers) if h["when"] == OTHERWISE]
    if len(otherwise_positions) > 1:
        raise EtlError(
            MALFORMED_STEP, "at most one 'otherwise' branch is allowed", branches_path
        )
    if otherwise_positions and otherwise_positions[0] != len(headers) - 1:
        raise EtlError(
            MALFORMED_STEP, "the 'otherwise' branch must be the last branch", branches_path
        )

    # 3. Nested steps. Each branch starts from the columns available before the
    #    branch step; afterwards the union of all branch outputs is available.
    normalized_branches: list[dict] = []
    forks: list[ColumnTracker] = []
    for j, (branch, header) in enumerate(zip(branches, headers)):
        branch_path = _item(branches_path, j)
        fork = tracker.fork()
        if header["when"] != OTHERWISE:
            ast = parse_expression(header["when"])
            fork.require(expression_columns(ast), _sub(branch_path, "when"))
        header["steps"] = normalize_steps(branch["steps"], _sub(branch_path, "steps"), fork)
        normalized_branches.append(header)
        forks.append(fork)
    tracker.merge(forks)
    return {"op": "branch", "branches": normalized_branches, "merge": merge}


OP_NORMALIZERS: dict[str, Normalizer] = {
    "select": _normalize_select,
    "filter": _normalize_filter,
    "map": _normalize_map,
    "rename": _normalize_rename,
    "limit": _normalize_limit,
    "branch": _normalize_branch,
}


def _order_keys(step: dict) -> dict:
    """``op`` first, then remaining keys alphabetically."""
    ordered = {"op": step["op"]}
    for key in sorted(k for k in step if k != "op"):
        ordered[key] = step[key]
    return ordered


def normalize_step(step: Any, step_path: str, tracker: ColumnTracker) -> dict:
    if not isinstance(step, dict):
        raise _schema_error("step must be an object", step_path)
    op_path = _sub(step_path, "op")
    if "op" not in step:
        raise _schema_error("missing required field 'op'", op_path)
    op = step["op"]
    if not isinstance(op, str):
        raise _schema_error("field 'op' must be a string", op_path)
    op = op.strip().lower()
    if not op:
        raise _schema_error("field 'op' must not be empty", op_path)
    normalizer = OP_NORMALIZERS.get(op)
    if normalizer is None:
        raise EtlError(UNKNOWN_OP, f"unsupported op '{op}'", op_path)
    return _order_keys(normalizer(step, step_path, tracker))


def normalize_steps(steps: list, steps_path: str, tracker: ColumnTracker) -> list[dict]:
    """Normalize a step list whose JSON path is ``steps_path`` (e.g. ``pipeline.steps``)."""
    return [normalize_step(step, _item(steps_path, i), tracker) for i, step in enumerate(steps)]


def validate_dataset(request: dict) -> list[dict]:
    if "dataset" not in request:
        raise _schema_error("missing required field 'dataset'", "dataset")
    dataset = request["dataset"]
    if not isinstance(dataset, list):
        raise _schema_error("field 'dataset' must be an array", "dataset")
    for i, row in enumerate(dataset):
        if not isinstance(row, dict):
            raise _schema_error("dataset rows must be objects", f"dataset[{i}]")
    return dataset


def validate_steps(request: dict) -> list:
    if "pipeline" not in request:
        raise _schema_error("missing required field 'pipeline'", "pipeline")
    pipeline = request["pipeline"]
    if not isinstance(pipeline, dict):
        raise _schema_error("field 'pipeline' must be an object", "pipeline")
    if "steps" not in pipeline:
        raise _schema_error("missing required field 'steps'", STEPS_PATH)
    steps = pipeline["steps"]
    if not isinstance(steps, list):
        raise _schema_error("field 'steps' must be an array", STEPS_PATH)
    return steps


# ---------------------------------------------------------------------------
# Execution
# ---------------------------------------------------------------------------

# An executor receives the normalized step, the raw step as submitted (needed
# to pick error paths such as ``.from`` vs ``.mapping.<key>``), the step's
# JSON path and the current rows; it returns the new list of rows. Rows are
# plain dicts and are never shared with the input dataset, so executors may
# mutate them.
Executor = Callable[[dict, dict, str, list[dict]], list[dict]]


def _missing_column(name: str, path: str) -> EtlError:
    return EtlError(MISSING_COLUMN, f"column '{name}' not found in row", path)


def _compile(text: str, path: str) -> tuple:
    try:
        return parse_expression(text)
    except ExpressionSyntaxError as exc:  # already rejected by normalization
        raise EtlError(BAD_EXPR, str(exc), path) from None


def _evaluate(ast: tuple, row: dict, path: str) -> Any:
    try:
        return evaluate(ast, row)
    except ExpressionRuntimeError as exc:
        raise EtlError(EXECUTION_FAILED, str(exc), path) from None


def _exec_select(step: dict, raw: dict, step_path: str, rows: list[dict]) -> list[dict]:
    columns = step["columns"]
    out: list[dict] = []
    for row in rows:
        new_row: dict = {}
        for col_index, name in enumerate(columns):
            if name not in row:
                raise _missing_column(name, _item(_sub(step_path, "columns"), col_index))
            new_row[name] = row[name]
        out.append(new_row)
    return out


def _exec_filter(step: dict, raw: dict, step_path: str, rows: list[dict]) -> list[dict]:
    path = _sub(step_path, "where")
    ast = _compile(step["where"], path)
    return [row for row in rows if truthy(_evaluate(ast, row, path))]


def _exec_map(step: dict, raw: dict, step_path: str, rows: list[dict]) -> list[dict]:
    path = _sub(step_path, "expr")
    ast = _compile(step["expr"], path)
    target = step["as"]
    for row in rows:
        row[target] = _evaluate(ast, row, path)
    return rows


def _rename_key(row: dict, src: str, dst: str) -> dict:
    """Return ``row`` with ``src`` renamed to ``dst``, keeping ``src``'s position.

    An existing ``dst`` column is overwritten (and its old slot dropped).
    """
    value = row[src]
    new_row: dict = {}
    for key, val in row.items():
        if key == src:
            new_row[dst] = value
        elif key != dst:
            new_row[key] = val
    return new_row


def _exec_rename(step: dict, raw: dict, step_path: str, rows: list[dict]) -> list[dict]:
    mapping = step["mapping"]
    uses_mapping = _rename_uses_mapping(raw)
    out: list[dict] = []
    for row in rows:
        for src, dst in mapping.items():
            if src not in row:
                field = f"mapping.{src}" if uses_mapping else "from"
                raise _missing_column(src, _sub(step_path, field))
            if src != dst:
                row = _rename_key(row, src, dst)
        out.append(row)
    return out


def _exec_limit(step: dict, raw: dict, step_path: str, rows: list[dict]) -> list[dict]:
    return rows[: step["n"]]


def _exec_branch(step: dict, raw: dict, step_path: str, rows: list[dict]) -> list[dict]:
    """Route each row to the first branch whose ``when`` holds, run each
    branch's steps over its rows, then concatenate in branch order.

    Rows matching no branch are dropped. ``when`` is evaluated with the
    same rules as ``filter`` (truthiness); an ``otherwise`` branch always
    matches. Every branch runs even when it received no rows.
    """
    branches = step["branches"]
    branches_path = _sub(step_path, "branches")
    compiled: list[tuple | None] = []
    for j, branch in enumerate(branches):
        when = branch["when"]
        when_path = _sub(_item(branches_path, j), "when")
        compiled.append(None if when == OTHERWISE else _compile(when, when_path))

    buckets: list[list[dict]] = [[] for _ in branches]
    for row in rows:
        for j, ast in enumerate(compiled):
            if ast is None or truthy(_evaluate(ast, row, _sub(_item(branches_path, j), "when"))):
                buckets[j].append(row)
                break

    out: list[dict] = []
    for j, (branch, bucket) in enumerate(zip(branches, buckets)):
        raw_steps = raw["branches"][j]["steps"]
        out.extend(execute_steps(branch["steps"], raw_steps, _sub(_item(branches_path, j), "steps"), bucket))
    return out


OP_EXECUTORS: dict[str, Executor] = {
    "select": _exec_select,
    "filter": _exec_filter,
    "map": _exec_map,
    "rename": _exec_rename,
    "limit": _exec_limit,
    "branch": _exec_branch,
}


def execute_steps(normalized: list[dict], raw_steps: list, steps_path: str, rows: list[dict]) -> list[dict]:
    """Run ``normalized`` (with its raw counterparts) over ``rows``.

    ``steps_path`` is the JSON path of the step list, used for error paths.
    """
    for index, (step, raw) in enumerate(zip(normalized, raw_steps)):
        step_path = _item(steps_path, index)
        executor = OP_EXECUTORS[step["op"]]
        try:
            rows = executor(step, raw, step_path, rows)
        except EtlError:
            raise
        except Exception as exc:  # defensive: never leak a traceback to stdout
            raise EtlError(
                EXECUTION_FAILED,
                f"step '{step['op']}' failed: {exc}",
                step_path,
            ) from None
    return rows


def execute_pipeline(normalized: list[dict], raw_steps: list, dataset: list[dict]) -> list[dict]:
    """Run the normalized top-level steps over copies of the dataset rows."""
    rows = [dict(row) for row in dataset]
    return execute_steps(normalized, raw_steps, STEPS_PATH, rows)


# ---------------------------------------------------------------------------
# Request processing
# ---------------------------------------------------------------------------


def process_request(request: Any, execute: bool = False) -> dict:
    """Validate, normalize and optionally execute a decoded request.

    Raises ``EtlError`` on any failure.
    """
    if not isinstance(request, dict):
        raise _schema_error("request must be a JSON object", "")
    steps = validate_steps(request)
    dataset = validate_dataset(request)
    tracker = ColumnTracker(dataset, enabled=not execute)
    normalized = normalize_steps(steps, STEPS_PATH, tracker)
    if not execute:
        return {"status": "ok", "normalized": {"steps": normalized}}
    data = execute_pipeline(normalized, steps, dataset)
    return {
        "status": "ok",
        "data": data,
        "metrics": {"rows_in": len(dataset), "rows_out": len(data)},
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

_TRUE_WORDS = {"true", "1", "yes", "on"}
_FALSE_WORDS = {"false", "0", "no", "off"}


def _parse_bool(text: str) -> bool:
    lowered = text.strip().lower()
    if lowered in _TRUE_WORDS:
        return True
    if lowered in _FALSE_WORDS:
        return False
    raise argparse.ArgumentTypeError(f"expected true/false, got {text!r}")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="etl_pipeline.py",
        description="Validate, normalize and optionally execute an ETL pipeline "
        "request read from STDIN.",
    )
    parser.add_argument(
        "--execute",
        nargs="?",
        const=True,
        default=False,
        type=_parse_bool,
        metavar="true|false",
        help="execute the pipeline over the dataset and return data + metrics "
        "(default: false, return the normalized pipeline only)",
    )
    return parser.parse_args(argv)


def run(stdin_text: str, execute: bool = False) -> tuple[dict, int]:
    """Return ``(response, exit_code)`` for the raw request text."""
    try:
        try:
            request = json.loads(stdin_text)
        except ValueError as exc:
            raise _schema_error(f"invalid JSON input: {exc}", "") from None
        return process_request(request, execute=execute), 0
    except EtlError as exc:
        return exc.to_response(), 1


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    response, code = run(sys.stdin.read(), execute=args.execute)
    sys.stdout.write(json.dumps(response, ensure_ascii=False))
    sys.stdout.write("\n")
    sys.stdout.flush()
    return code


if __name__ == "__main__":
    sys.exit(main())
