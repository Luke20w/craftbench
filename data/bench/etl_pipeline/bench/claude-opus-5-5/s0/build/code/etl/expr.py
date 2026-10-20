"""Tokenizer and recursive-descent parser for filter/map expressions.

Grammar (lowest to highest precedence):

    expr       := or_expr
    or_expr    := and_expr (("||" | "or") and_expr)*
    and_expr   := not_expr (("&&" | "and") not_expr)*
    not_expr   := ("!" | "not") not_expr | comparison
    comparison := additive (COMP_OP additive)?
    additive   := term (("+" | "-") term)*
    term       := unary (("*" | "/") unary)*
    unary      := "-" unary | "+" unary | primary
    primary    := NUMBER | STRING | "true" | "false" | "null"
                | IDENT | "(" expr ")"

Parsing yields a tree of tuples:

    ("num", value) ("str", value) ("bool", value) ("null",)
    ("col", name)
    ("unary", op, operand)          op in {"-", "+", "not"}  ("!" parses as "not")
    ("binary", op, left, right)     arithmetic, comparison, "and", "or"

Comparisons do not chain: ``a < b < c`` is a syntax error.

Operator characters are lexed as maximal runs (e.g. ``*-`` or ``**``). A run is
valid if it is an optional binary operator followed only by prefix operators
(``-``, ``+``, ``!``); anything else (``**``, ``^^``, ``=``) is reported as an
unsupported operator naming the whole run.
"""

from dataclasses import dataclass

COMPARISON_OPS = (">=", "<=", "==", "!=", ">", "<")
ARITH_OPS = ("+", "-", "*", "/")
LOGICAL_OPS = ("&&", "||")
BINARY_OPS = LOGICAL_OPS + COMPARISON_OPS + ARITH_OPS  # longest first where prefixes overlap
PREFIX_OPS = ("-", "+", "!")
OPERATOR_CHARS = set("+-*/=!<>&|^%~?:")
KEYWORDS = {"and", "or", "not", "true", "false", "null"}


class ExprSyntaxError(Exception):
    pass


def _split_operator_run(run, pos):
    """Split a run of operator characters into op tokens, or raise."""
    def prefix_tokens(rest, start):
        if all(ch in PREFIX_OPS for ch in rest):
            return [Token("op", ch, start + k) for k, ch in enumerate(rest)]
        return None

    tokens = prefix_tokens(run, pos)
    if tokens is not None:
        return tokens
    for op in BINARY_OPS:
        if run.startswith(op):
            rest = prefix_tokens(run[len(op):], pos + len(op))
            if rest is not None:
                return [Token("op", op, pos)] + rest
    raise ExprSyntaxError(f"unsupported operator '{run}'")


@dataclass(frozen=True)
class Token:
    kind: str  # "num", "str", "ident", "kw", "op", "lparen", "rparen", "eof"
    value: object
    pos: int


def tokenize(text):
    tokens = []
    i, n = 0, len(text)
    while i < n:
        ch = text[i]
        if ch.isspace():
            i += 1
        elif ch.isdigit() or (ch == "." and i + 1 < n and text[i + 1].isdigit()):
            start = i
            while i < n and text[i].isdigit():
                i += 1
            is_float = False
            if i < n and text[i] == ".":
                is_float = True
                i += 1
                while i < n and text[i].isdigit():
                    i += 1
            if i < n and (text[i].isalpha() or text[i] == "_"):
                raise ExprSyntaxError(f"invalid number at position {start}")
            raw = text[start:i]
            tokens.append(Token("num", float(raw) if is_float else int(raw), start))
        elif ch.isalpha() or ch == "_":
            start = i
            while i < n and (text[i].isalnum() or text[i] == "_"):
                i += 1
            word = text[start:i]
            tokens.append(Token("kw" if word in KEYWORDS else "ident", word, start))
        elif ch in "'\"":
            start = i
            i += 1
            chars = []
            while i < n and text[i] != ch:
                if text[i] == "\\" and i + 1 < n:
                    i += 1
                chars.append(text[i])
                i += 1
            if i >= n:
                raise ExprSyntaxError(f"unterminated string at position {start}")
            i += 1
            tokens.append(Token("str", "".join(chars), start))
        elif ch == "(":
            tokens.append(Token("lparen", ch, i))
            i += 1
        elif ch == ")":
            tokens.append(Token("rparen", ch, i))
            i += 1
        elif ch in OPERATOR_CHARS:
            start = i
            while i < n and text[i] in OPERATOR_CHARS:
                i += 1
            tokens.extend(_split_operator_run(text[start:i], start))
        else:
            raise ExprSyntaxError(f"unexpected character {ch!r} at position {i}")
    tokens.append(Token("eof", None, n))
    return tokens


class _Parser:
    def __init__(self, tokens):
        self.tokens = tokens
        self.pos = 0

    def peek(self):
        return self.tokens[self.pos]

    def advance(self):
        tok = self.tokens[self.pos]
        self.pos += 1
        return tok

    def at(self, kind, *values):
        tok = self.peek()
        return tok.kind == kind and (not values or tok.value in values)

    def parse(self):
        node = self.or_expr()
        if not self.at("eof"):
            tok = self.peek()
            raise ExprSyntaxError(f"unexpected token {tok.value!r} at position {tok.pos}")
        return node

    def or_expr(self):
        node = self.and_expr()
        while self.at("kw", "or") or self.at("op", "||"):
            self.advance()
            node = ("binary", "or", node, self.and_expr())
        return node

    def and_expr(self):
        node = self.not_expr()
        while self.at("kw", "and") or self.at("op", "&&"):
            self.advance()
            node = ("binary", "and", node, self.not_expr())
        return node

    def not_expr(self):
        if self.at("kw", "not") or self.at("op", "!"):
            self.advance()
            return ("unary", "not", self.not_expr())
        return self.comparison()

    def comparison(self):
        node = self.additive()
        if self.at("op", *COMPARISON_OPS):
            op = self.advance().value
            node = ("binary", op, node, self.additive())
            if self.at("op", *COMPARISON_OPS):
                tok = self.peek()
                raise ExprSyntaxError(f"chained comparison at position {tok.pos}")
        return node

    def additive(self):
        node = self.term()
        while self.at("op", "+", "-"):
            op = self.advance().value
            node = ("binary", op, node, self.term())
        return node

    def term(self):
        node = self.unary()
        while self.at("op", "*", "/"):
            op = self.advance().value
            node = ("binary", op, node, self.unary())
        return node

    def unary(self):
        if self.at("op", "-", "+"):
            op = self.advance().value
            return ("unary", op, self.unary())
        return self.primary()

    def primary(self):
        tok = self.advance()
        if tok.kind == "num":
            return ("num", tok.value)
        if tok.kind == "str":
            return ("str", tok.value)
        if tok.kind == "ident":
            return ("col", tok.value)
        if tok.kind == "kw" and tok.value in ("true", "false"):
            return ("bool", tok.value == "true")
        if tok.kind == "kw" and tok.value == "null":
            return ("null",)
        if tok.kind == "lparen":
            node = self.or_expr()
            if not self.at("rparen"):
                raise ExprSyntaxError(f"expected ')' at position {self.peek().pos}")
            self.advance()
            return node
        if tok.kind == "eof":
            raise ExprSyntaxError("unexpected end of expression")
        raise ExprSyntaxError(f"unexpected token {tok.value!r} at position {tok.pos}")


def parse_expr(text):
    """Parse an expression string into an AST; raises ExprSyntaxError."""
    return _Parser(tokenize(text)).parse()


def referenced_columns(node):
    """Return the set of column names referenced by an AST."""
    kind = node[0]
    if kind == "col":
        return {node[1]}
    if kind == "unary":
        return referenced_columns(node[2])
    if kind == "binary":
        return referenced_columns(node[2]) | referenced_columns(node[3])
    return set()
