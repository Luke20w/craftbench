# 6. Number and Grouping Operations

Add six operations on numbers and two that collapse rows into groups. The field kinds and execution rules
from milestone 4 apply unchanged, and everything from earlier milestones keeps working.

In this milestone, "number" never includes booleans, and a non-`null` value that isn't a number is an
`EXECUTION_FAILED` error at the field that names its column.

## Number operations

### `round`
| Field | Kind |
|---|---|
| `column` | required; name |
| `digits` | optional; count; default `0` |

The column must exist. Rounds a number to `digits` decimal places, the way Python's built-in `round()`
does (halves go to the even neighbour, applied to the binary float value). Whole-number results are
integers. `null` is left as it is.

### `clip`
| Field | Kind |
|---|---|
| `column` | required; name |
| `min` | optional; number (no default) |
| `max` | optional; number (no default) |

The column must exist. A number below `min` becomes `min`, and one above `max` becomes `max`; a bound that
is omitted doesn't apply. `null` is left as it is.

### `scale`
| Field | Kind |
|---|---|
| `column` | required; name |
| `factor` | required; number |
| `offset` | optional; number; default `0` |

The column must exist. Replaces a number `v` with `v × factor + offset` (whole-number results are
integers). `null` is left as it is.

### `bucket`
| Field | Kind |
|---|---|
| `column` | required; name |
| `as` | required; name |
| `edges` | required; non-empty array of numbers |

The column must exist. Sets `as` to how many of the `edges` are less than or equal to the value (the edges
need not be sorted). A `null` value gives `null`.

### `math`
| Field | Kind |
|---|---|
| `column` | required; name |
| `fn` | required; choice of `abs`, `floor`, `ceil`, `sqrt`, `neg` |

The column must exist. Replaces a number with its absolute value, its floor or ceiling (as integers), its
square root or its negation (whole-number results are integers). The square root of a negative number is
an `EXECUTION_FAILED` error at `column`. `null` is left as it is.

### `between`
| Field | Kind |
|---|---|
| `column` | required; name |
| `low` | required; number |
| `high` | required; number |
| `as` | required; name |

Sets `as` to `true` when the value is a number with `low ≤ value ≤ high`, otherwise `false`. A missing
column or a `null` value gives `false` (the column doesn't have to exist).

## Grouping operations

Rows belong to the same group when they have the same values in all the `by` columns (a missing column
counts as `null`; values are compared as JSON values, so `1` and `"1"` differ). Groups come out in the
order their first row appears, and an empty input gives no output rows.

### `group_count`
| Field | Kind |
|---|---|
| `by` | required; non-empty array of exact strings |
| `as` | required; name |

Outputs one row per group with the `by` columns, followed by `as` set to the number of rows in the group.

### `summarize`
| Field | Kind |
|---|---|
| `by` | optional; array of exact strings; default `[]` |
| `metrics` | required; non-empty array of metric objects (below) |

Each metric is an object with these fields, checked like the fields of a step (a metric that isn't an
object is a `SCHEMA_VALIDATION_FAILED` error at `metrics[j]`; unknown keys are dropped):

| Metric field | Kind |
|---|---|
| `as` | required; name |
| `fn` | required; choice of `sum`, `min`, `max`, `avg`, `count` |
| `column` | optional; exact string (no default) |

With no `by` columns, all rows form one group. Outputs one row per group: the `by` columns, then one column
per metric, named `as`:

* `count`: the number of non-`null` values of `column` in the group, or the number of rows when `column` is
  omitted.
* `sum`, `min`, `max`, `avg`: computed over the non-`null` values of `column`, which must all be numbers
  (otherwise `EXECUTION_FAILED` at `metrics[j].column`); `null` when there are no such values. `sum` and
  `avg` follow the whole-number rule. Without a `column`, these are an `EXECUTION_FAILED` error at
  `metrics[j].column`.

## Example

*Input* (with `--execute`)
```json
{
  "pipeline": {"steps": [
    {"op": "clip", "column": "amount", "max": 100},
    {"op": "bucket", "column": "amount", "as": "band", "edges": [10, 50]},
    {"op": "summarize", "by": ["city"], "metrics": [
      {"as": "n", "fn": "count"},
      {"as": "total", "fn": "sum", "column": "amount"},
      {"as": "mean", "fn": "avg", "column": "amount"}
    ]}
  ]},
  "dataset": [
    {"city": "Oslo", "amount": 12.5},
    {"city": "Rome", "amount": null},
    {"city": "Oslo", "amount": 250}
  ]
}
```

*Output*
```json
{
  "status": "ok",
  "data": [
    {"city": "Oslo", "n": 2, "total": 112.5, "mean": 56.25},
    {"city": "Rome", "n": 1, "total": null, "mean": null}
  ],
  "metrics": {"rows_in": 3, "rows_out": 2}
}
```
