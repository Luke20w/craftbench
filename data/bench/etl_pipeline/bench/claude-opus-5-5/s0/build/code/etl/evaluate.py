"""Evaluate expression ASTs (see ``expr.py``) against a single row.

Semantics:
  * Missing columns resolve to null.
  * Arithmetic with a null operand yields null; division by zero yields null.
    Arithmetic on non-numeric (non-null) values raises ``EvalError``.
  * Comparisons involving null, or between mismatched types, yield false
    (this holds for ``!=`` too). Ints and floats are the same type; bools are not numbers.
  * ``and``/``or``/``not`` use truthiness (null, false, 0, "", [] and {} are falsy)
    and always yield booleans.
"""

import math


class EvalError(Exception):
    pass


def is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def truthy(value):
    return value is not None and value is not False and bool(value)


def _type_class(value):
    if is_number(value):
        return "number"
    return type(value).__name__


def _tidy_number(value):
    """Integral floats become ints (100.0 -> 100); non-finite results become null."""
    if isinstance(value, float):
        if not math.isfinite(value):
            return None
        if value.is_integer():
            return int(value)
    return value


def _arith(op, left, right):
    if left is None or right is None:
        return None
    if not (is_number(left) and is_number(right)):
        raise EvalError(
            f"operator '{op}' requires numbers, got {_type_class(left)} and {_type_class(right)}"
        )
    if op == "+":
        result = left + right
    elif op == "-":
        result = left - right
    elif op == "*":
        result = left * right
    else:
        if right == 0:
            return None
        result = left / right
    return _tidy_number(result)


_ORDERING = {
    "<": lambda a, b: a < b,
    "<=": lambda a, b: a <= b,
    ">": lambda a, b: a > b,
    ">=": lambda a, b: a >= b,
}


def _compare(op, left, right):
    if left is None or right is None or _type_class(left) != _type_class(right):
        return False
    if op == "==":
        return left == right
    if op == "!=":
        return left != right
    if not isinstance(left, (int, float, str)):  # lists/objects have no ordering
        return False
    return _ORDERING[op](left, right)


def evaluate(node, row):
    kind = node[0]
    if kind in ("num", "str", "bool"):
        return node[1]
    if kind == "null":
        return None
    if kind == "col":
        return row.get(node[1])
    if kind == "unary":
        op, operand = node[1], evaluate(node[2], row)
        if op == "not":
            return not truthy(operand)
        if operand is None:
            return None
        if not is_number(operand):
            raise EvalError(f"unary '{op}' requires a number, got {_type_class(operand)}")
        return -operand if op == "-" else operand
    if kind == "binary":
        op = node[1]
        if op == "and":
            return truthy(evaluate(node[2], row)) and truthy(evaluate(node[3], row))
        if op == "or":
            return truthy(evaluate(node[2], row)) or truthy(evaluate(node[3], row))
        left, right = evaluate(node[2], row), evaluate(node[3], row)
        if op in ("+", "-", "*", "/"):
            return _arith(op, left, right)
        return _compare(op, left, right)
    raise EvalError(f"unknown expression node {kind!r}")
