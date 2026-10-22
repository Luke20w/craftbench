# Report Every Broken Step

Our users write long pipelines by hand. When a pipeline has several mistakes they fix one, run it again,
hit the next one, and so on, sometimes ten times. We'd like one run to tell them about all the broken
steps at once.

## Acceptance details

Add a `--all-errors` flag. Without it, every response is exactly as before.

With the flag, a response for a **validation error** (any error reported before rows are processed:
`SCHEMA_VALIDATION_FAILED`, `UNKNOWN_OP`, `BAD_EXPR`, `MALFORMED_STEP`, with or without `--execute`) also
has an `errors` array. Everything else in the response is unchanged: `status`, and the top-level
`error_code`, `path` and `message` are exactly what they are without the flag (that problem is always
one of the entries).

* Each entry is `{"error_code": ..., "path": ...}`, using the same codes and paths as the top-level fields.
* There is one entry for each step that has a problem, holding that step's **first** problem (the one that
  would be reported if it were the only broken step). Steps without problems have no entry.
* Every step is checked, at any depth: top-level steps, and steps inside `branch` branches, also when the
  `branch` step itself has a problem.
* A `branch` step's own problem is the first problem in its own fields (`branches`, each branch's `when`,
  `steps` and `id`, and `merge`), not counting problems of the steps inside it. It and the problems of its
  inner steps are separate entries.
* Entries are in the order the steps start: steps in order, and a `branch` step's own entry before the
  entries of the steps inside it, branch by branch (recursively for nested branches).
* If the request itself is broken (not JSON, or `pipeline`, `pipeline.steps`, `dataset` or a dataset row
  is missing or of the wrong type), `errors` holds just that one problem.

Success responses and execution errors (`MISSING_COLUMN`, `EXECUTION_FAILED`) have no `errors` key.

## Example

*Input* (with `--all-errors`)
```json
{
  "pipeline": {"steps": [
    {"op": "select", "columns": "id"},
    {"op": "limit", "n": 5},
    {"op": "branch", "branches": [
      {"when": "price >", "steps": [{"op": "fill", "column": "x"}, {"op": "explode"}]}
    ]},
    {"op": "trim"}
  ]},
  "dataset": []
}
```

*Output*
```json
{
  "status": "error",
  "error_code": "SCHEMA_VALIDATION_FAILED",
  "message": "ETL_ERROR: 'columns' must be an array",
  "path": "pipeline.steps[0].columns",
  "errors": [
    {"error_code": "SCHEMA_VALIDATION_FAILED", "path": "pipeline.steps[0].columns"},
    {"error_code": "BAD_EXPR", "path": "pipeline.steps[2].branches[0].when"},
    {"error_code": "SCHEMA_VALIDATION_FAILED", "path": "pipeline.steps[2].branches[0].steps[0].value"},
    {"error_code": "SCHEMA_VALIDATION_FAILED", "path": "pipeline.steps[2].branches[0].steps[1].column"},
    {"error_code": "UNKNOWN_OP", "path": "pipeline.steps[3].op"}
  ]
}
```
