"""Evaluate expression ASTs (see `expr.parse`) against a row.

Semantics:
- Missing identifiers resolve to null.
- Arithmetic with a null operand is null; division by zero is null.
  `+` also concatenates two strings. Any other operand types raise EvalError.
- Comparisons involving null are false (including `!=`), as are comparisons
  between different types. Ints and floats are the same type; bools are not
  numbers.
- `and`/`or`/`not`/`!` treat null, false, 0 and "" (and empty arrays/objects)
  as falsy and always produce a boolean.
- Integral float results of arithmetic are returned as ints (`12.5 * 8` is
  `100`); non-finite results raise EvalError.
"""

import math
import operator


class EvalError(ValueError):
    pass


def _is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _type_name(value):
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
    return "object"


def truthy(value):
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    if _is_number(value):
        return value != 0
    return len(value) > 0


def _tidy_number(value):
    if isinstance(value, float):
        if not math.isfinite(value):
            raise EvalError("arithmetic result is not a finite number")
        if value.is_integer():
            return int(value)
    return value


_ARITHMETIC = {"+": operator.add, "-": operator.sub, "*": operator.mul, "/": operator.truediv}
_ORDERING = {"<": operator.lt, "<=": operator.le, ">": operator.gt, ">=": operator.ge}


def _arithmetic(op, left, right):
    if left is None or right is None:
        return None
    if op == "+" and isinstance(left, str) and isinstance(right, str):
        return left + right
    if not (_is_number(left) and _is_number(right)):
        raise EvalError(
            f"operator '{op}' not supported between {_type_name(left)} and {_type_name(right)}"
        )
    if op == "/" and right == 0:
        return None
    try:
        return _tidy_number(_ARITHMETIC[op](left, right))
    except OverflowError:
        raise EvalError("arithmetic result is not a finite number")


def _compare(op, left, right):
    if left is None or right is None:
        return False
    if _type_name(left) != _type_name(right):
        return False
    if op == "==":
        return left == right
    if op == "!=":
        return left != right
    if isinstance(left, (list, dict)):
        return False
    return _ORDERING[op](left, right)


def _unary(op, value):
    if op in ("not", "!"):
        return not truthy(value)
    if value is None:
        return None
    if not _is_number(value):
        raise EvalError(f"unary '{op}' not supported for {_type_name(value)}")
    return -value if op == "-" else value


def evaluate(node, row):
    kind = node[0]
    if kind in ("num", "str", "bool"):
        return node[1]
    if kind == "null":
        return None
    if kind == "col":
        return row.get(node[1])
    if kind == "unary":
        return _unary(node[1], evaluate(node[2], row))
    op, left_node, right_node = node[1], node[2], node[3]
    if op == "and":
        return truthy(evaluate(left_node, row)) and truthy(evaluate(right_node, row))
    if op == "or":
        return truthy(evaluate(left_node, row)) or truthy(evaluate(right_node, row))
    left = evaluate(left_node, row)
    right = evaluate(right_node, row)
    if op in _ARITHMETIC:
        return _arithmetic(op, left, right)
    return _compare(op, left, right)
