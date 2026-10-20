"""Tokenizer and recursive-descent parser for filter/map expressions.

Grammar (lowest to highest precedence):

    or_expr     := and_expr (("or"|"||") and_expr)*
    and_expr    := not_expr (("and"|"&&") not_expr)*
    not_expr    := "not" not_expr | comparison
    comparison  := additive (("=="|"!="|"<"|"<="|">"|">=") additive)?
    additive    := term (("+"|"-") term)*
    term        := unary (("*"|"/") unary)*
    unary       := ("-"|"+"|"!") unary | primary
    primary     := NUMBER | STRING | "true" | "false" | "null"
                 | IDENT | "(" or_expr ")"

`&&` and `||` are aliases of `and` and `or`. `!` is a high-precedence unary
(`!a == b` is `(!a) == b`), unlike the low-precedence `not`. Comparisons do not
chain (`a < b < c` is rejected). A run of operator characters that isn't a
supported operator (optionally followed by unary `!`/`-`/`+`), such as `**`
or `^^`, is reported as "unsupported operator '<run>'". `parse()` returns a
tuple-based AST so later stages can evaluate it:

    ("num", value) | ("str", value) | ("bool", value) | ("null",)
    ("col", name)
    ("unary", op, operand)          op in {"-", "+", "!", "not"}
    ("binary", op, left, right)     arithmetic, comparison, "and", "or"
"""

import re


class ExprSyntaxError(ValueError):
    pass


KEYWORDS = {"and", "or", "not", "true", "false", "null"}
COMPARISON_OPS = {"==", "!=", "<", "<=", ">", ">="}

_TOKEN_RE = re.compile(
    r"""
    (?P<ws>\s+)
  | (?P<num>(?:\d+\.\d*|\.\d+|\d+)(?:[eE][+-]?\d+)?)
  | (?P<ident>[A-Za-z_][A-Za-z0-9_]*)
  | (?P<str>"(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*')
  | (?P<op>[!%&*+\-/<=>^|~]+)
  | (?P<lparen>\()
  | (?P<rparen>\))
    """,
    re.VERBOSE,
)

# Longest first, so a run like `<=-` splits as `<=`, `-`.
OPERATORS = ("==", "!=", "<=", ">=", "&&", "||", "<", ">", "+", "-", "*", "/", "!")
UNARY_OPERATORS = ("!", "-", "+")
# Symbolic spellings mapped onto the keyword tokens the parser understands.
_OPERATOR_KEYWORDS = {"&&": "and", "||": "or"}

_ESCAPES = {"n": "\n", "t": "\t", "r": "\r", "\\": "\\", '"': '"', "'": "'"}


def _unquote(raw):
    body = raw[1:-1]
    out = []
    i = 0
    while i < len(body):
        ch = body[i]
        if ch == "\\":
            nxt = body[i + 1]
            if nxt not in _ESCAPES:
                raise ExprSyntaxError(f"invalid escape '\\{nxt}' in string literal")
            out.append(_ESCAPES[nxt])
            i += 2
        else:
            out.append(ch)
            i += 1
    return "".join(out)


def _split_operators(run):
    """Split a run of operator characters into supported operators.

    Only the first operator may be binary; anything after it must be a unary
    prefix (e.g. `a*-b`, `a&&!b`). Otherwise the whole run is unsupported.
    """
    ops = []
    i = 0
    while i < len(run):
        candidates = OPERATORS if not ops else UNARY_OPERATORS
        op = next((o for o in candidates if run.startswith(o, i)), None)
        if op is None:
            raise ExprSyntaxError(f"unsupported operator '{run}'")
        ops.append(op)
        i += len(op)
    return ops


def tokenize(text):
    """Return a list of (kind, value, position) tuples."""
    tokens = []
    pos = 0
    while pos < len(text):
        m = _TOKEN_RE.match(text, pos)
        if not m:
            raise ExprSyntaxError(f"unexpected character {text[pos]!r} at position {pos}")
        kind = m.lastgroup
        raw = m.group()
        if kind == "num":
            # Reject things like `3abc` instead of reading them as `3 abc`.
            end = m.end()
            if end < len(text) and (text[end].isalnum() or text[end] == "_"):
                raise ExprSyntaxError(f"invalid number at position {pos}")
            value = float(raw) if any(c in raw for c in ".eE") else int(raw)
            tokens.append(("num", value, pos))
        elif kind == "ident":
            tokens.append(("kw" if raw in KEYWORDS else "ident", raw, pos))
        elif kind == "str":
            tokens.append(("str", _unquote(raw), pos))
        elif kind == "op":
            offset = pos
            for op in _split_operators(raw):
                if op in _OPERATOR_KEYWORDS:
                    tokens.append(("kw", _OPERATOR_KEYWORDS[op], offset))
                else:
                    tokens.append(("op", op, offset))
                offset += len(op)
        elif kind != "ws":
            tokens.append((kind, raw, pos))
        pos = m.end()
    tokens.append(("eof", None, len(text)))
    return tokens


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

    def at(self, kind, *values):
        tok = self.peek()
        return tok[0] == kind and (not values or tok[1] in values)

    def fail(self, expected):
        kind, value, pos = self.peek()
        found = "end of expression" if kind == "eof" else repr(value)
        raise ExprSyntaxError(f"expected {expected} but found {found} at position {pos}")

    def parse(self):
        node = self.or_expr()
        if not self.at("eof"):
            self.fail("operator or end of expression")
        return node

    def or_expr(self):
        node = self.and_expr()
        while self.at("kw", "or"):
            self.advance()
            node = ("binary", "or", node, self.and_expr())
        return node

    def and_expr(self):
        node = self.not_expr()
        while self.at("kw", "and"):
            self.advance()
            node = ("binary", "and", node, self.not_expr())
        return node

    def not_expr(self):
        if self.at("kw", "not"):
            self.advance()
            return ("unary", "not", self.not_expr())
        return self.comparison()

    def comparison(self):
        node = self.additive()
        if self.at("op", *COMPARISON_OPS):
            op = self.advance()[1]
            node = ("binary", op, node, self.additive())
            if self.at("op", *COMPARISON_OPS):
                self.fail("end of comparison (comparisons cannot be chained)")
        return node

    def additive(self):
        node = self.term()
        while self.at("op", "+", "-"):
            op = self.advance()[1]
            node = ("binary", op, node, self.term())
        return node

    def term(self):
        node = self.unary()
        while self.at("op", "*", "/"):
            op = self.advance()[1]
            node = ("binary", op, node, self.unary())
        return node

    def unary(self):
        if self.at("op", "-", "+", "!"):
            op = self.advance()[1]
            return ("unary", op, self.unary())
        return self.primary()

    def primary(self):
        kind, value, _ = self.peek()
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
            return ("null",)
        if kind == "lparen":
            self.advance()
            node = self.or_expr()
            if not self.at("rparen"):
                self.fail("')'")
            self.advance()
            return node
        self.fail("a value")


def parse(text):
    """Parse an expression string into an AST, raising ExprSyntaxError."""
    return _Parser(tokenize(text)).parse()
