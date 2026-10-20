"""Validation and normalization of the request and its pipeline steps.

Each op has a normalizer that takes the raw step dict and its path and
returns the normalized fields (excluding "op"). Unknown keys are dropped
simply by never being read. To add an op, write a normalizer and register
it in STEP_NORMALIZERS.
"""

from . import expr
from .errors import BAD_EXPR, MALFORMED_STEP, SCHEMA_VALIDATION_FAILED, UNKNOWN_OP, EtlError

OTHERWISE = "otherwise"


def _schema_error(detail, path):
    return EtlError(SCHEMA_VALIDATION_FAILED, detail, path)


def _is_int(value):
    return isinstance(value, int) and not isinstance(value, bool)


def _require(step, field, path):
    if field not in step:
        raise _schema_error(f"missing required field '{field}'", f"{path}.{field}")
    return step[field]


def _trimmed_string(step, field, path):
    """Required string field, trimmed; empty after trim is invalid."""
    value = _require(step, field, path)
    if not isinstance(value, str):
        raise _schema_error(f"'{field}' must be a string", f"{path}.{field}")
    value = value.strip()
    if not value:
        raise _schema_error(f"'{field}' must not be empty", f"{path}.{field}")
    return value


def _exact_string(value, what, path):
    """String preserved verbatim (column names, mapping entries)."""
    if not isinstance(value, str):
        raise _schema_error(f"{what} must be a string", path)
    if not value.strip():
        raise _schema_error(f"{what} must not be empty", path)
    return value


def _expression(step, field, path):
    text = _trimmed_string(step, field, path)
    try:
        expr.parse(text)
    except expr.ExprSyntaxError as exc:
        raise EtlError(BAD_EXPR, str(exc), f"{path}.{field}")
    return text


def _normalize_select(step, path):
    columns = _require(step, "columns", path)
    cpath = f"{path}.columns"
    if not isinstance(columns, list):
        raise _schema_error("'columns' must be an array of strings", cpath)
    if not columns:
        raise _schema_error("'columns' must not be empty", cpath)
    return {
        "columns": [_exact_string(c, "column name", f"{cpath}[{j}]") for j, c in enumerate(columns)]
    }


def _normalize_filter(step, path):
    return {"where": _expression(step, "where", path)}


def _normalize_map(step, path):
    return {
        "as": _trimmed_string(step, "as", path),
        "expr": _expression(step, "expr", path),
    }


def _normalize_rename(step, path):
    has_pair = "from" in step or "to" in step
    has_mapping = "mapping" in step
    if has_pair and has_mapping:
        raise _schema_error("rename accepts either 'from'/'to' or 'mapping', not both", path)
    if has_pair:
        source = _trimmed_string(step, "from", path)
        target = _trimmed_string(step, "to", path)
        return {"mapping": {source: target}}
    if not has_mapping:
        raise _schema_error("rename requires 'from'/'to' or 'mapping'", f"{path}.mapping")
    mapping = step["mapping"]
    mpath = f"{path}.mapping"
    if not isinstance(mapping, dict):
        raise _schema_error("'mapping' must be an object", mpath)
    if not mapping:
        raise _schema_error("'mapping' must not be empty", mpath)
    for key, value in mapping.items():
        _exact_string(key, "mapping key", mpath)
        _exact_string(value, "mapping value", f"{mpath}.{key}")
    return {"mapping": dict(mapping)}


def _normalize_limit(step, path):
    n = _require(step, "n", path)
    if not _is_int(n):
        raise _schema_error("'n' must be an integer", f"{path}.n")
    if n < 0:
        raise _schema_error("'n' must be >= 0", f"{path}.n")
    return {"n": n}


def _is_otherwise(branch):
    when = branch.get("when") if isinstance(branch, dict) else None
    return isinstance(when, str) and when.strip() == OTHERWISE


def _normalize_branch_entry(branch, path):
    if not isinstance(branch, dict):
        raise _schema_error("branch must be an object", path)
    out = {}
    if "id" in branch:
        out["id"] = _exact_string(branch["id"], "'id'", f"{path}.id")
    out["when"] = OTHERWISE if _is_otherwise(branch) else _expression(branch, "when", path)
    steps = _require(branch, "steps", path)
    if not isinstance(steps, list):
        raise _schema_error("'steps' must be an array", f"{path}.steps")
    out["steps"] = normalize_steps(steps, f"{path}.steps")
    return out


def _normalize_branch(step, path):
    branches = _require(step, "branches", path)
    bpath = f"{path}.branches"
    if not isinstance(branches, list):
        raise _schema_error("'branches' must be an array", bpath)
    if not branches:
        raise _schema_error("'branches' must not be empty", bpath)
    # Structural rules are checked before validating each branch's contents.
    otherwise_at = [j for j, b in enumerate(branches) if _is_otherwise(b)]
    if len(otherwise_at) > 1:
        raise EtlError(MALFORMED_STEP, "at most one 'otherwise' branch is allowed", bpath)
    if otherwise_at and otherwise_at[0] != len(branches) - 1:
        raise EtlError(MALFORMED_STEP, "the 'otherwise' branch must be last", bpath)

    merge = step.get("merge", {})
    mpath = f"{path}.merge"
    if merge is None:
        merge = {}
    if not isinstance(merge, dict):
        raise _schema_error("'merge' must be an object", mpath)
    strategy = merge.get("strategy", "concat")
    if not isinstance(strategy, str) or strategy.strip().lower() != "concat":
        raise _schema_error("'merge.strategy' must be \"concat\"", f"{mpath}.strategy")

    return {
        "branches": [_normalize_branch_entry(b, f"{bpath}[{j}]") for j, b in enumerate(branches)],
        "merge": {"strategy": "concat"},
    }


STEP_NORMALIZERS = {
    "select": _normalize_select,
    "filter": _normalize_filter,
    "map": _normalize_map,
    "rename": _normalize_rename,
    "limit": _normalize_limit,
    "branch": _normalize_branch,
}


def normalize_step(step, path):
    if not isinstance(step, dict):
        raise _schema_error("step must be an object", path)
    op = _trimmed_string(step, "op", path).lower()
    normalizer = STEP_NORMALIZERS.get(op)
    if normalizer is None:
        raise EtlError(UNKNOWN_OP, f"unsupported op '{op}'", f"{path}.op")
    fields = normalizer(step, path)
    return {"op": op, **{k: fields[k] for k in sorted(fields)}}


def normalize_steps(steps, path):
    """Normalize a list of steps found at `path` (e.g. "pipeline.steps")."""
    return [normalize_step(step, f"{path}[{i}]") for i, step in enumerate(steps)]


def parse_request(request):
    """Validate the request; return (normalized_steps, dataset)."""
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

    return normalize_steps(steps, "pipeline.steps"), dataset
