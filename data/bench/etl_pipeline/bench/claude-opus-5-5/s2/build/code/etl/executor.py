"""Run normalized pipeline steps over an in-memory dataset.

Steps run one at a time over the whole dataset, so the first failing step
(and, within it, the first failing row) is the error reported. Each op has a
runner in STEP_RUNNERS taking (step, raw_step, rows, path) and returning the
new list of rows; `raw_step` is the step as given in the request, used to
point error paths at the field the user actually wrote.
"""

from . import expr
from .errors import EXECUTION_FAILED, MISSING_COLUMN, EtlError
from .evaluator import EvalError, evaluate, truthy
from .schema import OTHERWISE


def _missing_column(name, path):
    return EtlError(MISSING_COLUMN, f"column '{name}' not found in row", path)


def _evaluator(step, field, path):
    """Return a function row -> value for the expression in step[field]."""
    tree = expr.parse(step[field])  # already validated during normalization

    def run(row):
        try:
            return evaluate(tree, row)
        except EvalError as exc:
            raise EtlError(EXECUTION_FAILED, str(exc), f"{path}.{field}")

    return run


def _run_select(step, raw_step, rows, path):
    columns = step["columns"]
    out = []
    for row in rows:
        for j, name in enumerate(columns):
            if name not in row:
                raise _missing_column(name, f"{path}.columns[{j}]")
        out.append({name: row[name] for name in columns})
    return out


def _run_filter(step, raw_step, rows, path):
    where = _evaluator(step, "where", path)
    return [row for row in rows if truthy(where(row))]


def _run_map(step, raw_step, rows, path):
    compute = _evaluator(step, "expr", path)
    target = step["as"]
    return [{**row, target: compute(row)} for row in rows]


def _rename_key(row, source, target):
    """Rename in place position-wise; an existing `target` is overwritten."""
    value = row[source]
    out = {}
    for key, current in row.items():
        if key == source:
            out[target] = value
        elif key != target:
            out[key] = current
    return out


def _run_rename(step, raw_step, rows, path):
    def source_path(source):
        if "mapping" in raw_step:
            return f"{path}.mapping.{source}"
        return f"{path}.from"

    out = []
    for row in rows:
        # Entries apply sequentially, so a later entry sees earlier renames.
        for source, target in step["mapping"].items():
            if source not in row:
                raise _missing_column(source, source_path(source))
            if source != target:
                row = _rename_key(row, source, target)
        out.append(row)
    return out


def _run_limit(step, raw_step, rows, path):
    return rows[: step["n"]]


def _run_branch(step, raw_step, rows, path):
    """Route each row to its first matching branch, run, then concat in branch order."""
    branches = step["branches"]
    tests = [
        None if b["when"] == OTHERWISE else _evaluator(b, "when", f"{path}.branches[{j}]")
        for j, b in enumerate(branches)
    ]
    routed = [[] for _ in branches]
    for row in rows:
        for j, test in enumerate(tests):
            if test is None or truthy(test(row)):
                routed[j].append(row)
                break  # unmatched rows (no otherwise branch) are dropped

    out = []
    for j, (branch, raw_branch) in enumerate(zip(branches, raw_step["branches"])):
        out.extend(run_steps(branch["steps"], raw_branch["steps"], routed[j], f"{path}.branches[{j}].steps"))
    return out


STEP_RUNNERS = {
    "select": _run_select,
    "filter": _run_filter,
    "map": _run_map,
    "rename": _run_rename,
    "limit": _run_limit,
    "branch": _run_branch,
}


def run_steps(steps, raw_steps, rows, path):
    """Run `steps` (found at `path`, e.g. "pipeline.steps") over `rows` in order."""
    for i, (step, raw_step) in enumerate(zip(steps, raw_steps)):
        rows = STEP_RUNNERS[step["op"]](step, raw_step, rows, f"{path}[{i}]")
    return rows


def execute(steps, raw_steps, dataset):
    """Run normalized `steps` over `dataset`; return (rows, metrics)."""
    rows = run_steps(steps, raw_steps, [dict(row) for row in dataset], "pipeline.steps")
    return rows, {"rows_in": len(dataset), "rows_out": len(rows)}
