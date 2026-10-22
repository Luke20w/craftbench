# 5. Text Operations

Add twelve operations that work on strings. The field kinds and execution rules from milestone 4 apply
unchanged, and everything from earlier milestones keeps working.

## Operations

### `concat`
| Field | Kind |
|---|---|
| `as` | required; name |
| `columns` | required; non-empty array of exact strings |
| `sep` | optional; exact string; default `""` |

Each listed column must exist. Sets `as` to the text forms of the listed columns joined with `sep`; a
`null` value contributes an empty string.

### `split`
| Field | Kind |
|---|---|
| `column` | required; name |
| `sep` | required; non-empty exact string |
| `into` | required; non-empty array of exact strings |

The column must exist. Splits its string value at every occurrence of `sep` and sets `into[i]` to the
i-th part, or to `null` when there are fewer parts; extra parts are dropped. The column itself is kept. A
`null` value sets every `into` column to `null`. Any other non-string value is an `EXECUTION_FAILED` error
at `column`.

### `text`
| Field | Kind |
|---|---|
| `columns` | required; array of exact strings |
| `fn` | required; choice of `upper`, `lower`, `trim` |

Each listed column must exist. Applies `fn` to each listed column's value: `upper` and `lower` change the
case; `trim` removes leading and trailing whitespace. `null` values are skipped; any other non-string value
is an `EXECUTION_FAILED` error at `columns[j]`.

### `replace`
| Field | Kind |
|---|---|
| `column` | required; name |
| `find` | required; non-empty exact string |
| `with` | required; exact string |

The column must exist. Replaces every occurrence of `find` in the string value with `with`. `null` is
skipped; any other non-string value is an `EXECUTION_FAILED` error at `column`.

### `regex_extract`
| Field | Kind |
|---|---|
| `column` | required; name |
| `pattern` | required; regex |
| `as` | required; name |
| `group` | optional; count; default `0` |

The column must exist. Finds the first match of `pattern` anywhere in the string value and sets `as` to
the text of capture group `group` (`0` is the whole match). `as` is `null` when there is no match, when the
group didn't take part in the match, or when the value is `null`. A non-string value is an
`EXECUTION_FAILED` error at `column`. When there is a match and the pattern has fewer than `group` capture
groups, the error is `EXECUTION_FAILED` at `group`.

### `regex_filter`
| Field | Kind |
|---|---|
| `column` | required; name |
| `pattern` | required; regex |
| `invert` | optional; boolean; default `false` |

Keeps the rows whose column holds a string containing a match of `pattern`. A row where the column is
missing, `null` or not a string doesn't match (this is not an error). With `invert`, keeps the rows that
don't match instead.

### `substr`
| Field | Kind |
|---|---|
| `column` | required; name |
| `as` | required; name |
| `start` | required; count |
| `length` | optional; count (no default) |

The column must exist. Sets `as` to the characters of the string value starting at index `start`
(0-based): `length` characters, or up to the end when `length` is omitted. Past the end of the string the
result is `""`. A `null` value gives `null`; any other non-string value is an `EXECUTION_FAILED` error at
`column`.

### `pad`
| Field | Kind |
|---|---|
| `column` | required; name |
| `width` | required; count |
| `fill` | optional; non-empty exact string; default `" "` |
| `side` | optional; choice of `left`, `right`; default `left` |

The column must exist. Every non-`null` value is replaced by its text form, padded on `side` up to `width`
characters with `fill` repeated (and cut to fit exactly). Values that are already `width` characters or
longer are not cut, but are still converted to their text form. `null` is left as it is.

### `length`
| Field | Kind |
|---|---|
| `column` | required; name |
| `as` | required; name |

The column must exist. Sets `as` to the number of characters of a string, elements of an array or keys of
an object; `null` gives `null`. Any other value is an `EXECUTION_FAILED` error at `column`.

### `json_parse`
| Field | Kind |
|---|---|
| `column` | required; name |

The column must exist. Replaces a string value with the JSON value it contains. `null` is left as it is.
A non-string value, or a string that isn't valid JSON, is an `EXECUTION_FAILED` error at `column`.

### `json_dump`
| Field | Kind |
|---|---|
| `column` | required; name |

The column must exist. Replaces every non-`null` value with its JSON text: keys sorted, `", "` between
elements, `": "` between keys and values, non-ASCII characters escaped as `\uXXXX`. A string becomes a
quoted JSON string (`abc` → `"\"abc\""`). `null` is left as it is.

### `date_part`
| Field | Kind |
|---|---|
| `column` | required; name |
| `part` | required; choice of `year`, `month`, `day` |
| `as` | required; name |

The column must exist. The value must be a string that starts with a date written `YYYY-MM-DD` (four, two
and two digits; anything may follow, and the numbers are not otherwise checked). Sets `as` to that part as
an integer. A `null` value gives `null`; anything else is an `EXECUTION_FAILED` error at `column`.

## Example

*Input* (with `--execute`)
```json
{
  "pipeline": {"steps": [
    {"op": "split", "column": "name", "sep": " ", "into": ["first", "last"]},
    {"op": "text", "columns": ["last"], "fn": "upper"},
    {"op": "concat", "as": "label", "columns": ["last", "id"], "sep": "-"},
    {"op": "pad", "column": "id", "width": 4, "fill": "0"},
    {"op": "date_part", "column": "day", "part": "month", "as": "month"}
  ]},
  "dataset": [
    {"id": 7, "name": "Ada Lovelace", "day": "1815-12-10"},
    {"id": 42, "name": "Plato", "day": null}
  ]
}
```

*Output*
```json
{
  "status": "ok",
  "data": [
    {"id": "0007", "name": "Ada Lovelace", "day": "1815-12-10", "first": "Ada", "last": "LOVELACE",
     "label": "LOVELACE-7", "month": 12},
    {"id": "0042", "name": "Plato", "day": null, "first": "Plato", "last": null, "label": "-42",
     "month": null}
  ],
  "metrics": {"rows_in": 2, "rows_out": 2}
}
```
