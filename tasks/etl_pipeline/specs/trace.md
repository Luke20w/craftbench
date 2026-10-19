# Execution Trace

Operators debugging pipelines want to see how many rows flowed through every step.

## CLI

Add a `--trace` flag. It only has an effect together with `--execute`:

* `--execute --trace`: the success response gains a top-level `trace` array (described below).
  `status`, `data` and `metrics` are unchanged.
* `--trace` without `--execute`: ignored; output is exactly as before.
* Error responses are unchanged (no `trace` key), with or without `--trace`.

## Trace entries

One entry per executed step:

```json
{"path": "pipeline.steps[1].branches[0].steps[0]", "op": "map", "rows_in": 3, "rows_out": 3}
```

* `path`: the step's path, in the same notation used for error paths (e.g. `pipeline.steps[2]`,
  `pipeline.steps[1].branches[0].steps[0]`).
* `op`: the normalized (lower-case) op name.
* `rows_in` / `rows_out`: number of rows the step received / produced.

**Ordering** — entries are listed in the order steps *start*:

* steps in order;
* a `branch` step's own entry comes first, followed by the entries of the steps inside its
  branches, branch by branch in declaration order (recursively for nested branches);
* the `branch` entry's `rows_in` is the rows reaching the branch step and its `rows_out` is the
  merged row count after all branches.

Steps inside a branch that received no rows still appear, with `rows_in` 0 and `rows_out` 0.
A branch with an empty `steps` list contributes no entries.

## Example

*Input* (run with `--execute --trace`)
```json
{
  "pipeline": {"steps": [
    {"op": "filter", "where": "x > 0"},
    {"op": "branch", "branches": [
      {"when": "x > 5", "steps": [{"op": "map", "as": "big", "expr": "true"}]},
      {"when": "x > 100", "steps": [{"op": "limit", "n": 1}]},
      {"when": "otherwise", "steps": []}
    ]},
    {"op": "limit", "n": 2}
  ]},
  "dataset": [{"x": 1}, {"x": 7}, {"x": -1}, {"x": 3}]
}
```

*Output*
```json
{
  "status": "ok",
  "data": [{"x": 7, "big": true}, {"x": 1}],
  "metrics": {"rows_in": 4, "rows_out": 2},
  "trace": [
    {"path": "pipeline.steps[0]", "op": "filter", "rows_in": 4, "rows_out": 3},
    {"path": "pipeline.steps[1]", "op": "branch", "rows_in": 3, "rows_out": 3},
    {"path": "pipeline.steps[1].branches[0].steps[0]", "op": "map", "rows_in": 1, "rows_out": 1},
    {"path": "pipeline.steps[1].branches[1].steps[0]", "op": "limit", "rows_in": 0, "rows_out": 0},
    {"path": "pipeline.steps[2]", "op": "limit", "rows_in": 3, "rows_out": 2}
  ]
}
```
