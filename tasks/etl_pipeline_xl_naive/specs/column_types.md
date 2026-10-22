# Column Types

We know the shape of our datasets up front: `price` is a number, `name` is a string, `tags` is an array.
Still, pipelines that round a string column or upper-case a number only fail when they meet real data, often
hours into a run and sometimes only on the one record that has a value. We want to declare the column types
with the request and have such pipelines rejected before anything runs.

## Acceptance details

A request may have a top-level `schema` object mapping column names to a type: `"number"`, `"string"`,
`"boolean"`, `"array"` or `"object"` (exactly these words; "number" never includes booleans). A `schema`
that isn't an object is a `SCHEMA_VALIDATION_FAILED` error at `schema`; a value that isn't one of the words is
one at `schema.<name>` (the first such entry in the request). These problems are reported after any problem
with `pipeline`, `pipeline.steps`, `dataset` or a dataset row, and before any problem in the steps.

Without `schema`, everything is exactly as before. With it:

* A field that names a column the step looks at must not name a column whose known type the step can't
  handle. A step can't handle a type when every non-`null` value of that type would make it fail with
  `EXECUTION_FAILED` (for example `round` on a string, `text` on a number, `unnest` on an array, `cast` to
  `int` on a boolean). Values that fail only for some values of the type (a string that isn't a number for
  `cast` to `int`) are fine. Column names used inside expressions are not checked.
* A violation is a `TYPE_MISMATCH` error at the path of the field that names the column (`...columns[j]` for
  an array, `...metrics[j].column` for a `summarize` metric).
* Types follow the columns through the pipeline. A column has its declared type from the start until a step
  changes it: once a step may give a column a new value (setting, overwriting, creating or converting it in
  place), deletes it, renames it or moves it into another column, the steps after it don't know its type and
  don't check it. The exception is `cast`: after it, the column's type is what it converts to (`int` and
  `float` give `number`, `string` gives `string`, `bool` gives `boolean`), also for a column not in `schema`.
* A step that may change columns it doesn't name (`unnest`, `prefix` without `columns`) leaves no known types.
  A step that keeps only some columns (`select`, `group_count`, `summarize`) leaves only the types of the
  columns it keeps with their values unchanged.
* Inside a `branch`, each branch's steps start from the types known before the `branch` step. After the
  `branch` step, a column keeps its type only if no step in any of its branches (at any depth) changed it.
* Type problems are checked only when the pipeline has no other validation problem. The first one is
  reported: steps in order, the steps inside a `branch` branch by branch at its position, and within a step
  its fields in the order of the operation's field table.
* This applies with and without `--execute`; with `--execute`, a pipeline with a type problem doesn't run. The
  dataset itself is not checked against `schema`, and nothing else changes.

## Example

*Input*
```json
{
  "schema": {"price": "string", "qty": "number"},
  "pipeline": {"steps": [
    {"op": "round", "column": "qty"},
    {"op": "cast", "column": "price", "to": "float"},
    {"op": "between", "column": "price", "low": 0, "high": 10, "as": "cheap"},
    {"op": "text", "columns": ["qty"], "fn": "upper"},
    {"op": "length", "column": "price", "as": "n"}
  ]},
  "dataset": []
}
```

*Output*: `qty` was changed by `round`, so `text` on it isn't checked; after the `cast`, `price` is a number,
which `between` can handle and `length` can't:

```json
{
  "status": "error",
  "error_code": "TYPE_MISMATCH",
  "message": "ETL_ERROR: column 'price' is a number",
  "path": "pipeline.steps[4].column"
}
```
