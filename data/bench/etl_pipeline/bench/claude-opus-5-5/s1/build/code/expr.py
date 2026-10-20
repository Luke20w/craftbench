"""Tokenizer and parser for filter/map expressions.

Grammar (lowest to highest precedence):

    expr       := or_expr
    or_expr    := and_expr (("or" | "||") and_expr)*
    and_expr   := not_expr (("and" | "&&") not_expr)*
    not_expr   := "not" not_expr | comparison
    comparison := additive (CMP additive)?          # comparisons do not chain
    additive   := term (("+" | "-") term)*
    term       := unary (("*" | "/") unary)*
    unary      := ("-" | "!") unary | primary
    primary    := NUMBER | STRING | IDENT | `quoted ident` | true | false | null
                | "(" expr ")"

The parser produces a small tuple-based AST:

    ("num", value) | ("str", value) | ("bool", value) | ("null", None)
    ("col", name)
    ("neg", operand) | ("not", operand)
    ("bin", op, left, right)      # op in + - * / > >= < <= == != and or

`&&`, `||` and `!` are parsed to the same nodes as `and`, `or` and `not`.
Any other run of operator characters (e.g. `**`, `^^`, `=`) is rejected
with "unsupported operator '<run>'".
"""

import math
import re

CMP_OPS = (">=", "<=", "==", "!=", ">", "<")
KEYWORDS = {"and", "or", "not", "true", "false", "null"}

_TOKEN_RE = re.compile(
    r"""
    (?P<ws>\s+)
  | (?P<num>(?:\d+\.\d*|\.\d+|\d+)(?:[eE][+-]?\d+)?)
  | (?P<str>"(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*')
  | (?P<qident>`[^`]+`)
  | (?P<ident>[A-Za-z_][A-Za-z0-9_]*)
  | (?P<paren>[()])
  | (?P<sym>[!<>=+\-*/&|^%~?:@#$]+)
    """,
    re.VERBOSE,
)

# Longest first so greedy splitting prefers two-character operators.
_OPERATORS = ("&&", "||", ">=", "<=", "==", "!=", ">", "<", "+", "-", "*", "/", "!")
# Unary operators may directly follow another operator (e.g. `a * -b`, `!!x`).
_UNARY_OPS = ("-", "!")
_OP_ALIASES = {"&&": ("kw", "and"), "||": ("kw", "or")}


class ExprError(Exception):
    pass


def tokenize(src):
    tokens = []
    pos = 0
    while pos < len(src):
        m = _TOKEN_RE.match(src, pos)
        if not m:
            raise ExprError(f"unexpected character {src[pos]!r} at position {pos}")
        kind = m.lastgroup
        text = m.group()
        pos = m.end()
        if kind == "ws":
            continue
        if kind == "num":
            value = float(text) if any(c in text for c in ".eE") else int(text)
            tokens.append(("num", value))
        elif kind == "str":
            tokens.append(("str", _unescape(text[1:-1])))
        elif kind == "qident":
            tokens.append(("ident", text[1:-1]))
        elif kind == "ident":
            if text in KEYWORDS:
                tokens.append(("kw", text))
            else:
                tokens.append(("ident", text))
        elif kind == "paren":
            tokens.append(("op", text))
        else:
            tokens.extend(_split_operators(text))
    tokens.append(("eof", None))
    return tokens


def _split_operators(run):
    """Split a run of operator characters into known operator tokens."""
    ops = []
    pos = 0
    while pos < len(run):
        op = next((o for o in _OPERATORS if run.startswith(o, pos)), None)
        if op is None or (ops and op not in _UNARY_OPS):
            raise ExprError(f"unsupported operator '{run}'")
        ops.append(op)
        pos += len(op)
    return [_OP_ALIASES.get(op, ("op", op)) for op in ops]


def _unescape(body):
    return re.sub(r"\\(.)", lambda m: {"n": "\n", "t": "\t"}.get(m.group(1), m.group(1)), body)


class _Parser:
    def __init__(self, tokens):
        self.tokens = tokens
        self.i = 0

    def peek(self):
        return self.tokens[self.i]

    def advance(self):
        tok = self.tokens[self.i]
        self.i += 1
        return tok

    def accept(self, kind, value):
        if self.peek() == (kind, value):
            self.i += 1
            return True
        return False

    def parse(self):
        node = self.or_expr()
        if self.peek()[0] != "eof":
            raise ExprError(f"unexpected token {self.peek()[1]!r}")
        return node

    def or_expr(self):
        node = self.and_expr()
        while self.accept("kw", "or"):
            node = ("bin", "or", node, self.and_expr())
        return node

    def and_expr(self):
        node = self.not_expr()
        while self.accept("kw", "and"):
            node = ("bin", "and", node, self.not_expr())
        return node

    def not_expr(self):
        if self.accept("kw", "not"):
            return ("not", self.not_expr())
        return self.comparison()

    def comparison(self):
        node = self.additive()
        kind, value = self.peek()
        if kind == "op" and value in CMP_OPS:
            self.advance()
            node = ("bin", value, node, self.additive())
            kind, value = self.peek()
            if kind == "op" and value in CMP_OPS:
                raise ExprError("chained comparisons are not supported")
        return node

    def additive(self):
        node = self.term()
        while self.peek() in (("op", "+"), ("op", "-")):
            op = self.advance()[1]
            node = ("bin", op, node, self.term())
        return node

    def term(self):
        node = self.unary()
        while self.peek() in (("op", "*"), ("op", "/")):
            op = self.advance()[1]
            node = ("bin", op, node, self.unary())
        return node

    def unary(self):
        if self.accept("op", "-"):
            return ("neg", self.unary())
        if self.accept("op", "!"):
            return ("not", self.unary())
        return self.primary()

    def primary(self):
        kind, value = self.advance()
        if kind == "num":
            return ("num", value)
        if kind == "str":
            return ("str", value)
        if kind == "ident":
            return ("col", value)
        if kind == "kw" and value in ("true", "false"):
            return ("bool", value == "true")
        if kind == "kw" and value == "null":
            return ("null", None)
        if (kind, value) == ("op", "("):
            node = self.or_expr()
            if not self.accept("op", ")"):
                raise ExprError("missing closing parenthesis")
            return node
        if kind == "eof":
            raise ExprError("unexpected end of expression")
        raise ExprError(f"unexpected token {value!r}")


def parse(src):
    """Parse an expression string into an AST. Raises ExprError."""
    return _Parser(tokenize(src)).parse()


def columns_referenced(node):
    """Return the set of column names referenced by an AST."""
    tag = node[0]
    if tag == "col":
        return {node[1]}
    if tag in ("neg", "not"):
        return columns_referenced(node[1])
    if tag == "bin":
        return columns_referenced(node[2]) | columns_referenced(node[3])
    return set()


# ---------------------------------------------------------------------------
# Evaluation
#
# Semantics: null propagates through arithmetic and unary minus; division by
# zero yields null; comparisons involving null or mismatched types are false;
# boolean operators treat null as falsy and always return a bool.
# ---------------------------------------------------------------------------

class EvalError(Exception):
    pass


def _is_number(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def truthy(v):
    return v is not None and v is not False and v != 0 and v != ""


def _tidy_number(v):
    """Non-finite results become null; integral floats become ints (12.5 * 8 -> 100)."""
    if isinstance(v, float):
        if not math.isfinite(v):
            return None
        if v.is_integer() and abs(v) < 2 ** 53:
            return int(v)
    return v


def _same_kind(a, b):
    if _is_number(a) and _is_number(b):
        return True
    return type(a) is type(b)


def _arith(op, a, b):
    if a is None or b is None:
        return None
    if op == "+" and isinstance(a, str) and isinstance(b, str):
        return a + b
    if not (_is_number(a) and _is_number(b)):
        raise EvalError(f"operator '{op}' not supported between {_type_name(a)} and {_type_name(b)}")
    if op == "+":
        return _tidy_number(a + b)
    if op == "-":
        return _tidy_number(a - b)
    if op == "*":
        return _tidy_number(a * b)
    if b == 0:
        return None
    return _tidy_number(a / b)


def _compare(op, a, b):
    if a is None or b is None or not _same_kind(a, b):
        return False
    if op == "==":
        return a == b
    if op == "!=":
        return a != b
    if not (_is_number(a) or isinstance(a, str)):
        return False
    if op == "<":
        return a < b
    if op == "<=":
        return a <= b
    if op == ">":
        return a > b
    return a >= b


def _type_name(v):
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "boolean"
    if _is_number(v):
        return "number"
    if isinstance(v, str):
        return "string"
    if isinstance(v, list):
        return "array"
    return "object"


def evaluate(node, row):
    """Evaluate an AST against a row (dict). Missing columns are null. Raises EvalError."""
    tag = node[0]
    if tag in ("num", "str", "bool", "null"):
        return node[1]
    if tag == "col":
        return row.get(node[1])
    if tag == "not":
        return not truthy(evaluate(node[1], row))
    if tag == "neg":
        v = evaluate(node[1], row)
        if v is None:
            return None
        if not _is_number(v):
            raise EvalError(f"unary '-' not supported for {_type_name(v)}")
        return _tidy_number(-v)
    _, op, left, right = node
    if op == "and":
        return truthy(evaluate(left, row)) and truthy(evaluate(right, row))
    if op == "or":
        return truthy(evaluate(left, row)) or truthy(evaluate(right, row))
    a = evaluate(left, row)
    b = evaluate(right, row)
    if op in CMP_OPS:
        return _compare(op, a, b)
    return _arith(op, a, b)
