# Date Operations

Our exports carry dates in whatever format the source system used: `2024-03-01` from one, `03/01/2024` from
the US office, `01/03/2024` from Europe. We need to turn them into one format, work out how many days lie
between two dates (time to ship, days overdue), and shift a date by a number of days (due dates).

## Acceptance details

Three new operations, with fields described like the operations of milestone 4 (same field kinds, the same
validation, defaults and normalization, and fields checked in the order listed). They work everywhere a
step can appear, including inside `branch`.

A **date** is a string `YYYY-MM-DD` (exactly four, two and two digits, nothing before or after) naming a
real calendar day between years 0001 and 9999 (`2023-02-29` is not a date; `2024-02-29` is).

### `to_date`
| Field | Kind |
|---|---|
| `column` | required; name |
| `format` | optional; choice of `iso`, `us`, `eu`; default `iso` |
| `as` | optional; name (no default) |

The column must exist. Reads its value in `format`: `iso` is `YYYY-MM-DD`, `us` is `MM/DD/YYYY`, `eu` is
`DD/MM/YYYY` (two-digit month and day, four-digit year, the whole string), and writes the date as
`YYYY-MM-DD` to `as`, or back into `column` when `as` is omitted. A value that isn't a string holding a
real date in that format is an `EXECUTION_FAILED` error at `column`. `null` gives `null`.

### `date_diff`
| Field | Kind |
|---|---|
| `start` | required; name |
| `end` | required; name |
| `as` | required; name |

Both columns must exist (`MISSING_COLUMN` at `start` or `end`, `start` checked first). Sets `as` to the
number of days from `start` to `end` (negative when `end` is earlier). Each non-`null` value must be a date
(otherwise `EXECUTION_FAILED` at that field, `start` checked first); if either is `null`, `as` is `null`.

### `date_add`
| Field | Kind |
|---|---|
| `column` | required; name |
| `days` | required; integer |
| `as` | required; name |

The column must exist and its value must be a date or `null` (otherwise `EXECUTION_FAILED` at `column`).
Sets `as` to the date `days` days later (earlier when negative); `null` gives `null`. A result outside years
0001–9999 is an `EXECUTION_FAILED` error at `days`.

## Example

*Input* (with `--execute`)
```json
{
  "pipeline": {"steps": [
    {"op": "to_date", "column": "ordered", "format": "us"},
    {"op": "date_add", "column": "ordered", "days": 30, "as": "due"},
    {"op": "date_diff", "start": "ordered", "end": "shipped", "as": "wait"}
  ]},
  "dataset": [
    {"ordered": "02/14/2024", "shipped": "2024-03-01"},
    {"ordered": null, "shipped": "2024-03-02"}
  ]
}
```

*Output*
```json
{
  "status": "ok",
  "data": [
    {"ordered": "2024-02-14", "shipped": "2024-03-01", "due": "2024-03-15", "wait": 16},
    {"ordered": null, "shipped": "2024-03-02", "due": null, "wait": null}
  ],
  "metrics": {"rows_in": 2, "rows_out": 2}
}
```
