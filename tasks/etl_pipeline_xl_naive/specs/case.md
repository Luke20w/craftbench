# Conditional values

Analysts keep writing chains of `branch` + `map` just to compute one column from a list of conditions
("price under 20 is cheap, under 100 is mid, otherwise premium"). They want one step for that.

## Acceptance details

```json
{"op": "case", "as": "tier",
 "cases": [{"when": "price < 20", "then": "\"cheap\""}, {"when": "price < 100", "then": "\"mid\""}],
 "else": "\"premium\""}
```

* `as`: required, same rules as `map.as`. `cases`: required, non-empty array of objects, each with a
  required `when` and `then`. `else`: optional. `when`, `then` and `else` are expressions with the same
  rules as `map.expr`.
* Problems are reported like any other step's, at the field's path (`...cases[j]`, `...cases[j].when`,
  `...else`, …), with the usual error codes; evaluation errors are `EXECUTION_FAILED` at the field being
  evaluated.
* Normalized like every other step: `op` first, then `as`, `cases`, `else` (omitted when not given); each
  case becomes exactly `{"then", "when"}`; unknown keys are dropped.
* With `--execute`, each row gets `as` set to the `then` of the first case whose `when` is truthy (same
  truthiness as `filter`), else the `else` value, else `null`. Rows are otherwise unchanged.
* Works anywhere a step can appear.

## Example

With `--execute`, on rows with `price` 10, 50 and 500, the step above adds `tier` = `"cheap"`, `"mid"`
and `"premium"`.
