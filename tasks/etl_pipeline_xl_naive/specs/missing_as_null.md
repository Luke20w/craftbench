# Missing Columns as Null

Several of our sources leave a key out of a record when its value is empty, instead of sending `null`. Every
pipeline that touches such a column stops with `MISSING_COLUMN` on the first record that lacks it, so people
end up putting `ensure` steps in front of everything. We want a switch on the request that says "a missing
column is just a null".

## Acceptance details

A request may have a top-level `options` object. When present it must be an object (otherwise
`SCHEMA_VALIDATION_FAILED` at `options`); its key `missing_as_null`, when present, must be `true` or `false`
(otherwise `SCHEMA_VALIDATION_FAILED` at `options.missing_as_null`). Other keys of `options` are ignored.
These problems are reported after any problem with `pipeline`, `pipeline.steps`, `dataset` or a dataset row,
and before any problem in the steps, with and without `--execute`.

Without `options`, or with `missing_as_null` absent or `false`, everything is exactly as before.

With `"missing_as_null": true`:

* Wherever a step would fail with `MISSING_COLUMN` because a row doesn't have a column, it instead goes on
  exactly as if that row had the column, holding `null`. What the step then does follows from its existing
  rules for a `null` value.
* The column is then part of that row like any other: it stays in the row's output as `null` (or whatever
  the step turns it into) unless the step removes it.
* This applies to every operation, wherever the step appears (top level or inside `branch` branches at any
  depth). `MISSING_COLUMN` never happens with the option on.
* Steps that already accept a missing column behave exactly as before; nothing is added to their rows.
* Everything else is unchanged: validation, normalization, and `EXECUTION_FAILED` errors (for example from
  a value of the wrong type in another row).

## Example

*Input* (with `--execute`)
```json
{
  "options": {"missing_as_null": true},
  "pipeline": {"steps": [
    {"op": "concat", "as": "name", "columns": ["first", "last"], "sep": " "},
    {"op": "select", "columns": ["id", "name", "last"]}
  ]},
  "dataset": [
    {"id": 1, "first": "Ada", "last": "Lovelace"},
    {"id": 2, "first": "Plato"}
  ]
}
```

*Output*
```json
{
  "status": "ok",
  "data": [
    {"id": 1, "name": "Ada Lovelace", "last": "Lovelace"},
    {"id": 2, "name": "Plato ", "last": null}
  ],
  "metrics": {"rows_in": 2, "rows_out": 2}
}
```
