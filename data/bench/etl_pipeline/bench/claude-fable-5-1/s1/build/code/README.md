# ETL pipeline CLI

Reads a JSON request on STDIN, writes a JSON response on STDOUT. Exit code 0 on
success, 1 on error. Errors are always JSON on STDOUT, never a traceback.

Two modes, chosen by the `--execute` flag:

| Invocation | Response |
| --- | --- |
| `python3 etl_pipeline.py` (or `--execute=false`) | `{"status":"ok","normalized":{"steps":[...]}}` |
| `python3 etl_pipeline.py --execute` (or `--execute=true`) | `{"status":"ok","data":[...],"metrics":{"rows_in":N,"rows_out":M}}` |

```sh
echo '{"pipeline":{"steps":[{"op":"Select","columns":["id"]}]},"dataset":[]}' \
  | python3 etl_pipeline.py

echo '{"pipeline":{"steps":[{"op":"map","as":"total","expr":"price * qty"}]},"dataset":[{"price":2,"qty":3}]}' \
  | python3 etl_pipeline.py --execute
```

`--execute` accepts a bare flag (true), `--execute=VALUE`, or `--execute VALUE`
where VALUE is one of `true/false`, `1/0`, `yes/no`, `on/off` (case-insensitive).
Bad flag values or unknown flags produce a `SCHEMA_VALIDATION_FAILED` JSON error.

Run the tests with:

```sh
python3 -m unittest -v test_etl_pipeline
```

## Code map (`etl_pipeline.py`)

| Section | What lives there |
| --- | --- |
| `EtlError` | The one exception type; `to_response()` builds the error JSON. |
| Expression parsing | `tokenize`, `Parser`, `parse_expression` produce a tuple AST. `expression_columns` lists referenced columns. |
| Expression evaluation | `evaluate(ast, row)` implements the null/type semantics below. Raises `ExprEvalError` for type errors. |
| `Schema` | Static column tracking used in normalize mode only. `Schema.disabled()` turns the checks off (execute mode). |
| Step validators | `validate_<op>(step, path, schema)` returns the normalized fields for one op. |
| Step executors | `execute_<op>(step, raw, path, rows)` returns the new rows. Never mutates its input rows. |
| `OPS` | Registry `op name -> Op(validate, execute)`. Add a new op by writing both functions and adding an entry. |
| `normalize_step` / `execute_steps` | Take a path `prefix` (default `pipeline.steps`) so `branch` can recurse into sub-pipelines with `...branches[j].steps`. |
| Request handling | `process_request(request, execute)` checks top-level shape, normalizes each step, then (execute mode) runs `execute_steps`. |
| `parse_args` / `run` / `main` | `run(text, execute)` returns `(response, exit_code)` and is handy for tests. |

## Execution model

The executor is linear: each step receives the full list of rows produced by
the previous step and returns a new list. All steps are validated (shape,
expression syntax) before any step runs, so a `BAD_EXPR` in step 3 is reported
even if step 1 would have hit a `MISSING_COLUMN` at run time.

Per-op behaviour in execute mode:

- **select**: every row must contain every column; otherwise `MISSING_COLUMN`
  at `pipeline.steps[i].columns[j]`. Output columns are in the requested order.
- **map**: evaluates `expr` per row and stores it under `as`. An existing field
  is overwritten in place (keeps its position); a new one is appended.
- **filter**: keeps rows whose `where` is truthy.
- **rename**: applies mapping entries one at a time, in iteration order. Each
  source must exist in the row at that point; otherwise `MISSING_COLUMN` at
  `pipeline.steps[i].from` (for `from`/`to` form) or `pipeline.steps[i].mapping.<key>`.
  The renamed column keeps its position. If the target already exists, the
  renamed value replaces it, so with two sources mapping to one target the
  later entry wins.
- **limit**: keeps the first `n` rows.
- **branch**: routes each row to the first branch whose `when` is truthy
  (`"otherwise"` always matches), runs each branch's `steps` over just its
  rows, then concatenates the results in branch declaration order. Rows that
  match no branch are dropped. Branches nest. Error paths inside a branch
  look like `pipeline.steps[i].branches[j].steps[k]...`; a failing `when`
  reports `pipeline.steps[i].branches[j].when`.

`metrics.rows_in` is the dataset length, `rows_out` the final row count. With
an empty dataset no step touches any row, so no `MISSING_COLUMN` can occur.

## Expression semantics

Supported: numbers, single- or double-quoted strings, identifiers
(`[A-Za-z_][A-Za-z0-9_]*`), `true`/`false`/`null`, unary `-` and `!`,
`+ - * /`, `> >= < <= == !=`, `&&`/`||`, `and`/`or`/`not` (case-insensitive
keywords), parentheses.

Precedence from low to high: `or`/`||`, `and`/`&&`, `not`, comparison,
additive, multiplicative, unary (`-`, `!`). Note `!` is C-style (binds tighter
than comparison, so `!a == b` is `(!a) == b`) while the `not` keyword is
Python-style (`not a == b` is `not (a == b)`).

Any run of operator characters that is not a supported operator (optionally
followed by unary `-`/`!`, as in `a*-b`) is a `BAD_EXPR` with the message
`unsupported operator '<run>'`. So `**`, `^^`, `=`, `<>`, `%`, `&`, `|` are all
rejected as a whole.

Values are JSON values: `null`, bool, number (int or float, never bool),
string, and arrays/objects if a row contains them.

- **Identifiers** resolve to the row field, or `null` if the field is absent.
- **Arithmetic** (`+ - * /`, unary `-`): any `null` operand gives `null`.
  Division by zero gives `null`. Non-finite results (float overflow) give
  `null`. Any non-number operand (string, bool, array, object) is an
  `EXECUTION_FAILED` error at the expression's path.
- **Number formatting**: integer literals are ints, so `2 * 3` is `6`. A float
  result that is integral is emitted as an int (`12.5 * 8` is `100`, `6 / 3`
  is `2`), matching the spec example. Dataset values that are not touched by
  an expression are passed through unchanged.
- **Equality** (`==`, `!=`): either operand `null`, or types differing
  (number vs string, bool vs number, ...) gives `false` for both operators.
  `1 == 1.0` is `true`.
- **Ordering** (`<`, `<=`, `>`, `>=`): `null` or mismatched types give `false`.
  Numbers compare numerically, strings lexicographically, bools as
  `false < true`. Arrays/objects give `false`.
- **Boolean operators** use truthiness: `null`, `false`, `0`, `""`, `[]`, `{}`
  are falsy, everything else truthy. `&&`/`||` short-circuit and always return
  a bool. `filter` uses the same truthiness.

## Decisions the spec left open

These are deliberate; change them knowingly.

- **Validation order**: top-level `pipeline`/`steps` are checked before `dataset`, then steps are checked in order. The first failure wins. In execute mode all steps are validated before any is executed.
- **Top-level error paths**: `pipeline`, `pipeline.steps`, `dataset`, `dataset[i]`. Invalid JSON, a non-object root, or bad CLI arguments use an empty path `""`.
- **Static column checks (normalize mode only)**: `MISSING_COLUMN` checks run when the dataset is non-empty. The starting column set is the union of keys across all rows. `select` narrows the set, `map` adds `as`, `rename` renames. `select` columns, `rename` sources, and identifiers in `where`/`expr` must exist. With an empty dataset nothing can be inferred, so no column checks happen.
- **Execute mode does not run the static checks.** The spec says missing identifiers in expressions resolve to `null`, and `select`/`rename` are checked per row at run time with the message `column '<name>' not found in row`. So the same request can be a `MISSING_COLUMN` in normalize mode and succeed in execute mode when an expression references an unknown column.
- **`select`** requires a non-empty array; column names are kept exactly but a column that is empty or whitespace-only is rejected.
- **`rename`** accepts `from`/`to` or `mapping`, not both. `from`/`to` are trimmed; mapping keys and values are kept exactly but empty/whitespace-only keys or values are rejected. An empty `mapping` object is rejected. The normalized form is always `mapping`. Execution applies entries sequentially, so `{"a":"b","b":"c"}` on `{"a":1,"b":2}` yields `{"c":1}`.
- **`branch`**: `branches` must be a non-empty array of objects; each needs a string `when` (non-empty after trimming) and an array `steps`; `id` is optional but must be a string if present and is passed through untouched (it has no effect on execution). `when` is trimmed and matched case-insensitively against `otherwise`, normalized to lowercase. More than one `otherwise`, or an `otherwise` that is not last, is `MALFORMED_STEP` at `pipeline.steps[i].branches`; the branch objects are shape-checked first, so a type error in any branch wins over the placement check. `merge` is optional and defaults to `{"strategy":"concat"}`; a present but non-object `merge`, a non-string `strategy`, or any strategy other than `concat` is `SCHEMA_VALIDATION_FAILED` at `...merge` / `...merge.strategy`. Normalized branch objects keep the spec's key order (`id`, `when`, `steps`). All `when` expressions are checked against the columns available *before* the branch step, since routing happens before any sub-pipeline runs. In normalize mode each sub-pipeline is checked against its own copy of the column set, and the set after the branch step is the union of all branches' results (a merged row may come from any branch). Rows are routed first, then each sub-pipeline runs over its whole slice, so a `limit` inside a branch limits that branch only.
- **`limit.n`** must be a JSON integer. Booleans, floats (even `5.0`), strings and null are rejected.
- **Empty expressions** (after trimming) are `SCHEMA_VALIDATION_FAILED`, consistent with other empty fields. Anything that fails to parse is `BAD_EXPR`; the message is the parser's own text (no extra prefix) so the spec example `unsupported operator '**'` matches exactly.
- **`EXECUTION_FAILED`** is used for type errors in arithmetic/negation and as a catch-all if an executor raises something unexpected (path is the step). Nothing else currently produces it.
- **Expressions are parsed twice** in execute mode (once to validate, once per step to execute). Parsing is trivial, and it keeps validators and executors independent. If that ever matters, have the validator return the AST alongside the normalized fields.
