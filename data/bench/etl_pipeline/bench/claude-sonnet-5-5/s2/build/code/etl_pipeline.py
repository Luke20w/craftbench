#!/usr/bin/env python3
"""ETL pipeline CLI: reads a JSON request on stdin, validates and normalizes
the pipeline, and writes a JSON response on stdout (exit 0 ok, 1 error)."""
import json
import re
import sys


class EtlError(Exception):
    def __init__(self, code, message, path):
        super().__init__(message)
        self.code = code
        self.message = message
        self.path = path


def schema_error(message, path):
    return EtlError("SCHEMA_VALIDATION_FAILED", message, path)


# --------------------------------------------------------------------------
# Expressions: tokenizer + recursive-descent parser producing a small AST,
# and an evaluator. AST nodes are tuples:
#   ("lit", value) ("id", name) ("un", op, node) ("bin", op, left, right)
# --------------------------------------------------------------------------

_TOKEN_RE = re.compile(
    r"""\s*(?:
        (?P<num>\d+(?:\.\d*)?|\.\d+)
      | (?P<str>"[^"]*"|'[^']*')
      | (?P<id>[A-Za-z_][A-Za-z0-9_.]*)
      | (?P<opchars>[*/<>=!&|^%~?:@#$\\]+|[-+()])
    )""",
    re.VERBOSE,
)
_KEYWORDS = {"and": "&&", "or": "||", "not": "!"}
_LITERALS = {"true": True, "false": False, "null": None}
_KNOWN_OPS = ("<=", ">=", "==", "!=", "&&", "||", "*", "/", "<", ">", "!")


def _split_ops(run):
    """Split a run of operator characters into known operators, or raise."""
    parts = []
    pos = 0
    while pos < len(run):
        for op in _KNOWN_OPS:
            if run.startswith(op, pos):
                parts.append(op)
                pos += len(op)
                break
        else:
            raise ValueError("unsupported operator '%s'" % run)
    # Only a trailing unary '!' may directly follow another operator.
    if len(parts) > 1 and any(p != "!" for p in parts[1:]) or "!" in parts[:-1] and len(parts) > 1 and parts[0] != "!":
        raise ValueError("unsupported operator '%s'" % run)
    return parts


def _tokenize(text):
    tokens = []
    pos = 0
    text = text.rstrip()
    while pos < len(text):
        m = _TOKEN_RE.match(text, pos)
        if not m or m.end() == pos:
            raise ValueError("unexpected character %r" % text[pos:].lstrip()[:1])
        pos = m.end()
        kind = m.lastgroup
        value = m.group(kind)
        if kind == "id" and value.lower() in _KEYWORDS:
            tokens.append(("op", _KEYWORDS[value.lower()]))
        elif kind == "opchars":
            for op in ([value] if value in "-+()" else _split_ops(value)):
                tokens.append(("op", op))
        elif kind == "str":
            tokens.append(("str", value[1:-1]))
        elif kind == "num":
            tokens.append(("num", float(value) if "." in value else int(value)))
        else:
            tokens.append((kind, value))
    return tokens


class _Parser:
    def __init__(self, tokens):
        self.tokens = tokens
        self.i = 0

    def peek(self):
        return self.tokens[self.i] if self.i < len(self.tokens) else (None, None)

    def take(self):
        tok = self.peek()
        self.i += 1
        return tok

    def at_op(self, ops):
        kind, value = self.peek()
        return kind == "op" and value in ops

    def parse(self):
        node = self.binary(0)
        if self.i < len(self.tokens):
            raise ValueError("unexpected token %r" % (self.peek()[1],))
        return node

    _LEVELS = (("||",), ("&&",), ("<", "<=", ">", ">=", "==", "!="), ("+", "-"), ("*", "/"))

    def binary(self, level):
        if level == len(self._LEVELS):
            return self.unary()
        node = self.binary(level + 1)
        while self.at_op(self._LEVELS[level]):
            op = self.take()[1]
            node = ("bin", op, node, self.binary(level + 1))
        return node

    def unary(self):
        if self.at_op(("!", "-", "+")):
            op = self.take()[1]
            return ("un", op, self.unary())
        return self.atom()

    def atom(self):
        kind, value = self.take()
        if kind in ("num", "str"):
            return ("lit", value)
        if kind == "id":
            if value in _LITERALS:
                return ("lit", _LITERALS[value])
            return ("id", value)
        if (kind, value) == ("op", "("):
            node = self.binary(0)
            if self.take() != ("op", ")"):
                raise ValueError("expected ')'")
            return node
        raise ValueError("unexpected %s" % ("end of expression" if kind is None else repr(value)))


def parse_expression(text, path):
    try:
        return _Parser(_tokenize(text)).parse()
    except ValueError as exc:
        msg = str(exc)
        if not msg.startswith("unsupported operator"):
            msg = "invalid expression: " + msg
        raise EtlError("BAD_EXPR", msg, path)


def _is_num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _truthy(v):
    return v is not None and bool(v)


def _arith(op, a, b, path):
    if a is None or b is None:
        return None
    if not (_is_num(a) and _is_num(b)):
        raise EtlError("EXECUTION_FAILED", "operator '%s' requires numeric operands" % op, path)
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
    if op in ("==", "!="):
        if _is_num(a) and _is_num(b):
            same = a == b
        elif type(a) is not type(b):
            return False
        else:
            same = a == b
        return same if op == "==" else not same
    if _is_num(a) and _is_num(b) or (isinstance(a, str) and isinstance(b, str)):
        return {"<": a < b, "<=": a <= b, ">": a > b, ">=": a >= b}[op]
    return False


def evaluate(node, row, path):
    kind = node[0]
    if kind == "lit":
        return node[1]
    if kind == "id":
        return row.get(node[1])
    if kind == "un":
        v = evaluate(node[2], row, path)
        if node[1] == "!":
            return not _truthy(v)
        if v is None:
            return None
        if not _is_num(v):
            raise EtlError("EXECUTION_FAILED", "operator '%s' requires a numeric operand" % node[1], path)
        return -v if node[1] == "-" else v
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


def check_expression(text, path):
    parse_expression(text, path)


# --------------------------------------------------------------------------
# Field helpers
# --------------------------------------------------------------------------

def _require(step, field, path):
    if field not in step:
        raise schema_error("missing required field '%s'" % field, path)
    return step[field]


def _trimmed_string(step, field, path):
    value = _require(step, field, path)
    if not isinstance(value, str):
        raise schema_error("'%s' must be a string" % field, path)
    value = value.strip()
    if not value:
        raise schema_error("'%s' must not be empty" % field, path)
    return value


def _expression(step, field, path):
    value = _trimmed_string(step, field, path)
    check_expression(value, path)
    return value


# --------------------------------------------------------------------------
# Per-op normalizers. Each returns a dict of fields (without "op").
# --------------------------------------------------------------------------

OTHERWISE = "otherwise"


def _norm_select(step, base):
    path = base + ".columns"
    cols = _require(step, "columns", path)
    if not isinstance(cols, list) or not all(isinstance(c, str) for c in cols):
        raise schema_error("'columns' must be an array of strings", path)
    return {"columns": list(cols)}


def _norm_filter(step, base):
    return {"where": _expression(step, "where", base + ".where")}


def _norm_map(step, base):
    return {
        "as": _trimmed_string(step, "as", base + ".as"),
        "expr": _expression(step, "expr", base + ".expr"),
    }


def _norm_rename(step, base):
    if "mapping" in step:
        path = base + ".mapping"
        mapping = step["mapping"]
        if not isinstance(mapping, dict) or not all(
            isinstance(v, str) for v in mapping.values()
        ):
            raise schema_error("'mapping' must be an object of strings", path)
        return {"mapping": dict(mapping)}
    if "from" not in step and "to" not in step:
        raise schema_error("rename requires 'from' and 'to', or 'mapping'", base)
    src = _trimmed_string(step, "from", base + ".from")
    dst = _trimmed_string(step, "to", base + ".to")
    return {"mapping": {src: dst}}


def _norm_limit(step, base):
    path = base + ".n"
    n = _require(step, "n", path)
    if isinstance(n, bool) or not isinstance(n, int) or n < 0:
        raise schema_error("'n' must be an integer >= 0", path)
    return {"n": n}


def _norm_branch(step, base):
    path = base + ".branches"
    branches = _require(step, "branches", path)
    if not isinstance(branches, list) or not branches:
        raise schema_error("'branches' must be a non-empty array", path)
    shaped = []
    for j, br in enumerate(branches):
        bpath = "%s[%d]" % (path, j)
        if not isinstance(br, dict):
            raise schema_error("branch must be an object", bpath)
        entry = {}
        if "id" in br:
            if not isinstance(br["id"], str):
                raise schema_error("'id' must be a string", bpath + ".id")
            entry["id"] = br["id"]
        when = _trimmed_string(br, "when", bpath + ".when")
        if when == "otherwise":
            entry["when"] = when
        else:
            check_expression(when, bpath + ".when")
            entry["when"] = when
        shaped.append(entry)
    otherwise = [j for j, e in enumerate(shaped) if e["when"] == OTHERWISE]
    if len(otherwise) > 1 or (otherwise and otherwise[0] != len(shaped) - 1):
        raise EtlError("MALFORMED_STEP",
                       "'otherwise' branch must appear at most once and be last", path)
    merge = step.get("merge", {"strategy": "concat"})
    if not isinstance(merge, dict):
        raise schema_error("'merge' must be an object", base + ".merge")
    strategy = merge.get("strategy", "concat")
    if strategy != "concat":
        raise schema_error("merge strategy must be 'concat'", base + ".merge.strategy")
    for j, (br, entry) in enumerate(zip(branches, shaped)):
        spath = "%s[%d].steps" % (path, j)
        steps = _require(br, "steps", spath)
        if not isinstance(steps, list):
            raise schema_error("'steps' must be an array", spath)
        entry["steps"] = normalize_steps(steps, spath)
    return {"branches": shaped, "merge": {"strategy": "concat"}}


OPS = {
    "branch": _norm_branch,
    "select": _norm_select,
    "filter": _norm_filter,
    "map": _norm_map,
    "rename": _norm_rename,
    "limit": _norm_limit,
}


def normalize_steps(steps, base):
    return [normalize_step(s, "%s[%d]" % (base, i)) for i, s in enumerate(steps)]


def normalize_step(step, base):
    if not isinstance(step, dict):
        raise schema_error("step must be an object", base)
    op = step.get("op")
    if "op" not in step or not isinstance(op, str):
        raise schema_error("step requires string 'op'", base + ".op")
    op = op.strip().lower()
    if op not in OPS:
        raise EtlError("UNKNOWN_OP", "unsupported op '%s'" % op, base + ".op")
    fields = OPS[op](step, base)
    out = {"op": op}
    for key in sorted(fields):
        out[key] = fields[key]
    return out


def normalize_request(req):
    if not isinstance(req, dict):
        raise schema_error("request must be a JSON object", "")
    pipeline = req.get("pipeline")
    if not isinstance(pipeline, dict):
        raise schema_error("'pipeline' must be an object", "pipeline")
    steps = pipeline.get("steps")
    if not isinstance(steps, list):
        raise schema_error("'steps' must be an array", "pipeline.steps")
    if "dataset" not in req or not isinstance(req["dataset"], list):
        raise schema_error("'dataset' must be an array", "dataset")
    for i, row in enumerate(req["dataset"]):
        if not isinstance(row, dict):
            raise schema_error("dataset rows must be objects", "dataset[%d]" % i)
    return {"steps": normalize_steps(steps, "pipeline.steps")}


def _tidy(v):
    if isinstance(v, float) and v.is_integer() and abs(v) < 1e15:
        return int(v)
    return v


def execute_steps(steps, rows, base):
    for i, step in enumerate(steps):
        rows = execute_step(step, rows, "%s[%d]" % (base, i))
    return rows


def _execute_branch(step, rows, base):
    branches = step["branches"]
    trees = []
    for j, br in enumerate(branches):
        when = br["when"]
        path = "%s.branches[%d].when" % (base, j)
        trees.append(None if when == OTHERWISE else parse_expression(when, path))
    buckets = [[] for _ in branches]
    for row in rows:
        for j, tree in enumerate(trees):
            path = "%s.branches[%d].when" % (base, j)
            if tree is None or _truthy(evaluate(tree, row, path)):
                buckets[j].append(row)
                break
    out = []
    for j, (br, bucket) in enumerate(zip(branches, buckets)):
        out.extend(execute_steps(br["steps"], bucket, "%s.branches[%d].steps" % (base, j)))
    return out


def execute_step(step, rows, base):
    op = step["op"]
    if op == "branch":
        return _execute_branch(step, rows, base)
    if op == "select":
        cols = step["columns"]
        out = []
        for row in rows:
            for j, c in enumerate(cols):
                if c not in row:
                    raise EtlError("MISSING_COLUMN", "column '%s' not found in row" % c,
                                   "%s.columns[%d]" % (base, j))
            out.append({c: row[c] for c in cols})
        return out
    if op == "filter":
        path = base + ".where"
        tree = parse_expression(step["where"], path)
        return [r for r in rows if _truthy(evaluate(tree, r, path))]
    if op == "map":
        path = base + ".expr"
        tree = parse_expression(step["expr"], path)
        out = []
        for row in rows:
            new = dict(row)
            new[step["as"]] = _tidy(evaluate(tree, row, path))
            out.append(new)
        return out
    if op == "rename":
        out = []
        for row in rows:
            new = dict(row)
            for src, dst in step["mapping"].items():
                if src not in new:
                    raise EtlError("MISSING_COLUMN", "column '%s' not found in row" % src,
                                   "%s.mapping.%s" % (base, src))
                new[dst] = new.pop(src)
            out.append(new)
        return out
    if op == "limit":
        return rows[: step["n"]]
    raise EtlError("UNKNOWN_OP", "unsupported op '%s'" % op, base + ".op")


def execute(req, normalized):
    rows = req["dataset"]
    rows = execute_steps(normalized["steps"], rows, "pipeline.steps")
    return {
        "status": "ok",
        "data": rows,
        "metrics": {"rows_in": len(req["dataset"]), "rows_out": len(rows)},
    }


def _execute_flag(argv):
    flag = False
    for i, arg in enumerate(argv):
        if arg == "--execute":
            nxt = argv[i + 1].lower() if i + 1 < len(argv) else ""
            flag = nxt != "false"
        elif arg.startswith("--execute="):
            flag = arg.split("=", 1)[1].lower() not in ("false", "0", "")
    return flag


def main():
    try:
        try:
            req = json.loads(sys.stdin.read())
        except ValueError:
            raise schema_error("invalid JSON input", "")
        normalized = normalize_request(req)
        if _execute_flag(sys.argv[1:]):
            result = execute(req, normalized)
        else:
            result = {"status": "ok", "normalized": normalized}
        code = 0
    except EtlError as err:
        result = {
            "status": "error",
            "error_code": err.code,
            "message": "ETL_ERROR: " + err.message,
            "path": err.path,
        }
        code = 1
    json.dump(result, sys.stdout)
    sys.stdout.write("\n")
    return code


if __name__ == "__main__":
    sys.exit(main())
