# 7. Row Operations

Add fourteen operations that filter, order, number or add rows. The field kinds and execution rules from
milestone 4 apply unchanged, and everything from earlier milestones keeps working.

A value is **truthy** when it is not `null`, `false`, `0` or an empty string, array or object (the same
test `filter` uses).

## Operations

### `distinct`
| Field | Kind |
|---|---|
| `columns` | optional; array of exact strings (no default) |

Keeps the first row of each distinct combination of values in the listed columns (a missing column counts
as `null`), or of each distinct whole row when `columns` is omitted (the order of a row's columns doesn't
matter). Values are compared as JSON values.

### `sort`
| Field | Kind |
|---|---|
| `by` | required; name |
| `desc` | optional; boolean; default `false` |

Sorts the rows by the `by` column: numbers first (by value), then strings (by code point), then booleans
(`false` before `true`). `desc` reverses that order. Rows where the column is missing or `null` always come
last, in their original order. Ties keep their original order. An array or object value is an
`EXECUTION_FAILED` error at `by`.

### `offset`
| Field | Kind |
|---|---|
| `n` | required; count |

Drops the first `n` rows.

### `tail`
| Field | Kind |
|---|---|
| `n` | required; count |

Keeps only the last `n` rows (none when `n` is `0`).

### `assert`
| Field | Kind |
|---|---|
| `where` | required; expression |
| `message` | optional; exact string; default `"assertion failed"` |

Checks `where` on every row in order. If it isn't truthy for a row, the result is an `EXECUTION_FAILED`
error at `where` whose message is `ETL_ERROR: ` followed by `message`. Otherwise the rows pass through
unchanged.

### `sample_every`
| Field | Kind |
|---|---|
| `n` | required; count, at least `1` |

Keeps every n-th row, starting with the first (rows 0, n, 2n, …).

### `take_while`
| Field | Kind |
|---|---|
| `where` | required; expression |

Keeps the rows before the first row for which `where` isn't truthy.

### `skip_while`
| Field | Kind |
|---|---|
| `where` | required; expression |

Drops rows until the first row for which `where` isn't truthy; keeps that row and every row after it.

### `append`
| Field | Kind |
|---|---|
| `rows` | required; array of objects |

Adds copies of `rows` after the existing rows. The normalized step contains `rows` as given.

### `require`
| Field | Kind |
|---|---|
| `columns` | required; non-empty array of exact strings |

Every row must have each listed column with a non-`null` value. The first row (and, within it, the first
listed column) that doesn't is an `EXECUTION_FAILED` error at `columns[j]`. Otherwise the rows pass through
unchanged.

### `row_number`
| Field | Kind |
|---|---|
| `as` | required; name |
| `start` | optional; integer; default `1` |

Sets `as` to `start`, `start + 1`, … in row order.

### `rank`
| Field | Kind |
|---|---|
| `by` | required; name |
| `as` | required; name |
| `desc` | optional; boolean; default `false` |

Sets `as` to the dense rank of the row's `by` value among the distinct values: the smallest value is rank
`1` (the largest, with `desc`), equal values share a rank, and there are no gaps. A missing or `null` value
gives `null`. A value that isn't a number is an `EXECUTION_FAILED` error at `by`.

### `cumsum`
| Field | Kind |
|---|---|
| `column` | required; name |
| `as` | required; name |

Sets `as` to the running total of the column up to and including the row; missing and `null` values count
as `0`. Whole-number results are integers. A value that isn't a number is an `EXECUTION_FAILED` error at
`column`.

### `lag`
| Field | Kind |
|---|---|
| `column` | required; name |
| `as` | required; name |
| `n` | optional; count; default `1` |
| `default` | optional; scalar (no default) |

Sets `as` to the column's value in the row `n` rows earlier (`null` if that row doesn't have the column).
The first `n` rows get `default`, or `null` when it is omitted. With `n` = `0`, the row's own value is used.

## Example

*Input* (with `--execute`)
```json
{
  "pipeline": {"steps": [
    {"op": "sort", "by": "score", "desc": true},
    {"op": "rank", "by": "score", "as": "place", "desc": true},
    {"op": "cumsum", "column": "score", "as": "running"},
    {"op": "lag", "column": "name", "as": "ahead"},
    {"op": "take_while", "where": "place <= 2"}
  ]},
  "dataset": [
    {"name": "a", "score": 3},
    {"name": "b", "score": null},
    {"name": "c", "score": 5},
    {"name": "d", "score": 3}
  ]
}
```

*Output*
```json
{
  "status": "ok",
  "data": [
    {"name": "c", "score": 5, "place": 1, "running": 5, "ahead": null},
    {"name": "a", "score": 3, "place": 2, "running": 8, "ahead": "c"},
    {"name": "d", "score": 3, "place": 2, "running": 11, "ahead": "a"}
  ],
  "metrics": {"rows_in": 4, "rows_out": 3}
}
```
