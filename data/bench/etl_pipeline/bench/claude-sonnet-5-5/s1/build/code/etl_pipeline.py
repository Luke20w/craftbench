#!/usr/bin/env python3
"""ETL pipeline CLI: reads a JSON request on stdin, validates and normalizes
the pipeline (and with --execute runs it over the dataset), and writes a JSON response on stdout (exit 0 ok, 1 error)."""
import json
import re
import sys

SCHEMA = "SCHEMA_VALIDATION_FAILED"
UNKNOWN_OP = "UNKNOWN_OP"
MISSING_COLUMN = "MISSING_COLUMN"
BAD_EXPR = "BAD_EXPR"


class EtlError(Exception):
    def __init__(self, code, message, path):
        super().__init__(message)
        self.code = code
        self.message = message
        self.path = path


# --------------------------------------------------------------------------
# Expression language: tokenizer, parser (builds an AST) and evaluator
# --------------------------------------------------------------------------

_TOKEN_RE = re.compile(
    r"""\s*(?:
        (?P<num>\d+(?:\.\d+)?|\.\d+)
      | (?P<str>"(?:[^"\\]|\\.)*"|'[^']*')
      | (?P<id>[A-Za-z_][A-Za-z0-9_]*)
      | (?P<sym>[*/^%&|=<>!~?:]+)
      | (?P<op>[-+()])
    )""",
    re.VERBOSE,
)
_KEYWORDS = {"and", "or", "not"}
_LITERALS = {"true": True, "false": False, "null": None}
_SYM_OPS = {"*", "/", "<", "<=", ">", ">=", "==", "!=", "&&", "||", "!"}


class ExprSyntaxError(ValueError):
    pass


def _split_symbols(run):
    """Split a run of symbol characters into valid operator tokens."""
    if run in _SYM_OPS:
        return [run]
    # allow trailing unary '!' (e.g. "a >= !b" written without spaces)
    core = run.rstrip("!")
    if core and core in _SYM_OPS:
        return [core] + ["!"] * (len(run) - len(core))
    if not core and set(run) == {"!"}:
        return ["!"] * len(run)
    raise ExprSyntaxError(f"unsupported operator '{run}'")


def _tokenize(text):
    tokens = []
    pos = 0
    text = text.rstrip()
    while pos < len(text):
        m = _TOKEN_RE.match(text, pos)
        if not m or m.end() == pos:
            raise ExprSyntaxError(f"unexpected character {text[pos:].lstrip()[:1]!r}")
        pos = m.end()
        kind = m.lastgroup
        val = m.group(kind)
        if kind == "sym":
            for s in _split_symbols(val):
                tokens.append(("op", s))
            continue
        if kind == "id" and val in _KEYWORDS:
            kind = "kw"
        tokens.append((kind, val))
    return tokens


def _unquote(raw):
    if raw[0] == '"':
        try:
            return json.loads(raw)
        except ValueError:
            pass
    return raw[1:-1]


class _Parser:
    """Recursive-descent parser producing a tuple AST:
    ("lit", v) | ("id", name) | ("not", e) | ("neg", e) | ("pos", e)
    | ("bin", op, l, r)"""

    def __init__(self, tokens):
        self.t = tokens
        self.i = 0

    def peek(self):
        return self.t[self.i] if self.i < len(self.t) else (None, None)

    def take(self):
        tok = self.peek()
        self.i += 1
        return tok

    def is_op(self, *vals):
        k, v = self.peek()
        return k in ("op", "kw") and v in vals

    def parse(self):
        if not self.t:
            raise ExprSyntaxError("empty expression")
        node = self.or_expr()
        if self.i < len(self.t):
            raise ExprSyntaxError(f"unexpected token {self.peek()[1]!r}")
        return node

    def _binary(self, sub, ops, alias=None):
        left = sub()
        while self.is_op(*ops):
            op = self.take()[1]
            op = (alias or {}).get(op, op)
            left = ("bin", op, left, sub())
        return left

    def or_expr(self):
        return self._binary(self.and_expr, ("||", "or"), {"or": "||"})

    def and_expr(self):
        return self._binary(self.eq_expr, ("&&", "and"), {"and": "&&"})

    def eq_expr(self):
        return self._binary(self.rel_expr, ("==", "!="))

    def rel_expr(self):
        return self._binary(self.add_expr, ("<", "<=", ">", ">="))

    def add_expr(self):
        return self._binary(self.mul_expr, ("+", "-"))

    def mul_expr(self):
        return self._binary(self.unary, ("*", "/"))

    def unary(self):
        if self.is_op("!", "not"):
            self.take()
            return ("not", self.unary())
        if self.is_op("-"):
            self.take()
            return ("neg", self.unary())
        if self.is_op("+"):
            self.take()
            return self.unary()
        return self.atom()

    def atom(self):
        kind, val = self.take()
        if kind == "num":
            return ("lit", float(val) if "." in val else int(val))
        if kind == "str":
            return ("lit", _unquote(val))
        if kind == "id":
            if val in _LITERALS:
                return ("lit", _LITERALS[val])
            return ("id", val)
        if kind == "op" and val == "(":
            node = self.or_expr()
            if self.take()[1] != ")":
                raise ExprSyntaxError("missing closing parenthesis")
            return node
        if kind is None:
            raise ExprSyntaxError("unexpected end of expression")
        raise ExprSyntaxError(f"unexpected token {val!r}")


def parse_expr(text, path):
    try:
        return _Parser(_tokenize(text)).parse()
    except ExprSyntaxError as e:
        msg = str(e)
        if not msg.startswith("unsupported operator"):
            msg = f"invalid expression: {msg}"
        raise EtlError(BAD_EXPR, f"ETL_ERROR: {msg}", path)


def check_expr(text, path):
    parse_expr(text, path)


def _is_num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _truthy(v):
    return v is not None and bool(v)


def _arith(op, a, b):
    if a is None or b is None:
        return None
    if op == "+" and isinstance(a, str) and isinstance(b, str):
        return a + b
    if not (_is_num(a) and _is_num(b)):
        return None
    if op == "+":
        return a + b
    if op == "-":
        return a - b
    if op == "*":
        return a * b
    if b == 0:
        return None
    return a / b


def _compare(op, a, b):
    if a is None or b is None:
        return False
    if _is_num(a) and _is_num(b):
        pass
    elif type(a) is not type(b):
        return False
    if op == "==":
        return a == b
    if op == "!=":
        return a != b
    if isinstance(a, (bool, dict, list)):
        return False
    return {"<": a < b, "<=": a <= b, ">": a > b, ">=": a >= b}[op]


def evaluate(node, row):
    kind = node[0]
    if kind == "lit":
        return node[1]
    if kind == "id":
        return row.get(node[1])
    if kind == "not":
        return not _truthy(evaluate(node[1], row))
    if kind == "neg":
        v = evaluate(node[1], row)
        return -v if _is_num(v) else None
    _, op, left, right = node
    if op == "&&":
        return _truthy(evaluate(left, row)) and _truthy(evaluate(right, row))
    if op == "||":
        return _truthy(evaluate(left, row)) or _truthy(evaluate(right, row))
    a, b = evaluate(left, row), evaluate(right, row)
    if op in ("+", "-", "*", "/"):
        return _arith(op, a, b)
    return _compare(op, a, b)


def _clean(v):
    """Render integral floats as ints so 12.5 * 8 yields 100, not 100.0."""
    if isinstance(v, float) and v.is_integer():
        return int(v)
    return v


# --------------------------------------------------------------------------
# Field helpers
# --------------------------------------------------------------------------

def _schema(msg, path):
    return EtlError(SCHEMA, f"ETL_ERROR: {msg}", path)


def req_trimmed_str(step, field, path):
    if field not in step:
        raise _schema(f"missing required field '{field}'", f"{path}.{field}")
    v = step[field]
    if not isinstance(v, str):
        raise _schema(f"'{field}' must be a string", f"{path}.{field}")
    v = v.strip()
    if not v:
        raise _schema(f"'{field}' must not be empty", f"{path}.{field}")
    return v


def req_expr(step, field, path):
    v = req_trimmed_str(step, field, path)
    check_expr(v, f"{path}.{field}")
    return v


# --------------------------------------------------------------------------
# Per-op normalizers: each returns a dict of fields (excluding "op")
# --------------------------------------------------------------------------

def norm_select(step, path):
    if "columns" not in step:
        raise _schema("missing required field 'columns'", f"{path}.columns")
    cols = step["columns"]
    if not isinstance(cols, list):
        raise _schema("'columns' must be an array of strings", f"{path}.columns")
    for j, c in enumerate(cols):
        if not isinstance(c, str):
            raise _schema("column names must be strings", f"{path}.columns[{j}]")
    return {"columns": list(cols)}


def norm_filter(step, path):
    return {"where": req_expr(step, "where", path)}


def norm_map(step, path):
    return {"as": req_trimmed_str(step, "as", path), "expr": req_expr(step, "expr", path)}


def norm_rename(step, path):
    if "mapping" in step:
        m = step["mapping"]
        if not isinstance(m, dict):
            raise _schema("'mapping' must be an object", f"{path}.mapping")
        for k, v in m.items():
            if not isinstance(v, str):
                raise _schema("mapping values must be strings", f"{path}.mapping.{k}")
        return {"mapping": dict(m)}
    if "from" in step or "to" in step:
        f = req_trimmed_str(step, "from", path)
        t = req_trimmed_str(step, "to", path)
        return {"mapping": {f: t}}
    raise _schema("rename requires 'from' and 'to' or 'mapping'", f"{path}.mapping")


def norm_limit(step, path):
    if "n" not in step:
        raise _schema("missing required field 'n'", f"{path}.n")
    n = step["n"]
    if isinstance(n, bool) or not isinstance(n, int):
        raise _schema("'n' must be an integer", f"{path}.n")
    if n < 0:
        raise _schema("'n' must be >= 0", f"{path}.n")
    return {"n": n}


MALFORMED_STEP = "MALFORMED_STEP"
OTHERWISE = "otherwise"


def norm_branch(step, path):
    bpath = f"{path}.branches"
    if "branches" not in step:
        raise _schema("missing required field 'branches'", bpath)
    branches = step["branches"]
    if not isinstance(branches, list):
        raise _schema("'branches' must be an array", bpath)
    if not branches:
        raise _schema("'branches' must not be empty", bpath)
    out = []
    for j, b in enumerate(branches):
        p = f"{bpath}[{j}]"
        if not isinstance(b, dict):
            raise _schema("branch must be an object", p)
        item = {}
        if "id" in b:
            if not isinstance(b["id"], str):
                raise _schema("'id' must be a string", f"{p}.id")
            item["id"] = b["id"]
        when = req_trimmed_str(b, "when", p)
        if when != OTHERWISE:
            check_expr(when, f"{p}.when")
        item["when"] = when
        if "steps" not in b:
            raise _schema("missing required field 'steps'", f"{p}.steps")
        if not isinstance(b["steps"], list):
            raise _schema("'steps' must be an array", f"{p}.steps")
        item["steps"] = normalize_steps(b["steps"], f"{p}.steps")
        out.append(item)
    whens = [b["when"] for b in out]
    if whens.count(OTHERWISE) > 1:
        raise EtlError(MALFORMED_STEP, "ETL_ERROR: at most one 'otherwise' branch allowed", bpath)
    if OTHERWISE in whens and whens[-1] != OTHERWISE:
        raise EtlError(MALFORMED_STEP, "ETL_ERROR: 'otherwise' branch must be last", bpath)
    merge = step.get("merge")
    if merge is None:
        merge = {}
    if not isinstance(merge, dict):
        raise _schema("'merge' must be an object", f"{path}.merge")
    strategy = merge.get("strategy", "concat")
    if strategy != "concat":
        raise _schema("merge strategy must be 'concat'", f"{path}.merge.strategy")
    return {"branches": out, "merge": {"strategy": "concat"}}


OPS = {
    "branch": norm_branch,
    "select": norm_select,
    "filter": norm_filter,
    "map": norm_map,
    "rename": norm_rename,
    "limit": norm_limit,
}


# --------------------------------------------------------------------------
# Request handling
# --------------------------------------------------------------------------

def normalize_steps(steps, base):
    return [normalize_step(s, f"{base}[{i}]") for i, s in enumerate(steps)]


def normalize_step(step, path):
    if not isinstance(step, dict):
        raise _schema("step must be an object", path)
    if "op" not in step:
        raise _schema("missing required field 'op'", f"{path}.op")
    if not isinstance(step["op"], str):
        raise _schema("'op' must be a string", f"{path}.op")
    op = step["op"].strip().lower()
    if op not in OPS:
        raise EtlError(UNKNOWN_OP, f"ETL_ERROR: unsupported op '{op}'", f"{path}.op")
    fields = OPS[op](step, path)
    out = {"op": op}
    for k in sorted(fields):
        out[k] = fields[k]
    return out


def validate_request(req):
    if not isinstance(req, dict):
        raise _schema("request must be a JSON object", "")
    pipeline = req.get("pipeline")
    if not isinstance(pipeline, dict):
        raise _schema("'pipeline' must be an object", "pipeline")
    steps = pipeline.get("steps")
    if not isinstance(steps, list):
        raise _schema("'steps' must be an array", "pipeline.steps")
    if "dataset" not in req:
        raise _schema("missing required field 'dataset'", "dataset")
    ds = req["dataset"]
    if not isinstance(ds, list):
        raise _schema("'dataset' must be an array", "dataset")
    for i, row in enumerate(ds):
        if not isinstance(row, dict):
            raise _schema("dataset rows must be objects", f"dataset[{i}]")
    return normalize_steps(steps, "pipeline.steps"), ds


# --------------------------------------------------------------------------
# Execution
# --------------------------------------------------------------------------

def _missing(col, path):
    return EtlError(MISSING_COLUMN, f"ETL_ERROR: column '{col}' not found in row", path)


def exec_select(step, rows, path):
    cols = step["columns"]
    out = []
    for row in rows:
        for j, c in enumerate(cols):
            if c not in row:
                raise _missing(c, f"{path}.columns[{j}]")
        out.append({c: row[c] for c in cols})
    return out


def exec_filter(step, rows, path):
    ast = parse_expr(step["where"], f"{path}.where")
    return [r for r in rows if _truthy(evaluate(ast, r))]


def exec_map(step, rows, path):
    ast = parse_expr(step["expr"], f"{path}.expr")
    out = []
    for row in rows:
        new = dict(row)
        new[step["as"]] = _clean(evaluate(ast, row))
        out.append(new)
    return out


def exec_rename(step, rows, path):
    mapping = step["mapping"]
    out = []
    for row in rows:
        cur = dict(row)
        for src, dst in mapping.items():
            if src not in cur:
                raise _missing(src, f"{path}.mapping.{src}")
            if src == dst:
                continue
            renamed = {}
            for k, v in cur.items():
                if k == src:
                    renamed[dst] = v
                elif k != dst:
                    renamed[k] = v
            cur = renamed
        out.append(cur)
    return out


def exec_limit(step, rows, path):
    return rows[:step["n"]]


def exec_branch(step, rows, path):
    branches = step["branches"]
    asts = [None if b["when"] == OTHERWISE else
            parse_expr(b["when"], f"{path}.branches[{j}].when")
            for j, b in enumerate(branches)]
    buckets = [[] for _ in branches]
    for row in rows:
        for j, ast in enumerate(asts):
            if ast is None or _truthy(evaluate(ast, row)):
                buckets[j].append(row)
                break
    out = []
    for j, b in enumerate(branches):
        out.extend(execute(b["steps"], buckets[j], f"{path}.branches[{j}].steps"))
    return out


EXECUTORS = {
    "branch": exec_branch,
    "select": exec_select,
    "filter": exec_filter,
    "map": exec_map,
    "rename": exec_rename,
    "limit": exec_limit,
}


def execute(steps, dataset, base="pipeline.steps"):
    rows = dataset
    for i, step in enumerate(steps):
        path = f"{base}[{i}]"
        try:
            rows = EXECUTORS[step["op"]](step, rows, path)
        except EtlError:
            raise
        except Exception as e:
            raise EtlError("EXECUTION_FAILED", f"ETL_ERROR: {e}", path)
    return rows


def process(req, run=False):
    steps, ds = validate_request(req)
    if not run:
        return {"status": "ok", "normalized": {"steps": steps}}
    data = execute(steps, ds)
    return {"status": "ok", "data": data,
            "metrics": {"rows_in": len(ds), "rows_out": len(data)}}


def _parse_flag(argv):
    """--execute, --execute=true|false, or --execute true|false."""
    run = False
    for i, a in enumerate(argv):
        if a == "--execute":
            nxt = argv[i + 1].lower() if i + 1 < len(argv) else ""
            run = nxt != "false"
        elif a.startswith("--execute="):
            run = a.split("=", 1)[1].lower() not in ("false", "0", "no", "")
    return run


def main():
    try:
        req = json.loads(sys.stdin.read())
        resp = process(req, _parse_flag(sys.argv[1:]))
        code = 0
    except json.JSONDecodeError as e:
        resp = {"status": "error", "error_code": SCHEMA,
                "message": f"ETL_ERROR: invalid JSON: {e.msg}", "path": ""}
        code = 1
    except EtlError as e:
        resp = {"status": "error", "error_code": e.code,
                "message": e.message, "path": e.path}
        code = 1
    sys.stdout.write(json.dumps(resp, ensure_ascii=False))
    sys.stdout.write("\n")
    return code


if __name__ == "__main__":
    sys.exit(main())
