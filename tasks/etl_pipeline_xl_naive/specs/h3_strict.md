# Catch Misspelled Fields

People misspell field names (`colums`, `defualt`, `exprs` as `expr`) and the step silently ignores them, so
the pipeline runs with a default nobody asked for and nobody notices. We want a way to make that an error.

## Acceptance details

Add a `--strict` flag. Without it, unknown keys are still silently dropped, as before.

With `--strict`, an unknown key is a `SCHEMA_VALIDATION_FAILED` error at that key's path, for every
operation, wherever the step appears (top level or inside `branch` branches at any depth). This covers:

* the step object itself: its known keys are `op` and the operation's fields (for `rename`, `from`, `to`
  and `mapping` are all known, whichever form is used), e.g. `pipeline.steps[0].colums`;
* objects inside a step that have their own fields: each `branch` branch (`id`, `when`, `steps`), the
  `branch` step's `merge` (`strategy`) and each `summarize` metric (`as`, `fn`, `column`), e.g.
  `pipeline.steps[1].branches[0].stpes` or `pipeline.steps[0].metrics[2].col`.

Objects that hold data are not covered: the keys of `rename.mapping` and `lookup.table`, and the rows of
`append.rows`.

An object's keys are checked **after** all of its fields: any other problem in the same object is reported
first, and if there are several unknown keys, the first one in the request is reported. (An unknown key in
a branch is therefore found before any problem in a later branch or in `merge`, but after problems in that
branch's own `steps`.)

These are validation errors: they are reported with and without `--execute`, and with `--all-errors` they
are listed like any other problem (as the first problem of their step, when nothing else in the step comes
first).

## Example

*Input* (with `--strict`)
```json
{
  "pipeline": {"steps": [
    {"op": "lookup", "column": "cc", "as": "country", "table": {"NO": "Norway"}, "defualt": "?"}
  ]},
  "dataset": []
}
```

*Output*
```json
{
  "status": "error",
  "error_code": "SCHEMA_VALIDATION_FAILED",
  "message": "ETL_ERROR: unknown field 'defualt'",
  "path": "pipeline.steps[0].defualt"
}
```
