# etl_pipeline

CLI that reads an ETL pipeline request as JSON on STDIN and writes a JSON
response to STDOUT. Exit code 0 on success, 1 on error.

```sh
# Validate + normalize (milestone 1): returns {"status":"ok","normalized":{...}}
echo '{"pipeline":{"steps":[{"op":"Select","columns":["id"]}]},"dataset":[]}' | python3 etl_pipeline.py

# Validate + execute (milestone 2): returns {"status":"ok","data":[...],"metrics":{...}}
echo '{"pipeline":{"steps":[{"op":"Select","columns":["id"]}]},"dataset":[{"id":1}]}' | python3 etl_pipeline.py --execute
```

`--execute` defaults to false. `--execute`, `--execute=true` and
`--execute true` turn execution on; `--execute=false` / `--execute false`
turn it off.

## Layout

Everything lives in `etl_pipeline.py`, in pipeline order:

- **Errors.** `EtlError(code, message, path)` can be raised anywhere; `handle()`
  turns it into the error response and prefixes `message` with `ETL_ERROR: `.
  Codes: `SCHEMA_VALIDATION_FAILED`, `UNKNOWN_OP`, `BAD_EXPR`, `MISSING_COLUMN`,
  `EXECUTION_FAILED`, `MALFORMED_STEP`.
- **Expression syntax.** `tokenize` / `Parser` / `parse_expression` produce a
  tuple AST (`("binary", op, l, r)`, `("unary", op, x)`, `("ident", name)`,
  `("num"|"str"|"const", value)`). Logical operators are canonicalised to
  `and` / `or` / `not` whether written as `&&` / `||` / `!` or as keywords.
  A run of operator characters that is not a known operator (`**`, `^^`, `=`,
  `<>`, ...) raises `unsupported operator '...'`, which becomes `BAD_EXPR`.
- **Expression evaluation.** `evaluate(ast, row)` implements the semantics:
  missing identifiers are `null`; arithmetic with `null` or division by zero
  yields `null`; arithmetic on non-numbers raises `EvalError` (reported as
  `EXECUTION_FAILED`); any comparison involving `null` or mismatched types is
  `false` (including `!=`); `&&`/`||`/`!` coerce with JSON truthiness and
  return booleans. Integral float results are collapsed to ints
  (`12.5 * 8` -> `100`), non-finite floats become `null`.
- **Normalization.** One `normalize_<op>` per op, registered in
  `OP_NORMALIZERS`. `normalize_step(step, path)` handles op trimming/lowercasing,
  unknown ops and output key ordering; `normalize_steps(steps, path)` maps it
  over a list. Both take the dotted *path* of what they are normalizing
  (`pipeline.steps`, `pipeline.steps[0].branches[1].steps`, ...) so nested
  step lists inside `branch` report accurate error paths.
- **Execution.** One `execute_<op>` per op, registered in `OP_EXECUTORS`, with
  signature `(normalized_step, raw_step, path, rows) -> rows`. `raw_step` is
  only used for error paths that must refer to the request's spelling (a
  `rename` written with `from`/`to` reports `...steps[i].from`, one written
  with `mapping` reports `...steps[i].mapping.<src>`). Rows are shallow
  copies of the dataset, so executors may mutate them in place.
  `execute_steps(steps, raw_steps, path, rows)` runs a step list (top level or
  inside a branch); `execute_pipeline` wraps it for the top level and builds
  `metrics` (`rows_in`/`rows_out` are top-level only).
- **Request flow.** `validate_request` -> `handle(raw, execute)` -> `main`.

### Operation semantics worth knowing

- `select` checks every row; the first row missing a column fails with
  `MISSING_COLUMN` at `columns[<idx>]`. An empty dataset never fails.
- `map` overwrites an existing field in place (keeps its position); a new
  field is appended.
- `rename` applies mapping entries in order. Renaming keeps the column's
  position and drops any pre-existing column with the target name, so with
  `{"a":"x","b":"x"}` the later entry wins.
- `limit` keeps the first `n` rows.
- `branch` (milestone 3) routes each row to the **first** branch whose `when`
  is truthy (JSON truthiness, same expression language as `filter`); the
  literal `"otherwise"` (case-insensitive, trimmed) always matches. Later
  branches' conditions are not evaluated for a row once it is claimed, so a
  condition that would fail on that row never runs. Rows matching no branch
  are dropped. Each branch's `steps` then run over only its rows, and results
  are concatenated in branch declaration order (`merge.strategy` is always
  `"concat"`; `merge` and `strategy` default to it when absent). Branch
  `steps` may contain any op, including nested `branch`.
  Validation: `branches` must be a non-empty array of
  `{id?: string, when: string, steps: array}`; `MALFORMED_STEP` at
  `...steps[i].branches` if there is more than one `otherwise` or it is not
  last; everything else (types, missing fields, unknown merge strategy) is
  `SCHEMA_VALIDATION_FAILED`. The normalized form keeps `id` only when it was
  supplied and always emits `merge: {"strategy": "concat"}`.

To add an op: write a normalizer and an executor, register both.

## Tests

```sh
python3 -m unittest discover tests
```
