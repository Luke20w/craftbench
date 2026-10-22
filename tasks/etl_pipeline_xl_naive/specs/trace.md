# See where rows go

When a pipeline returns fewer rows than expected, operators can't tell which step dropped them. They want
to see how many rows went into and came out of every step.

## Acceptance details

* New `--trace` flag. With `--execute --trace`, a successful response also has a top-level `trace` array;
  `status`, `data` and `metrics` are unchanged. Without `--execute`, or on errors, output is exactly as
  before (no `trace`).
* One entry per executed step: `{"path": "pipeline.steps[1].branches[0].steps[0]", "op": "map", "rows_in": 3, "rows_out": 3}`.
  `path` uses the same notation as error paths; `op` is the normalized op name.
* Entries are in the order steps start. A `branch` step's own entry comes first (its `rows_in` is the rows
  reaching it, its `rows_out` the merged count), then the entries of the steps inside its branches, branch
  by branch, recursively. Steps in a branch that got no rows still appear with 0 and 0; an empty branch
  adds nothing.

## Example

`filter x > 0` then `limit 2` on 4 rows (3 positive) gives
`[{"path": "pipeline.steps[0]", "op": "filter", "rows_in": 4, "rows_out": 3}, {"path": "pipeline.steps[1]", "op": "limit", "rows_in": 3, "rows_out": 2}]`.
