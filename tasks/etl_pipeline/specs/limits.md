# String Field Limits

Downstream systems now store pipeline definitions in fixed-width columns, so every string value
inside a step must be short and printable.

## Rule

Every **string value** supplied inside a step must:

1. be **at most 64 characters** long, and
2. contain **no control characters** (code points U+0000–U+001F and U+007F; this includes tab and newline).

The rule applies to these fields, wherever the step appears (top-level steps and steps nested
inside `branch` branches, at any depth):

| Step | Fields |
|---|---|
| any step | `op` |
| `select` | each entry of `columns` |
| `filter` | `where` |
| `map` | `as`, `expr` |
| `rename` | `from`, `to`, and each **value** in `mapping` |
| `branch` | each branch's `id` and `when`, and `merge.strategy` |

Lengths are measured on the value **exactly as provided** in the request, before any trimming or
case normalisation.

## Errors

A violation produces the normal error response with:

* `error_code`: `SCHEMA_VALIDATION_FAILED`
* `path`: the same path that is already used for other validation errors on that field
  (for example `pipeline.steps[0].columns[1]`, `pipeline.steps[2].where`,
  `pipeline.steps[0].mapping.<key>`, `pipeline.steps[0].branches[1].when`,
  `pipeline.steps[0].branches[0].steps[1].as`, `pipeline.steps[0].merge.strategy`)
* `message`: any message starting with `ETL_ERROR: ` (as for other errors)

These checks happen during validation, before anything else is done with the value. In particular:

* an over-long or control-character `op` is `SCHEMA_VALIDATION_FAILED` at `...op`, not `UNKNOWN_OP`;
* an over-long `where`/`expr`/`when` is `SCHEMA_VALIDATION_FAILED` even if it is a valid expression,
  and is reported instead of any `BAD_EXPR`.

The rule applies both with and without `--execute`. Values of exactly 64 characters are valid.
All other behaviour is unchanged.

## Example

*Input*
```json
{
  "pipeline": {"steps": [
    {"op": "select", "columns": ["id", "customer_lifetime_value_including_all_historic_orders_and_refunds"]}
  ]},
  "dataset": []
}
```

*Output*
```json
{
  "status": "error",
  "error_code": "SCHEMA_VALIDATION_FAILED",
  "message": "ETL_ERROR: select.columns entries must be at most 64 characters",
  "path": "pipeline.steps[0].columns[1]"
}
```
