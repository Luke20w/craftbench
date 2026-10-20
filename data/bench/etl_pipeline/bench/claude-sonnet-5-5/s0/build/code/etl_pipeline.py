"""ETL pipeline CLI: reads a JSON request on stdin, validates and normalizes
the pipeline, and writes a JSON response on stdout (exit 0 ok, 1 error)."""
import json
import re
import sys

SCHEMA_FAILED = "SCHEMA_VALIDATION_FAILED"
UNKNOWN_OP = "UNKNOWN_OP"
MISSING_COLUMN = "MISSING_COLUMN"
BAD_EXPR = "BAD_EXPR"
EXECUTION_FAILED = "EXECUTION_FAILED"
MALFORMED_STEP = "MALFORMED_STEP"
OTHERWISE = "otherwise"


class EtlError(Exception):
    def __init__(self, code, message, path):
        super().__init__(message)
        self.code = code
        self.message = message
        self.path = path


def schema_error(message, path):
    return EtlError(SCHEMA_FAILED, message, path)


# ---------------------------------------------------------------- expressions

_TOKEN_RE = re.compile(
    r"""\s*(?:
        (?P<num>\d+\.\d*|\.\d+|\d+)
        |(?P<str>"[^"]*"|'[^']*')
        |(?P<id>[A-Za-z_][A-Za-z0-9_]*)
        |(?P<op>==|!=|>=|<=|&&|\|\||>|<|\+|-|\*|/|!)
        |(?P<paren>[()])
    )""",
    re.VERBOSE,
)
_KEYWORDS = {"and", "or", "not"}
_LITERALS = {"true": True, "false": False, "null": None}
# Operators that need a left operand; two of them side by side (e.g. `**`) is unsupported.
_BINARY_ONLY = {"*", "/", "==", "!=", "<", "<=", ">", ">=", "&&", "||"}
_SYMBOL_RUN_RE = re.compile(r"[*/<>=!&|^%~?]+")


class ExprSyntaxError(ValueError):
    def __init__(self, message, unsupported=False):
        super().__init__(message)
        self.unsupported = unsupported


def _unsupported(op):
    return ExprSyntaxError(f"unsupported operator '{op}'", unsupported=True)


def tokenize(text):
    """Return list of (kind, value); kind in num/str/id/kw/op/lp/rp."""
    tokens = []
    adjacent = []  # adjacent[i]: token i directly follows token i-1 without whitespace
    pos = 0
    text = text.rstrip()
    while pos < len(text):
        m = _TOKEN_RE.match(text, pos)
        if not m or m.end() == pos:
            rest = text[pos:].lstrip()
            run = _SYMBOL_RUN_RE.match(rest)
            if run:
                raise _unsupported(run.group())
            raise ExprSyntaxError(f"unexpected character {rest[:1]!r}")
        adjacent.append(m.start(m.lastgroup) == pos)
        pos = m.end()
        if m.group("num"):
            tokens.append(("num", m.group("num")))
        elif m.group("str"):
            tokens.append(("str", m.group("str")))
        elif m.group("id"):
            v = m.group("id")
            tokens.append(("kw", v.lower()) if v.lower() in _KEYWORDS else ("id", v))
        elif m.group("op"):
            tokens.append(("op", m.group("op")))
        else:
            tokens.append(("lp" if m.group("paren") == "(" else "rp", m.group("paren")))
    for i in range(1, len(tokens)):
        a, b = tokens[i - 1], tokens[i]
        if adjacent[i] and a[0] == "op" == b[0] and a[1] in _BINARY_ONLY and b[1] in _BINARY_ONLY:
            raise _unsupported(a[1] + b[1])
    return tokens


class _Parser:
    """Recursive descent building an AST over:
    or > and > not-keyword > comparison > add > mul > unary > atom."""

    def __init__(self, tokens):
        self.t = tokens
        self.i = 0

    def peek(self):
        return self.t[self.i] if self.i < len(self.t) else (None, None)

    def take(self):
        tok = self.peek()
        self.i += 1
        return tok

    def parse(self):
        if not self.t:
            raise ExprSyntaxError("empty expression")
        node = self.or_()
        if self.i != len(self.t):
            raise ExprSyntaxError(f"unexpected token {self.peek()[1]!r}")
        return node

    def _binary(self, sub, is_op, fold_kind="bin"):
        node = sub()
        while is_op(self.peek()):
            op = self.take()[1]
            node = (fold_kind, "||" if op == "or" else "&&" if op == "and" else op, node, sub())
        return node

    def or_(self):
        return self._binary(self.and_, lambda t: t in (("kw", "or"), ("op", "||")))

    def and_(self):
        return self._binary(self.not_, lambda t: t in (("kw", "and"), ("op", "&&")))

    def not_(self):
        if self.peek() == ("kw", "not"):
            self.take()
            return ("not", self.not_())
        return self.cmp_()

    def cmp_(self):
        return self._binary(self.add, lambda t: t[0] == "op" and t[1] in ("==", "!=", ">", ">=", "<", "<="))

    def add(self):
        return self._binary(self.mul, lambda t: t[0] == "op" and t[1] in ("+", "-"))

    def mul(self):
        return self._binary(self.unary, lambda t: t[0] == "op" and t[1] in ("*", "/"))

    def unary(self):
        kind, val = self.peek()
        if kind == "op" and val in ("+", "-", "!"):
            self.take()
            operand = self.unary()
            return ("not", operand) if val == "!" else ("neg", operand) if val == "-" else operand
        return self.atom()

    def atom(self):
        kind, val = self.take()
        if kind == "num":
            return ("lit", float(val) if "." in val else int(val))
        if kind == "str":
            return ("lit", val[1:-1])
        if kind == "id":
            if val in _LITERALS:
                return ("lit", _LITERALS[val])
            return ("id", val)
        if kind == "lp":
            node = self.or_()
            if self.take()[0] != "rp":
                raise ExprSyntaxError("missing closing parenthesis")
            return node
        if kind is None:
            raise ExprSyntaxError("unexpected end of expression")
        raise ExprSyntaxError(f"unexpected token {val!r}")


def parse_expr(text, path):
    try:
        return _Parser(tokenize(text)).parse()
    except ExprSyntaxError as e:
        if e.unsupported:
            raise EtlError(BAD_EXPR, f"ETL_ERROR: {e}", path)
        raise EtlError(BAD_EXPR, f"ETL_ERROR: invalid expression: {e}", path)


def validate_expr(text, path):
    parse_expr(text, path)


# ---------------------------------------------------------------- evaluation

def _is_num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _tidy(v):
    if isinstance(v, float) and v.is_integer() and abs(v) < 1e15:
        return int(v)
    return v


def _truthy(v):
    return v is not None and bool(v)


def _arith(op, a, b, path):
    if a is None or b is None:
        return None
    if not (_is_num(a) and _is_num(b)):
        raise EtlError(EXECUTION_FAILED, f"ETL_ERROR: operator '{op}' requires numeric operands", path)
    if op == "+":
        return _tidy(a + b)
    if op == "-":
        return _tidy(a - b)
    if op == "*":
        return _tidy(a * b)
    return None if b == 0 else _tidy(a / b)


def _compare(op, a, b):
    if a is None or b is None:
        return False
    if _is_num(a) and _is_num(b):
        pass
    elif isinstance(a, str) and isinstance(b, str):
        pass
    elif op in ("==", "!=") and type(a) is type(b):
        pass
    else:
        return False
    return {
        "==": lambda: a == b, "!=": lambda: a != b, "<": lambda: a < b,
        "<=": lambda: a <= b, ">": lambda: a > b, ">=": lambda: a >= b,
    }[op]()


def evaluate(node, row, path):
    kind = node[0]
    if kind == "lit":
        return node[1]
    if kind == "id":
        return row.get(node[1])
    if kind == "not":
        return not _truthy(evaluate(node[1], row, path))
    if kind == "neg":
        v = evaluate(node[1], row, path)
        if v is None:
            return None
        if not _is_num(v):
            raise EtlError(EXECUTION_FAILED, "ETL_ERROR: operator '-' requires numeric operands", path)
        return _tidy(-v)
    op = node[1]
    if op == "&&":
        return _truthy(evaluate(node[2], row, path)) and _truthy(evaluate(node[3], row, path))
    if op == "||":
        return _truthy(evaluate(node[2], row, path)) or _truthy(evaluate(node[3], row, path))
    a = evaluate(node[2], row, path)
    b = evaluate(node[3], row, path)
    if op in ("+", "-", "*", "/"):
        return _arith(op, a, b, path)
    return _compare(op, a, b)


# ---------------------------------------------------------------- steps

def _req(step, key, path):
    if key not in step:
        raise schema_error(f"ETL_ERROR: missing required field '{key}'", f"{path}.{key}")
    return step[key]


def _trimmed_str(step, key, path):
    val = _req(step, key, path)
    fpath = f"{path}.{key}"
    if not isinstance(val, str):
        raise schema_error(f"ETL_ERROR: '{key}' must be a string", fpath)
    val = val.strip()
    if not val:
        raise schema_error(f"ETL_ERROR: '{key}' must not be empty", fpath)
    return val


def _expr(step, key, path):
    val = _trimmed_str(step, key, path)
    validate_expr(val, f"{path}.{key}")
    return val


def norm_select(step, path):
    cols = _req(step, "columns", path)
    if not isinstance(cols, list) or not all(isinstance(c, str) for c in cols):
        raise schema_error("ETL_ERROR: 'columns' must be an array of strings", f"{path}.columns")
    return {"columns": list(cols)}


def norm_filter(step, path):
    return {"where": _expr(step, "where", path)}


def norm_map(step, path):
    return {"as": _trimmed_str(step, "as", path), "expr": _expr(step, "expr", path)}


def norm_rename(step, path):
    if "mapping" in step:
        mapping = step["mapping"]
        if not isinstance(mapping, dict) or not all(
            isinstance(v, str) for v in mapping.values()
        ):
            raise schema_error(
                "ETL_ERROR: 'mapping' must be an object of strings", f"{path}.mapping"
            )
        return {"mapping": dict(mapping)}
    if "from" in step or "to" in step:
        return {"mapping": {_trimmed_str(step, "from", path): _trimmed_str(step, "to", path)}}
    raise schema_error("ETL_ERROR: rename requires 'from' and 'to' or 'mapping'", f"{path}.mapping")


def norm_limit(step, path):
    n = _req(step, "n", path)
    if isinstance(n, bool) or not isinstance(n, int) or n < 0:
        raise schema_error("ETL_ERROR: 'n' must be an integer >= 0", f"{path}.n")
    return {"n": n}


def _is_otherwise(when):
    return when == OTHERWISE


def norm_branch(step, path):
    bpath = f"{path}.branches"
    branches = _req(step, "branches", path)
    if not isinstance(branches, list) or not branches:
        raise schema_error("ETL_ERROR: 'branches' must be a non-empty array", bpath)
    out = []
    for j, br in enumerate(branches):
        jpath = f"{bpath}[{j}]"
        if not isinstance(br, dict):
            raise schema_error("ETL_ERROR: branch must be an object", jpath)
        item = {}
        if "id" in br:
            if not isinstance(br["id"], str):
                raise schema_error("ETL_ERROR: 'id' must be a string", f"{jpath}.id")
            item["id"] = br["id"]
        when = _trimmed_str(br, "when", jpath)
        if not _is_otherwise(when):
            validate_expr(when, f"{jpath}.when")
        item["when"] = when
        item["steps"] = normalize_steps(_req(br, "steps", jpath), f"{jpath}.steps")
        out.append(item)
    others = [j for j, b in enumerate(out) if _is_otherwise(b["when"])]
    if len(others) > 1 or (others and others[0] != len(out) - 1):
        raise EtlError(
            MALFORMED_STEP,
            "ETL_ERROR: at most one 'otherwise' branch is allowed and it must be last",
            bpath,
        )
    merge = step.get("merge")
    strategy = "concat"
    if merge is not None:
        if not isinstance(merge, dict):
            raise schema_error("ETL_ERROR: 'merge' must be an object", f"{path}.merge")
        strategy = merge.get("strategy", "concat")
    if strategy != "concat":
        raise EtlError(
            MALFORMED_STEP, "ETL_ERROR: merge strategy must be 'concat'", f"{path}.merge.strategy"
        )
    return {"branches": out, "merge": {"strategy": "concat"}}


OPS = {
    "branch": norm_branch,
    "select": norm_select,
    "filter": norm_filter,
    "map": norm_map,
    "rename": norm_rename,
    "limit": norm_limit,
}


def normalize_steps(steps, path):
    if not isinstance(steps, list):
        raise schema_error("ETL_ERROR: 'steps' must be an array", path)
    return [normalize_step(s, f"{path}[{i}]") for i, s in enumerate(steps)]


def normalize_step(step, path):
    if not isinstance(step, dict):
        raise schema_error("ETL_ERROR: step must be an object", path)
    op = _req(step, "op", path)
    if not isinstance(op, str):
        raise schema_error("ETL_ERROR: 'op' must be a string", f"{path}.op")
    op = op.strip().lower()
    if not op:
        raise schema_error("ETL_ERROR: 'op' must not be empty", f"{path}.op")
    if op not in OPS:
        raise EtlError(UNKNOWN_OP, f"ETL_ERROR: unsupported op '{op}'", f"{path}.op")
    fields = OPS[op](step, path)
    out = {"op": op}
    for key in sorted(fields):
        out[key] = fields[key]
    return out


def normalize_request(req):
    if not isinstance(req, dict):
        raise schema_error("ETL_ERROR: request must be an object", "$")
    pipeline = req.get("pipeline")
    if not isinstance(pipeline, dict):
        raise schema_error("ETL_ERROR: 'pipeline' must be an object", "pipeline")
    steps = pipeline.get("steps")
    if not isinstance(steps, list):
        raise schema_error("ETL_ERROR: 'steps' must be an array", "pipeline.steps")
    dataset = req.get("dataset")
    if not isinstance(dataset, list):
        raise schema_error("ETL_ERROR: 'dataset' must be an array", "dataset")
    for i, row in enumerate(dataset):
        if not isinstance(row, dict):
            raise schema_error("ETL_ERROR: dataset rows must be objects", f"dataset[{i}]")
    return {"steps": normalize_steps(steps, "pipeline.steps")}


# ---------------------------------------------------------------- execution

def exec_select(step, rows, path):
    cols = step["columns"]
    out = []
    for row in rows:
        for i, c in enumerate(cols):
            if c not in row:
                raise EtlError(MISSING_COLUMN, f"ETL_ERROR: column '{c}' not found in row", f"{path}.columns[{i}]")
        out.append({c: row[c] for c in cols})
    return out


def exec_filter(step, rows, path):
    tree = parse_expr(step["where"], f"{path}.where")
    return [r for r in rows if _truthy(evaluate(tree, r, f"{path}.where"))]


def exec_map(step, rows, path):
    epath = f"{path}.expr"
    tree = parse_expr(step["expr"], epath)
    out = []
    for row in rows:
        new = dict(row)
        new[step["as"]] = evaluate(tree, row, epath)
        out.append(new)
    return out


def exec_rename(step, rows, path):
    out = []
    for row in rows:
        for src, dst in step["mapping"].items():
            if src not in row:
                raise EtlError(
                    MISSING_COLUMN, f"ETL_ERROR: column '{src}' not found in row", f"{path}.mapping.{src}"
                )
            row = {(dst if k == src else k): v for k, v in row.items() if k == src or k != dst}
        out.append(row)
    return out


def exec_limit(step, rows, path):
    return rows[: step["n"]]


def exec_branch(step, rows, path):
    branches = step["branches"]
    buckets = [[] for _ in branches]
    trees = [
        None if _is_otherwise(b["when"]) else parse_expr(b["when"], f"{path}.branches[{j}].when")
        for j, b in enumerate(branches)
    ]
    for row in rows:
        for j, tree in enumerate(trees):
            if tree is None or _truthy(evaluate(tree, row, f"{path}.branches[{j}].when")):
                buckets[j].append(row)
                break
    out = []
    for j, b in enumerate(branches):
        out.extend(execute_steps(b["steps"], buckets[j], f"{path}.branches[{j}].steps"))
    return out


EXECUTORS = {
    "branch": exec_branch,
    "select": exec_select,
    "filter": exec_filter,
    "map": exec_map,
    "rename": exec_rename,
    "limit": exec_limit,
}


def execute_steps(steps, rows, path):
    for i, step in enumerate(steps):
        rows = EXECUTORS[step["op"]](step, rows, f"{path}[{i}]")
    return rows


def execute(normalized, dataset):
    return execute_steps(normalized["steps"], dataset, "pipeline.steps")


def want_execute(argv):
    for i, arg in enumerate(argv):
        if arg == "--execute":
            nxt = argv[i + 1].lower() if i + 1 < len(argv) else ""
            return nxt != "false"
        if arg.startswith("--execute="):
            return arg.split("=", 1)[1].lower() not in ("false", "0", "no")
    return False


def main():
    try:
        try:
            req = json.loads(sys.stdin.read())
        except ValueError:
            raise schema_error("ETL_ERROR: invalid JSON input", "$")
        normalized = normalize_request(req)
        if want_execute(sys.argv[1:]):
            data = execute(normalized, req["dataset"])
            resp = {
                "status": "ok",
                "data": data,
                "metrics": {"rows_in": len(req["dataset"]), "rows_out": len(data)},
            }
        else:
            resp = {"status": "ok", "normalized": normalized}
        code = 0
    except EtlError as e:
        resp = {"status": "error", "error_code": e.code, "message": e.message, "path": e.path}
        code = 1
    sys.stdout.write(json.dumps(resp, ensure_ascii=False) + "\n")
    return code


if __name__ == "__main__":
    sys.exit(main())
