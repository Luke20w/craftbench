"""Validation and normalization of the request and its pipeline steps.

Each supported op has a normalizer in ``STEP_NORMALIZERS`` that receives the raw
step dict and its path, and returns the normalized fields (excluding ``op``).
Unknown keys are simply never copied, which drops them. Final key ordering
(``op`` first, then alphabetical) is applied in ``normalize_step``.

``branch`` steps contain nested step lists, which are normalized recursively
with paths like ``pipeline.steps[0].branches[1].steps[2]``.
"""

from .errors import BAD_EXPR, MALFORMED_STEP, SCHEMA_VALIDATION_FAILED, UNKNOWN_OP, EtlError
from .expr import ExprSyntaxError, parse_expr


def _schema_error(message, path):
    return EtlError(SCHEMA_VALIDATION_FAILED, message, path)


def _require(step, field, path):
    if field not in step:
        raise _schema_error(f"missing required field '{field}'", f"{path}.{field}")
    return step[field]


def _trimmed_string(step, field, path):
    """Required string field, trimmed; empty/whitespace-only is invalid."""
    value = _require(step, field, path)
    if not isinstance(value, str):
        raise _schema_error(f"field '{field}' must be a string", f"{path}.{field}")
    value = value.strip()
    if not value:
        raise _schema_error(f"field '{field}' must not be empty", f"{path}.{field}")
    return value


def _expression(step, field, path):
    text = _trimmed_string(step, field, path)
    try:
        parse_expr(text)
    except ExprSyntaxError as exc:
        raise EtlError(BAD_EXPR, str(exc), f"{path}.{field}")
    return text


def _select(step, path):
    columns = _require(step, "columns", path)
    col_path = f"{path}.columns"
    if not isinstance(columns, list):
        raise _schema_error("field 'columns' must be an array of strings", col_path)
    if not columns:
        raise _schema_error("field 'columns' must not be empty", col_path)
    for col in columns:
        if not isinstance(col, str):
            raise _schema_error("field 'columns' must contain only strings", col_path)
        if col == "":
            raise _schema_error("column names must not be empty", col_path)
    return {"columns": list(columns)}


def _filter(step, path):
    return {"where": _expression(step, "where", path)}


def _map(step, path):
    return {"as": _trimmed_string(step, "as", path), "expr": _expression(step, "expr", path)}


def _rename(step, path):
    has_pair = "from" in step or "to" in step
    if has_pair and "mapping" in step:
        raise _schema_error("rename accepts either 'from'/'to' or 'mapping', not both", path)
    if has_pair:
        src = _trimmed_string(step, "from", path)
        dst = _trimmed_string(step, "to", path)
        return {"mapping": {src: dst}}

    mapping = _require(step, "mapping", path)
    map_path = f"{path}.mapping"
    if not isinstance(mapping, dict):
        raise _schema_error("field 'mapping' must be an object", map_path)
    if not mapping:
        raise _schema_error("field 'mapping' must not be empty", map_path)
    for key, value in mapping.items():
        if key == "":
            raise _schema_error("mapping keys must not be empty", map_path)
        if not isinstance(value, str) or value == "":
            raise _schema_error("mapping values must be non-empty strings", map_path)
    return {"mapping": dict(mapping)}


def _limit(step, path):
    n = _require(step, "n", path)
    if isinstance(n, bool) or not isinstance(n, int) or n < 0:
        raise _schema_error("field 'n' must be an integer >= 0", f"{path}.n")
    return {"n": n}


OTHERWISE = "otherwise"
MERGE_STRATEGIES = ("concat",)


def _branch_case(branch, path, seen_otherwise, branches_path):
    if not isinstance(branch, dict):
        raise _schema_error("branch must be an object", path)
    case = {}
    if "id" in branch:
        if not isinstance(branch["id"], str):
            raise _schema_error("field 'id' must be a string", f"{path}.id")
        case["id"] = branch["id"].strip()
    when = _trimmed_string(branch, "when", path)
    if seen_otherwise:
        detail = "at most one" if when == OTHERWISE else "the 'otherwise' branch must be last;"
        raise EtlError(MALFORMED_STEP, f"{detail} 'otherwise' branch allowed", branches_path)
    if when != OTHERWISE:
        when = _expression(branch, "when", path)
    case["when"] = when
    steps = _require(branch, "steps", path)
    if not isinstance(steps, list):
        raise _schema_error("field 'steps' must be an array", f"{path}.steps")
    case["steps"] = normalize_steps(steps, f"{path}.steps")
    return case


def _merge(step, path):
    merge = step.get("merge")
    if merge is None:
        return {"strategy": "concat"}
    merge_path = f"{path}.merge"
    if not isinstance(merge, dict):
        raise _schema_error("field 'merge' must be an object", merge_path)
    if "strategy" not in merge:
        return {"strategy": "concat"}
    strategy = merge["strategy"]
    if not isinstance(strategy, str) or strategy.strip().lower() not in MERGE_STRATEGIES:
        raise _schema_error("merge strategy must be 'concat'", f"{merge_path}.strategy")
    return {"strategy": strategy.strip().lower()}


def _branch(step, path):
    branches = _require(step, "branches", path)
    branches_path = f"{path}.branches"
    if not isinstance(branches, list):
        raise _schema_error("field 'branches' must be an array", branches_path)
    if not branches:
        raise _schema_error("field 'branches' must not be empty", branches_path)
    cases = []
    for j, branch in enumerate(branches):
        seen_otherwise = any(case["when"] == OTHERWISE for case in cases)
        cases.append(_branch_case(branch, f"{branches_path}[{j}]", seen_otherwise, branches_path))
    return {"branches": cases, "merge": _merge(step, path)}


STEP_NORMALIZERS = {
    "select": _select,
    "filter": _filter,
    "map": _map,
    "rename": _rename,
    "limit": _limit,
    "branch": _branch,
}


def normalize_step(step, path):
    if not isinstance(step, dict):
        raise _schema_error("step must be an object", path)
    op = _trimmed_string(step, "op", path).lower()
    normalizer = STEP_NORMALIZERS.get(op)
    if normalizer is None:
        raise EtlError(UNKNOWN_OP, f"unsupported op '{op}'", f"{path}.op")
    fields = normalizer(step, path)
    return {"op": op, **{key: fields[key] for key in sorted(fields)}}


def normalize_steps(steps, path="pipeline.steps"):
    return [normalize_step(step, f"{path}[{i}]") for i, step in enumerate(steps)]


def validate_request(request):
    """Check the request envelope; returns (steps, dataset) as raw values."""
    if not isinstance(request, dict):
        raise _schema_error("request must be a JSON object", "")
    if "pipeline" not in request:
        raise _schema_error("missing required field 'pipeline'", "pipeline")
    pipeline = request["pipeline"]
    if not isinstance(pipeline, dict):
        raise _schema_error("'pipeline' must be an object", "pipeline")
    if "steps" not in pipeline:
        raise _schema_error("missing required field 'steps'", "pipeline.steps")
    steps = pipeline["steps"]
    if not isinstance(steps, list):
        raise _schema_error("'steps' must be an array", "pipeline.steps")

    if "dataset" not in request:
        raise _schema_error("missing required field 'dataset'", "dataset")
    dataset = request["dataset"]
    if not isinstance(dataset, list):
        raise _schema_error("'dataset' must be an array", "dataset")
    for i, row in enumerate(dataset):
        if not isinstance(row, dict):
            raise _schema_error("dataset rows must be objects", f"dataset[{i}]")
    return steps, dataset
