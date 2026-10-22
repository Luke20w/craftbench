# Short, printable settings

Downstream systems now store pipeline definitions in fixed-width columns, and long or unprintable values
are breaking them. Please reject them up front.

## Acceptance details

* Every string a user writes inside a step, in any field of any op and anywhere a step appears, must be at
  most 64 characters and contain no control characters (U+0000–U+001F and U+007F, including tab and
  newline). This includes `op` itself, strings inside arrays, string values of objects, and strings in
  objects nested in a step (branches, merge, metrics). It does not include object keys or the data rows in
  `append.rows`.
* Lengths are measured on the value exactly as given, before any trimming or lowercasing. Exactly 64 is fine.
* A violation is the usual validation error: `SCHEMA_VALIDATION_FAILED` at that value's path. It takes
  priority over any other problem with the same value (an over-long `op` is not `UNKNOWN_OP`; an over-long
  expression is not `BAD_EXPR`; an over-long choice is not an invalid choice).
* Applies with and without `--execute`. Nothing else changes.

## Example

`{"op": "select", "columns": ["id", "customer_lifetime_value_including_all_historic_orders_and_refunds"]}`
→ `SCHEMA_VALIDATION_FAILED` at `pipeline.steps[0].columns[1]`.
