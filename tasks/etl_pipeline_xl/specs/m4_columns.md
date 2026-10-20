# 4. Column Operations

Add twelve operations that add, remove and reshape columns. Everything from the earlier milestones keeps
working, and the new operations work everywhere a step can appear, including inside `branch` branches.

More operations will follow in later milestones, all described with the field kinds and execution
rules below.

## Field kinds

Each field of a new operation has one of these kinds.

| Kind | Accepts | Normalized value |
|---|---|---|
| **name** | a string; surrounding whitespace is trimmed; must not be empty after trimming | the trimmed string |
| **exact string** | a string, kept exactly as given (spaces are significant); may be empty unless marked *non-empty* | as given |
| **choice of** *a, b, …* | a string; trimmed and lowercased; must then be one of the listed words | the lowercased word |
| **boolean** | `true` or `false` | as given |
| **expression** | same rules as `map.expr`: a string, trimmed, not empty, a valid expression (`BAD_EXPR` otherwise) | the trimmed string |
| **count** | an integer ≥ 0, or ≥ the stated minimum (booleans are not integers) | as given |
| **integer** | any integer (booleans are not integers) | as given |
| **number** | an integer or a float (not a boolean) | as given |
| **scalar** | `null`, a boolean, a number or a string | as given |
| **regex** | a non-empty string that is a valid regular expression (Python `re` syntax), kept exactly | as given |
| **array of** *K* | an array; each element is checked as kind *K* at path `<field>[i]`; *non-empty* means at least one element | the array of normalized elements |
| **object of** *K* | an object; each value is checked as kind *K* at path `<field>.<key>`; keys are kept as given | the object of normalized values |
| **array of objects** | an array whose elements are all objects (error at `<field>[i]`) | copied as given |

Rules for every new operation:

* A field that breaks its kind's rules is a `SCHEMA_VALIDATION_FAILED` error at that field's path, for
  example `pipeline.steps[0].columns[1]` or `pipeline.steps[2].table.US`.
* A missing required field is a `SCHEMA_VALIDATION_FAILED` error at `pipeline.steps[i].<field>`.
* Fields are checked in the order they are listed below; the first problem found is reported.
* An optional field that has a **default** appears in the normalized step with that default when it is
  omitted. An optional field without a default is left out when omitted.
* As before, the normalized step has `op` first and the other fields in alphabetical order, and unknown
  keys are dropped.

## Execution rules

* **The column must exist:** if a row doesn't have the column, the error is `MISSING_COLUMN` at the
  field's path. For an array field, the path is `<field>[j]`; rows are checked in order and, within a
  row, columns in the listed order.
* **Bad values:** when a value has the wrong type for an operation, the error is `EXECUTION_FAILED` at the
  field's path (the message wording is up to you, after the `ETL_ERROR:` prefix).
* **Nulls:** unless stated otherwise, a `null` value is left as it is.
* **Text form:** strings are used as they are; any other value is written as JSON text, with `", "`
  between elements, `": "` between keys and values, and non-ASCII characters escaped as `\uXXXX`
  (for example `12.5`, `true`, `null`, `["a", "b"]`, `{"x": 1}`).
* **Whole numbers:** where an operation computes a number, a float result with no fractional part (and a
  magnitude below 10^15) is output as an integer (`3.0` → `3`).

Expressions (`fill.value`, `coalesce.exprs`) are evaluated against the row, as in `map`; an expression
error points at that field (`pipeline.steps[i].exprs[k]`).

## Operations

### `drop`
| Field | Kind |
|---|---|
| `columns` | required; array of exact strings |

Removes the listed columns from every row. Each listed column must exist.

### `fill`
| Field | Kind |
|---|---|
| `column` | required; name |
| `value` | required; expression |

In every row where `column` is missing or `null`, sets it to `value` evaluated on that row. Other rows are
unchanged.

### `cast`
| Field | Kind |
|---|---|
| `column` | required; name |
| `to` | required; choice of `int`, `float`, `string`, `bool` |

Converts the column's value in every row. The column must exist; `null` stays `null`.

* `int`: integers unchanged; floats truncated toward zero; strings that hold an integer (surrounding
  whitespace allowed), e.g. `"12"` → `12`. Anything else fails, including `"12.5"` and booleans.
* `float`: numbers, and strings that hold a number (`"2.5"`, `"1e3"`). Anything else fails, including
  booleans.
* `string`: the value's text form.
* `bool`: booleans unchanged; the strings `"true"` and `"false"` (any case, surrounding whitespace
  allowed); numbers become `false` if zero, otherwise `true`. Anything else fails.

A value that can't be converted is an `EXECUTION_FAILED` error at `column`.

### `coalesce`
| Field | Kind |
|---|---|
| `as` | required; name |
| `exprs` | required; non-empty array of expressions |

Sets `as` to the first non-`null` result of `exprs`, evaluated in order (later ones are not evaluated), or
`null` if every result is `null`.

### `explode`
| Field | Kind |
|---|---|
| `column` | required; name |

The column must exist. A row whose value is an array becomes one row per element, in order, each a copy of
the row with the column set to that element; an empty array produces no rows. Rows with any other value
(including `null`) are kept as they are.

### `lookup`
| Field | Kind |
|---|---|
| `column` | required; name |
| `as` | required; name |
| `table` | required; object of scalars |
| `default` | optional; scalar (no default) |

The column must exist. The lookup key is the value itself if it is a string, otherwise its text form
(`1` → `"1"`, `true` → `"true"`, `null` → `"null"`). Sets `as` to the table's value for that key; if the
key isn't in the table, to `default` when given, otherwise `null`.

### `set`
| Field | Kind |
|---|---|
| `column` | required; name |
| `value` | required; scalar |

Sets the column to `value` in every row, adding it where it is missing.

### `ensure`
| Field | Kind |
|---|---|
| `columns` | required; non-empty array of exact strings |
| `value` | optional; scalar; default `null` |

Adds each listed column that a row doesn't have, set to `value`, after the row's existing columns and in
the listed order. Columns a row already has keep their value, even if it is `null`.

### `reorder`
| Field | Kind |
|---|---|
| `columns` | required; non-empty array of exact strings |

Each listed column must exist. Every row gets the listed columns first, in the listed order, followed by
its other columns in their existing order.

### `prefix`
| Field | Kind |
|---|---|
| `prefix` | required; non-empty exact string |
| `columns` | optional; array of exact strings (no default) |

Renames columns by putting `prefix` in front of their names: the listed columns that the row has (listed
columns it doesn't have are ignored), or every column of the row when `columns` is omitted. Column order is
kept.

### `nest`
| Field | Kind |
|---|---|
| `columns` | required; non-empty array of exact strings |
| `as` | required; name |

Each listed column must exist. Moves the listed columns into an object (keys in the listed order) stored
in a new last column `as`; the row keeps its other columns in their existing order.

### `unnest`
| Field | Kind |
|---|---|
| `column` | required; name |
| `prefix` | optional; exact string; default `""` |

The column must exist, and its value must be an object or `null` (otherwise `EXECUTION_FAILED` at
`column`). Removes the column and adds each key of the object as a column named `prefix` + key, replacing
any existing column of that name. For `null`, the column is removed and nothing is added.

## Examples

**1) Normalization with defaults**

*Input*
```json
{
  "pipeline": {"steps": [
    {"op": " Ensure ", "columns": ["region"], "note": "dropped"},
    {"op": "unnest", "column": " meta "}
  ]},
  "dataset": []
}
```

*Output*
```json
{
  "status": "ok",
  "normalized": {"steps": [
    {"op": "ensure", "columns": ["region"], "value": null},
    {"op": "unnest", "column": "meta", "prefix": ""}
  ]}
}
```

**2) Execution**

*Input* (with `--execute`)
```json
{
  "pipeline": {"steps": [
    {"op": "lookup", "column": "cc", "as": "country", "table": {"NO": "Norway", "1": "one"}, "default": "?"},
    {"op": "explode", "column": "tags"},
    {"op": "drop", "columns": ["cc"]}
  ]},
  "dataset": [
    {"id": 1, "cc": "NO", "tags": ["a", "b"]},
    {"id": 2, "cc": 1, "tags": []},
    {"id": 3, "cc": "SE", "tags": "x"}
  ]
}
```

*Output*
```json
{
  "status": "ok",
  "data": [
    {"id": 1, "tags": "a", "country": "Norway"},
    {"id": 1, "tags": "b", "country": "Norway"},
    {"id": 3, "tags": "x", "country": "?"}
  ],
  "metrics": {"rows_in": 3, "rows_out": 3}
}
```

**3) A missing column**

*Input* (with `--execute`)
```json
{
  "pipeline": {"steps": [{"op": "reorder", "columns": ["id", "name"]}]},
  "dataset": [{"id": 1, "name": "a"}, {"id": 2}]
}
```

*Output*
```json
{
  "status": "error",
  "error_code": "MISSING_COLUMN",
  "message": "ETL_ERROR: column 'name' not found in row",
  "path": "pipeline.steps[0].columns[1]"
}
```
