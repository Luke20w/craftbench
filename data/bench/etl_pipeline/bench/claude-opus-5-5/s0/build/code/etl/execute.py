"""Execute normalized pipeline steps over an in-memory dataset.

Each op has an executor in ``STEP_EXECUTORS`` that receives the normalized step,
its path and the current rows, and returns the new rows. Input rows are never
mutated; every step that changes a row builds a new dict.
"""

from .errors import EXECUTION_FAILED, MISSING_COLUMN, EtlError
from .evaluate import EvalError, evaluate, truthy
from .expr import parse_expr
from .normalize import OTHERWISE


def _missing_column(name, path):
    return EtlError(MISSING_COLUMN, f"column '{name}' not found in row", path)


def _compile(step, field, path):
    """Parse an already-validated expression and return a row -> value function."""
    ast = parse_expr(step[field])
    field_path = f"{path}.{field}"

    def run(row):
        try:
            return evaluate(ast, row)
        except EvalError as exc:
            raise EtlError(EXECUTION_FAILED, str(exc), field_path)

    return run


def _select(step, path, rows):
    columns = step["columns"]
    out = []
    for row in rows:
        for i, col in enumerate(columns):
            if col not in row:
                raise _missing_column(col, f"{path}.columns[{i}]")
        out.append({col: row[col] for col in columns})
    return out


def _filter(step, path, rows):
    predicate = _compile(step, "where", path)
    return [row for row in rows if truthy(predicate(row))]


def _map(step, path, rows):
    compute = _compile(step, "expr", path)
    target = step["as"]
    return [{**row, target: compute(row)} for row in rows]


def _rename_one(row, src, dst):
    """Rename src to dst keeping src's position; an existing dst is overwritten."""
    if src == dst:
        return row
    value = row[src]
    return {(dst if key == src else key): (value if key == src else val)
            for key, val in row.items() if key != dst}


def _rename(step, path, rows):
    out = []
    for row in rows:
        for src, dst in step["mapping"].items():
            if src not in row:
                raise _missing_column(src, f"{path}.mapping.{src}")
            row = _rename_one(row, src, dst)
        out.append(row)
    return out


def _limit(step, path, rows):
    return rows[:step["n"]]


def _branch(step, path, rows):
    """Route each row to the first matching branch, run each branch, then concat."""
    branches = step["branches"]
    predicates = [
        None if branch["when"] == OTHERWISE
        else _compile(branch, "when", f"{path}.branches[{j}]")
        for j, branch in enumerate(branches)
    ]
    routed = [[] for _ in branches]
    for row in rows:
        for j, predicate in enumerate(predicates):
            if predicate is None or truthy(predicate(row)):
                routed[j].append(row)
                break
    out = []
    for j, branch in enumerate(branches):
        out.extend(run_steps(branch["steps"], routed[j], f"{path}.branches[{j}].steps"))
    return out


STEP_EXECUTORS = {
    "select": _select,
    "filter": _filter,
    "map": _map,
    "rename": _rename,
    "limit": _limit,
    "branch": _branch,
}


def run_steps(steps, rows, path):
    for i, step in enumerate(steps):
        rows = STEP_EXECUTORS[step["op"]](step, f"{path}[{i}]", rows)
    return rows


def execute(steps, dataset, path="pipeline.steps"):
    """Run normalized steps; returns the ``data``/``metrics`` part of the response."""
    rows = run_steps(steps, list(dataset), path)
    return {"data": rows, "metrics": {"rows_in": len(dataset), "rows_out": len(rows)}}
