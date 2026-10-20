"""ETL pipeline CLI: reads a JSON request on stdin, writes a JSON response on stdout.

Usage: etl_pipeline.py [--execute[=true|false]]

Without --execute the pipeline is validated and returned in normalized form;
with it the pipeline is run over the dataset and the transformed rows are
returned along with metrics.

Exit code 0 on success, 1 on error (including usage errors).
"""

import json
import sys

import expr

SCHEMA = "SCHEMA_VALIDATION_FAILED"
UNKNOWN_OP = "UNKNOWN_OP"
MISSING_COLUMN = "MISSING_COLUMN"
BAD_EXPR = "BAD_EXPR"
EXECUTION_FAILED = "EXECUTION_FAILED"
MALFORMED_STEP = "MALFORMED_STEP"

OTHERWISE = "otherwise"
MERGE_STRATEGIES = ("concat",)


class EtlError(Exception):
    def __init__(self, code, message, path):
        super().__init__(message)
        self.code = code
        self.message = message
        self.path = path

    def to_response(self):
        return {
            "status": "error",
            "error_code": self.code,
            "message": f"ETL_ERROR: {self.message}",
            "path": self.path,
        }


# ---------------------------------------------------------------------------
# Field helpers
# ---------------------------------------------------------------------------

def _require(step, field, path):
    if field not in step:
        raise EtlError(SCHEMA, f"missing required field '{field}'", f"{path}.{field}")
    return step[field]


def _trimmed_string(step, field, path):
    """Required string field, trimmed; empty/whitespace-only is invalid."""
    value = _require(step, field, path)
    if not isinstance(value, str):
        raise EtlError(SCHEMA, f"'{field}' must be a string", f"{path}.{field}")
    value = value.strip()
    if not value:
        raise EtlError(SCHEMA, f"'{field}' must not be empty", f"{path}.{field}")
    return value


def _exact_name(value, path, what):
    """A column name / mapping key or value: preserved exactly, but not blank."""
    if not isinstance(value, str):
        raise EtlError(SCHEMA, f"{what} must be a string", path)
    if not value.strip():
        raise EtlError(SCHEMA, f"{what} must not be empty", path)
    return value


def _expression(step, field, path):
    src = _trimmed_string(step, field, path)
    try:
        ast = expr.parse(src)
    except expr.ExprError as e:
        raise EtlError(BAD_EXPR, str(e), f"{path}.{field}")
    return src, ast


# ---------------------------------------------------------------------------
# Per-op normalizers. Each returns (normalized_fields, info) where info is
# op-specific data used by later semantic checks (e.g. parsed ASTs).
# ---------------------------------------------------------------------------

def _norm_select(step, path):
    columns = _require(step, "columns", path)
    if not isinstance(columns, list):
        raise EtlError(SCHEMA, "'columns' must be an array of strings", f"{path}.columns")
    if not columns:
        raise EtlError(SCHEMA, "'columns' must not be empty", f"{path}.columns")
    for i, col in enumerate(columns):
        _exact_name(col, f"{path}.columns[{i}]", "column name")
    return {"columns": list(columns)}, None


def _norm_filter(step, path):
    where, ast = _expression(step, "where", path)
    return {"where": where}, ast


def _norm_map(step, path):
    as_ = _trimmed_string(step, "as", path)
    src, ast = _expression(step, "expr", path)
    return {"as": as_, "expr": src}, ast


def _norm_rename(step, path):
    has_pair = "from" in step or "to" in step
    has_mapping = "mapping" in step
    if has_pair and has_mapping:
        raise EtlError(SCHEMA, "rename takes either 'from'/'to' or 'mapping', not both", path)
    if has_pair:
        src = _trimmed_string(step, "from", path)
        dst = _trimmed_string(step, "to", path)
        return {"mapping": {src: dst}}, None
    if not has_mapping:
        raise EtlError(SCHEMA, "rename requires 'from'/'to' or 'mapping'", f"{path}.mapping")
    mapping = step["mapping"]
    if not isinstance(mapping, dict):
        raise EtlError(SCHEMA, "'mapping' must be an object", f"{path}.mapping")
    if not mapping:
        raise EtlError(SCHEMA, "'mapping' must not be empty", f"{path}.mapping")
    for key, value in mapping.items():
        _exact_name(key, f"{path}.mapping", "mapping key")
        _exact_name(value, f"{path}.mapping.{key}", "mapping value")
    return {"mapping": dict(mapping)}, None


def _norm_limit(step, path):
    n = _require(step, "n", path)
    if isinstance(n, bool) or not isinstance(n, int):
        raise EtlError(SCHEMA, "'n' must be an integer", f"{path}.n")
    if n < 0:
        raise EtlError(SCHEMA, "'n' must be >= 0", f"{path}.n")
    return {"n": n}, None


def _norm_branch(step, path):
    """Normalize a branch step.

    info is a list with one entry per branch: (when_ast, step_infos), where
    when_ast is None for the `otherwise` branch.
    """
    branches = _require(step, "branches", path)
    if not isinstance(branches, list):
        raise EtlError(SCHEMA, "'branches' must be an array", f"{path}.branches")
    if not branches:
        raise EtlError(SCHEMA, "'branches' must not be empty", f"{path}.branches")

    norm_branches, info = [], []
    for j, branch in enumerate(branches):
        bpath = f"{path}.branches[{j}]"
        if not isinstance(branch, dict):
            raise EtlError(SCHEMA, "branch must be an object", bpath)
        norm = {}
        if "id" in branch:
            if not isinstance(branch["id"], str):
                raise EtlError(SCHEMA, "'id' must be a string", f"{bpath}.id")
            norm["id"] = branch["id"]
        when = _trimmed_string(branch, "when", bpath)
        if when == OTHERWISE:
            when_ast = None
        else:
            when, when_ast = _expression(branch, "when", bpath)
        norm["when"] = when

        steps = _require(branch, "steps", bpath)
        if not isinstance(steps, list):
            raise EtlError(SCHEMA, "'steps' must be an array", f"{bpath}.steps")
        norm["steps"], step_infos = normalize_steps(steps, f"{bpath}.steps")
        norm_branches.append(norm)
        info.append((when_ast, step_infos))

    otherwise = [j for j, (ast, _) in enumerate(info) if ast is None]
    if len(otherwise) > 1:
        raise EtlError(MALFORMED_STEP, "at most one 'otherwise' branch is allowed", f"{path}.branches")
    if otherwise and otherwise[0] != len(info) - 1:
        raise EtlError(MALFORMED_STEP, "the 'otherwise' branch must be last", f"{path}.branches")

    merge = step.get("merge", {})
    if not isinstance(merge, dict):
        raise EtlError(SCHEMA, "'merge' must be an object", f"{path}.merge")
    strategy = merge.get("strategy", "concat")
    if not isinstance(strategy, str):
        raise EtlError(SCHEMA, "'strategy' must be a string", f"{path}.merge.strategy")
    strategy = strategy.strip().lower()
    if strategy not in MERGE_STRATEGIES:
        raise EtlError(SCHEMA, f"unsupported merge strategy '{strategy}'", f"{path}.merge.strategy")

    return {"branches": norm_branches, "merge": {"strategy": strategy}}, info


NORMALIZERS = {
    "select": _norm_select,
    "filter": _norm_filter,
    "map": _norm_map,
    "rename": _norm_rename,
    "limit": _norm_limit,
    "branch": _norm_branch,
}


def normalize_step(step, path):
    """Validate one step and return (normalized_step, info)."""
    if not isinstance(step, dict):
        raise EtlError(SCHEMA, "step must be an object", path)
    if "op" not in step:
        raise EtlError(SCHEMA, "missing required field 'op'", f"{path}.op")
    op = step["op"]
    if not isinstance(op, str):
        raise EtlError(SCHEMA, "'op' must be a string", f"{path}.op")
    op = op.strip().lower()
    if not op:
        raise EtlError(SCHEMA, "'op' must not be empty", f"{path}.op")
    if op not in NORMALIZERS:
        raise EtlError(UNKNOWN_OP, f"unsupported op '{op}'", f"{path}.op")
    fields, info = NORMALIZERS[op](step, path)
    normalized = {"op": op}
    for key in sorted(fields):
        normalized[key] = fields[key]
    return normalized, info


def normalize_steps(steps, path):
    """Normalize a list of steps found at `path`; returns (normalized, infos)."""
    normalized, infos = [], []
    for i, step in enumerate(steps):
        norm, info = normalize_step(step, f"{path}[{i}]")
        normalized.append(norm)
        infos.append(info)
    return normalized, infos


# ---------------------------------------------------------------------------
# Column tracking: when the dataset has rows, check that every column a step
# references exists at that point in the pipeline.
# ---------------------------------------------------------------------------

def check_columns(steps, infos, dataset):
    if not dataset:
        return
    available = set()
    for row in dataset:
        available.update(row.keys())
    _check_steps(steps, infos, available, "pipeline.steps")


def _check_steps(steps, infos, available, prefix):
    """Check steps against the `available` columns; return columns available after."""
    for i, (step, ast) in enumerate(zip(steps, infos)):
        path = f"{prefix}[{i}]"
        op = step["op"]
        if op == "select":
            for j, col in enumerate(step["columns"]):
                if col not in available:
                    raise EtlError(MISSING_COLUMN, f"unknown column '{col}'", f"{path}.columns[{j}]")
            available = set(step["columns"])
        elif op in ("filter", "map"):
            field = "where" if op == "filter" else "expr"
            for col in sorted(expr.columns_referenced(ast)):
                if col not in available:
                    raise EtlError(MISSING_COLUMN, f"unknown column '{col}'", f"{path}.{field}")
            if op == "map":
                available.add(step["as"])
        elif op == "rename":
            mapping = step["mapping"]
            for src in mapping:
                if src not in available:
                    raise EtlError(MISSING_COLUMN, f"unknown column '{src}'", f"{path}.mapping")
            available = {mapping.get(c, c) for c in available}
        elif op == "branch":
            # Rows leaving a branch step may come from any branch, so the
            # columns available afterwards are the union of every branch's.
            after = set()
            for j, (when_ast, step_infos) in enumerate(ast):
                bpath = f"{path}.branches[{j}]"
                if when_ast is not None:
                    for col in sorted(expr.columns_referenced(when_ast)):
                        if col not in available:
                            raise EtlError(MISSING_COLUMN, f"unknown column '{col}'", f"{bpath}.when")
                after |= _check_steps(step["branches"][j]["steps"], step_infos,
                                      set(available), f"{bpath}.steps")
            available = after
    return available


# ---------------------------------------------------------------------------
# Execution: run normalized steps over the dataset. Each executor takes the
# current rows and returns new rows; input rows are never mutated.
# ---------------------------------------------------------------------------

def _exec_select(step, ast, rows, path):
    out = []
    for row in rows:
        new = {}
        for j, col in enumerate(step["columns"]):
            if col not in row:
                raise EtlError(MISSING_COLUMN, f"column '{col}' not found in row", f"{path}.columns[{j}]")
            new[col] = row[col]
        out.append(new)
    return out


def _eval(ast, row, path):
    try:
        return expr.evaluate(ast, row)
    except expr.EvalError as e:
        raise EtlError(EXECUTION_FAILED, str(e), path)


def _exec_filter(step, ast, rows, path):
    return [row for row in rows if expr.truthy(_eval(ast, row, f"{path}.where"))]


def _exec_map(step, ast, rows, path):
    out = []
    for row in rows:
        new = dict(row)
        new[step["as"]] = _eval(ast, row, f"{path}.expr")
        out.append(new)
    return out


def _rename_one(row, src, dst):
    """Rename src to dst in place of src's position, replacing any existing dst."""
    if src == dst:
        return row
    out = {}
    for key, value in row.items():
        if key == src:
            out[dst] = value
        elif key != dst:
            out[key] = value
    return out


def _exec_rename(step, ast, rows, path):
    out = []
    for row in rows:
        for src, dst in step["mapping"].items():
            if src not in row:
                raise EtlError(MISSING_COLUMN, f"column '{src}' not found in row", f"{path}.mapping.{src}")
            row = _rename_one(row, src, dst)
        out.append(row)
    return out


def _exec_limit(step, ast, rows, path):
    return rows[:step["n"]]


def _exec_branch(step, info, rows, path):
    """Route each row to the first matching branch, run each branch, concat."""
    routed = [[] for _ in info]
    for row in rows:
        for j, (when_ast, _) in enumerate(info):
            if when_ast is None or expr.truthy(_eval(when_ast, row, f"{path}.branches[{j}].when")):
                routed[j].append(row)
                break
    out = []
    for j, (branch, (_, step_infos)) in enumerate(zip(step["branches"], info)):
        out.extend(run_steps(branch["steps"], step_infos, routed[j], f"{path}.branches[{j}].steps"))
    return out


EXECUTORS = {
    "select": _exec_select,
    "filter": _exec_filter,
    "map": _exec_map,
    "rename": _exec_rename,
    "limit": _exec_limit,
    "branch": _exec_branch,
}


def run_steps(steps, infos, rows, prefix):
    for i, (step, info) in enumerate(zip(steps, infos)):
        rows = EXECUTORS[step["op"]](step, info, rows, f"{prefix}[{i}]")
    return rows


def execute(steps, infos, dataset):
    return run_steps(steps, infos, dataset, "pipeline.steps")


# ---------------------------------------------------------------------------
# Request handling
# ---------------------------------------------------------------------------

def process(request, execute_pipeline=False):
    if not isinstance(request, dict):
        raise EtlError(SCHEMA, "request must be a JSON object", "")
    if "pipeline" not in request:
        raise EtlError(SCHEMA, "missing required field 'pipeline'", "pipeline")
    pipeline = request["pipeline"]
    if not isinstance(pipeline, dict):
        raise EtlError(SCHEMA, "'pipeline' must be an object", "pipeline")
    if "steps" not in pipeline:
        raise EtlError(SCHEMA, "missing required field 'steps'", "pipeline.steps")
    steps = pipeline["steps"]
    if not isinstance(steps, list):
        raise EtlError(SCHEMA, "'steps' must be an array", "pipeline.steps")
    if "dataset" not in request:
        raise EtlError(SCHEMA, "missing required field 'dataset'", "dataset")
    dataset = request["dataset"]
    if not isinstance(dataset, list):
        raise EtlError(SCHEMA, "'dataset' must be an array", "dataset")
    for i, row in enumerate(dataset):
        if not isinstance(row, dict):
            raise EtlError(SCHEMA, "dataset rows must be objects", f"dataset[{i}]")

    normalized, infos = normalize_steps(steps, "pipeline.steps")

    if execute_pipeline:
        data = execute(normalized, infos, dataset)
        return {
            "status": "ok",
            "data": data,
            "metrics": {"rows_in": len(dataset), "rows_out": len(data)},
        }

    check_columns(normalized, infos, dataset)
    return {"status": "ok", "normalized": {"steps": normalized}}


_BOOL_ARGS = {"true": True, "1": True, "yes": True, "false": False, "0": False, "no": False}


def parse_args(argv):
    """Return the value of --execute. Accepts `--execute`, `--execute=V` and `--execute V`."""
    execute_pipeline = False
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg == "--execute":
            if i + 1 < len(argv) and argv[i + 1].lower() in _BOOL_ARGS:
                i += 1
                execute_pipeline = _BOOL_ARGS[argv[i].lower()]
            else:
                execute_pipeline = True
        elif arg.startswith("--execute="):
            value = arg.split("=", 1)[1].lower()
            if value not in _BOOL_ARGS:
                raise EtlError(SCHEMA, f"invalid value for --execute: '{value}'", "")
            execute_pipeline = _BOOL_ARGS[value]
        else:
            raise EtlError(SCHEMA, f"unknown argument '{arg}'", "")
        i += 1
    return execute_pipeline


def main(argv=None):
    try:
        execute_pipeline = parse_args(sys.argv[1:] if argv is None else argv)
        try:
            request = json.loads(sys.stdin.read())
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            raise EtlError(SCHEMA, f"invalid JSON: {e}", "")
        response = process(request, execute_pipeline)
        code = 0
    except EtlError as e:
        response = e.to_response()
        code = 1
    sys.stdout.write(json.dumps(response) + "\n")
    return code


if __name__ == "__main__":
    sys.exit(main())
