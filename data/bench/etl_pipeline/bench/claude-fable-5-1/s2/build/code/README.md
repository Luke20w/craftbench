# ETL pipeline CLI

Reads a JSON request on STDIN, validates and normalizes the pipeline and, with
`--execute`, runs it over the request's `dataset`. Writes a JSON response to
STDOUT. Exit code 0 on success, 1 on error.

    python3 etl_pipeline.py < request.json             # {"status":"ok","normalized":{...}}
    python3 etl_pipeline.py --execute < request.json   # {"status":"ok","data":[...],"metrics":{...}}
    python3 -m unittest -v test_etl_pipeline

`--execute` accepts an optional value (`--execute=false`, `--execute 1`);
the bare flag means true. Default is false.

## Layout of `etl_pipeline.py`

- `EtlError` – the only exception type; carries `code`, `message`, `path`.
- Expression parser (`tokenize`, `Parser`, `parse_expression`) – builds an AST
  (tuples: `num`, `str`, `col`, `bool`, `null`, `neg`, `not`, `bin`).
- `evaluate(ast, row)` – evaluates an AST against a row dict. Raises
  `ExpressionRuntimeError` (mapped to `EXECUTION_FAILED`) for type errors.
- `OP_NORMALIZERS` – one `_normalize_<op>` function per operation; each takes
  the raw step, the step's JSON path (`pipeline.steps[0]` or, inside a branch,
  `pipeline.steps[0].branches[1].steps[2]`) and the column tracker.
- `OP_EXECUTORS` – one `_exec_<op>` function per operation; each takes the
  normalized step, the raw step, the step's JSON path and the current rows and
  returns the new rows. To add an op, register both a normalizer and an executor.
- `normalize_steps` / `execute_steps` – run a step list under a given path
  prefix. They are what `branch` recurses into for its sub-pipelines, so any
  new op that nests steps should call them too.
- Paths are built with `_sub(path, "field")` and `_item(path, index)`.
- `ColumnTracker` – follows the set of available columns through the steps in
  normalize-only mode when the dataset is non-empty, producing `MISSING_COLUMN`
  errors. It is disabled in execute mode (the executor reports missing columns
  itself, and expression identifiers resolve to null).
- `process_request(request, execute)` / `run(text, execute)` – pure entry
  points; `main` handles argv and stdin/stdout.

## Expression language

Operators: `!`, `-` (unary), `*`, `/`, `+`, `-`, `<`, `<=`, `>`, `>=`, `==`,
`!=`, `&&`, `||`, parentheses. The keywords `and`, `or`, `not` (from
milestone 1) remain accepted as aliases. Strings may use single or double
quotes. Any other operator (`**`, `^^`, `=`, `%`, ...) is `BAD_EXPR`
with message `unsupported operator '<op>'`.

Precedence, highest first: unary `-`/`+`/`!`; `*` `/`; `+` `-`; comparisons;
`&&`/`and`; `||`/`or`. The keyword `not` binds *below* comparisons (Python
style) while `!` binds above them (C style).

Evaluation rules:

- Unknown identifiers evaluate to `null`.
- Arithmetic with a `null` operand yields `null`; division by zero yields `null`.
- Comparisons involving `null`, or operands of different JSON types, are `false`
  (including `null == null`). Ordering is only defined for numbers and strings;
  other same-type orderings are `false`. Booleans are not numbers.
- `&&`, `||`, `!` and `filter` use truthiness: `null`, `false`, `0`, `""` and
  empty containers are falsy.
- `+` on two strings concatenates. Any other arithmetic on non-numbers is
  `EXECUTION_FAILED` with the path of the `expr`/`where` field.
- Arithmetic results that are integral floats are emitted as integers
  (`12.5 * 8` → `100`), matching the spec examples.

## Execution semantics

- `select` rebuilds each row with the columns in the requested order. A column
  missing from any row is `MISSING_COLUMN` at `pipeline.steps[i].columns[j]`.
- `map` sets/overwrites `as`; an existing field keeps its position.
- `rename` applies mapping entries in iteration order, sequentially; the renamed
  column keeps the source's position and an existing target is overwritten.
  Missing source → `MISSING_COLUMN` at `.mapping.<src>` (mapping form) or
  `.from` (from/to form).
- `limit` keeps the first `n` rows.
- `branch` routes each row to the first branch whose `when` is truthy (same
  rules as `filter`); `"otherwise"` always matches. Rows matching no branch are
  dropped. Each branch's `steps` run over its rows only, then the results are
  concatenated in branch declaration order (`merge.strategy` is always
  `concat`). Every branch runs even if it received no rows, so a step that
  fails only on non-empty input is not reported for an empty branch. Errors
  inside a branch use the nested path
  `pipeline.steps[i].branches[j].steps[k]...`; errors evaluating `when` use
  `pipeline.steps[i].branches[j].when`.
- Rows are copied before execution; the input dataset is never mutated.
- `metrics.rows_in` is the dataset length, `rows_out` the result length.

## Decisions not spelled out by the spec

- `rename` with both `mapping` and `from`/`to`: `mapping` wins.
- Empty `columns` array, empty `mapping`, or empty column-name strings are
  `SCHEMA_VALIDATION_FAILED`.
- In normalize-only mode, element-level column errors point at the containing
  field (`pipeline.steps[i].columns`) as in milestone 1; execute mode uses the
  element path (`columns[2]`, `mapping.cost`) as in the milestone 2 examples.
- Unknown ops are `UNKNOWN_OP` in both modes.
- Root-level problems (invalid JSON, non-object request) use `path: ""`.
- Any unexpected exception during a step is reported as `EXECUTION_FAILED`
  at `pipeline.steps[i]` rather than a traceback.

### `branch`

- `branches` must be a non-empty array of objects, each with a required
  `when` (non-empty string) and required `steps` (array, may be empty), and an
  optional string `id`. `id` is echoed in the normalized output only when given.
- `when` is trimmed; `"otherwise"` is matched case-insensitively and emitted
  lower-case. Anything else is parsed as an expression (`BAD_EXPR` at
  `...branches[j].when`).
- `merge` is optional and defaults to `{"strategy": "concat"}`; any other
  strategy (or a non-object `merge`) is `SCHEMA_VALIDATION_FAILED` at
  `...merge.strategy` / `...merge`.
- Validation order: branch shapes (types, parseable `when`) and `merge` first,
  then the `otherwise` placement rules (`MALFORMED_STEP` at `...branches`),
  then the nested steps of each branch in order. So a malformed `otherwise`
  layout is reported before errors inside the sub-pipelines.
- Column tracking (normalize-only mode): each branch starts from the columns
  available before the branch step; afterwards the *union* of every branch's
  output columns is available. A later step that needs a column only some
  branches produce therefore normalizes fine and fails per row when executed.
