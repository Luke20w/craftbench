# Column Names in Any Case

Our sources don't agree on capitalisation: the same column arrives as `price` from one system, `Price` from
another and `PRICE` from a third. A pipeline written for one of them breaks or silently does nothing on the
others. We want a switch on the request that makes column names case-insensitive everywhere.

## Acceptance details

A request may have a top-level `options` object. When present it must be an object (otherwise
`SCHEMA_VALIDATION_FAILED` at `options`); its key `ignore_case_columns`, when present, must be `true` or
`false` (otherwise `SCHEMA_VALIDATION_FAILED` at `options.ignore_case_columns`). Other keys of `options` are
ignored. These problems are reported after any problem with `pipeline`, `pipeline.steps`, `dataset` or a
dataset row, and before any problem in the steps, with and without `--execute`.

Without `options`, or with `ignore_case_columns` absent or `false`, everything is exactly as before.

With `"ignore_case_columns": true`:

* Every column name a step uses, in any of its fields and in its expressions, refers to the row's column
  whose name is the same ignoring case. If a row has several such columns, the one spelled exactly the same
  is used, otherwise the first of them in the row.
* A step works on the column it found under the row's spelling: it reads it, overwrites it, changes it in
  place, moves it or removes it, and the name keeps the row's spelling. That includes rows and objects the
  step builds from it (`select`, `nest`, and the `by` columns of `group_count` and `summarize`, which take
  the spelling of the group's first row).
* A name that matches no column of the row behaves exactly as before: a column that must exist is still
  `MISSING_COLUMN`, a missing value is still `null`, and a column the step creates gets the name as written
  in the step.
* `rename` gives the column the new name exactly as written in the step and replaces any other column whose
  name matches the new name ignoring case. `prefix` puts the prefix in front of the row's spelling.
* Names that come from the data rather than from the step (the keys `unnest` spreads out) and whole-row
  comparisons (`distinct` without `columns`) are exact, as before.
* This applies to every operation, wherever the step appears (top level or inside `branch` branches at any
  depth). Validation, normalization (names keep the spelling they were written with) and error paths are
  unchanged.

## Example

*Input* (with `--execute`)
```json
{
  "options": {"ignore_case_columns": true},
  "pipeline": {"steps": [
    {"op": "map", "as": "Total", "expr": "PRICE * Qty"},
    {"op": "select", "columns": ["ID", "total"]}
  ]},
  "dataset": [{"id": 1, "price": 2, "qty": 3}]
}
```

*Output*
```json
{
  "status": "ok",
  "data": [{"id": 1, "Total": 6}],
  "metrics": {"rows_in": 1, "rows_out": 1}
}
```
