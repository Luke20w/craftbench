# ETL pipeline CLI

    python3 etl_pipeline.py < request.json            # validate + normalize
    python3 etl_pipeline.py --execute < request.json  # run the pipeline

Reads a request `{"pipeline": {"steps": [...]}, "dataset": [...]}` on stdin and
writes a JSON response to stdout (exit 0 on success, 1 on error). Without
`--execute` (also `--execute=false`) it returns `normalized`; with `--execute`
(or `--execute=true` / `--execute true`) it returns `data` and `metrics`.

## Layout

- `etl_pipeline.py` – CLI entrypoint (JSON in/out, exit codes).
- `etl/errors.py` – `EtlError` and the error-code constants.
- `etl/schema.py` – request validation and per-op step normalizers (`STEP_NORMALIZERS`).
- `etl/expr.py` – expression tokenizer/parser; `parse()` returns a tuple AST (grammar in the docstring).
- `etl/evaluator.py` – evaluates an AST against a row (null/type semantics in the docstring).
- `etl/executor.py` – per-op step runners (`STEP_RUNNERS`) and `execute()`. A new op needs both a normalizer and a runner.
- `tests/test_cli.py` – end-to-end tests: `python3 -m unittest discover tests`.

## Decisions where the spec is silent

- Validation order: top-level structure (`pipeline`, `pipeline.steps`, `dataset`, and the type of each row) first, then the steps in order. The first error found is the one reported.
- Invalid JSON or a non-object request returns `SCHEMA_VALIDATION_FAILED` with path `""`.
- Column names and mapping keys/values are kept exactly as given, but empty or whitespace-only values are rejected.
- `select.columns` and `rename.mapping` must not be empty. A rename can't mix `from`/`to` with `mapping`.
- `limit.n` must be a JSON integer; booleans and floats such as `1.5` are rejected.
- Expressions also accept string literals (`'x'` / `"x"`), numbers, `true`/`false`/`null`, and unary `-`/`+`. Comparisons can't be chained.
- An empty or whitespace-only expression is `SCHEMA_VALIDATION_FAILED`. A syntax error is `BAD_EXPR`.
- Expressions also accept `and`/`or`/`not` alongside `&&`/`||`/`!`. `not` binds loosely (`not a == b` is `not (a == b)`); `!` binds tightly (`!a == b` is `(!a) == b`).
- A run of operator characters that isn't a supported operator (optionally followed by unary `!`, `-`, `+`) gives `BAD_EXPR` with message `unsupported operator '<run>'`, e.g. `**`, `^^`, `<>`, `!==`, `%`.

### Execution

- The whole pipeline is validated first, so a schema/expression error in any step is reported before execution starts. Each step then runs over all rows before the next step starts. The first error is reported: earliest step first, then earliest row.
- A row only fails `select`/`rename` if it actually reaches that step, so an empty dataset or rows dropped by an earlier filter never raise `MISSING_COLUMN`.
- `rename` entries apply sequentially (`{"a":"b","b":"c"}` moves `a` to `c`). The renamed key keeps the source's position and replaces any existing target. A missing source points at `.mapping.<source>`, or at `.from` for the `from`/`to` form. Renaming a column to itself is a no-op.
- `filter` keeps a row when `where` is truthy. null, false, 0, `""` and empty arrays/objects are falsy. `&&`, `||` and `!` always return booleans.
- `!=` follows the same rules as `==`: it is `false` if either side is null or the types differ.
- `+` concatenates two strings. Any other arithmetic on non-numbers (booleans, strings, arrays, objects) gives `EXECUTION_FAILED` at the expression's path. The same applies to non-finite results (overflow).
- Arithmetic results that are integral floats are emitted as integers (`12.5 * 8` → `100`).
- `metrics.rows_in` is the dataset length and `metrics.rows_out` is the number of rows returned.

### Branch

- `branches` must be a non-empty array; each branch needs `when` (expression or `"otherwise"`, compared after trimming) and `steps` (an array, may be empty). `id` is optional and kept verbatim; it is omitted from the normalized output when absent.
- The `otherwise` placement rules (at most one, must be last) are checked before the contents of individual branches, so a misplaced `otherwise` is reported even if a branch is otherwise invalid.
- `merge` is optional; `merge.strategy` defaults to `concat` and any other value is `SCHEMA_VALIDATION_FAILED` at `.merge.strategy`. The normalized step always includes `"merge": {"strategy": "concat"}`.
- A row goes to the first branch whose `when` is truthy (same rules as `filter`). All rows are routed first, then each branch's sub-pipeline runs over its rows in declaration order, so errors in an earlier branch are reported first.
