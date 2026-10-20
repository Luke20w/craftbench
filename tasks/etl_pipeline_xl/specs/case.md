# Conditional Values: the `case` Step

Analysts keep writing chains of `branch` + `map` just to compute one column from a list of
conditions. Add a `case` step that does this directly.

## Step format

```json
{
  "op": "case",
  "as": "tier",
  "cases": [
    {"when": "price < 20",  "then": "\"cheap\""},
    {"when": "price < 100", "then": "\"mid\""}
  ],
  "else": "\"premium\""
}
```

| Field | Rules |
|---|---|
| `as` | required; same rules as `map.as` (string, trimmed, must not be empty) |
| `cases` | required; non-empty array. Each element is an object with required `when` and `then` |
| `cases[j].when`, `cases[j].then` | expressions; same rules as `map.expr` (string, trimmed, must not be empty, must be a valid expression) |
| `else` | optional expression; same rules as `map.expr` |

## Normalization

Same conventions as every other step: `op` is trimmed and lowercased; `op` comes first and the
other keys follow alphabetically (`as`, `cases`, `else`); `else` is omitted when it was not given;
each case is normalized to an object with exactly `then` and `when` (trimmed); unknown keys are
dropped, both on the step and inside each case.

## Semantics (with `--execute`)

For each row, the cases are tried in order. The first case whose `when` is truthy (same truthiness
as `filter`) sets the column `as` to the value of its `then`. If no case matches, `as` is set to
the value of `else`, or to `null` if there is no `else`. Like `map`, an existing column with that
name is overwritten. Row count is unchanged.

`case` can be used anywhere a step can appear, including inside `branch` branches at any depth.

## Errors

Normal error response, with these paths:

| Problem | `error_code` | `path` |
|---|---|---|
| `as` missing, not a string or empty | `SCHEMA_VALIDATION_FAILED` | `...steps[i].as` |
| `cases` missing, not an array, or empty | `SCHEMA_VALIDATION_FAILED` | `...steps[i].cases` |
| a case is not an object | `SCHEMA_VALIDATION_FAILED` | `...steps[i].cases[j]` |
| `when`/`then` missing, not a string or empty | `SCHEMA_VALIDATION_FAILED` | `...steps[i].cases[j].when` / `.then` |
| `else` not a string or empty | `SCHEMA_VALIDATION_FAILED` | `...steps[i].else` |
| invalid expression | `BAD_EXPR` | `...cases[j].when`, `...cases[j].then` or `...else` |
| evaluation error (e.g. type mismatch) | `EXECUTION_FAILED` | the field being evaluated: `...cases[j].when`, `...cases[j].then` or `...else` |

Validation errors are reported with and without `--execute`.

## Example

*Input* (with `--execute`)
```json
{
  "pipeline": {"steps": [
    {"op": "case", "as": "tier",
     "cases": [{"when": "price < 20", "then": "\"cheap\""}, {"when": "price < 100", "then": "\"mid\""}],
     "else": "\"premium\""}
  ]},
  "dataset": [{"id": 1, "price": 10}, {"id": 2, "price": 50}, {"id": 3, "price": 500}]
}
```

*Output*
```json
{
  "status": "ok",
  "data": [
    {"id": 1, "price": 10, "tier": "cheap"},
    {"id": 2, "price": 50, "tier": "mid"},
    {"id": 3, "price": 500, "tier": "premium"}
  ],
  "metrics": {"rows_in": 3, "rows_out": 3}
}
```
