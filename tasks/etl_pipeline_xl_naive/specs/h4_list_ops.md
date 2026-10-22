# List the Operations

We're building a visual pipeline editor. It needs to know every operation the tool supports and which
fields each one accepts, so it can offer them in menus and autocomplete, without us keeping a hand-written
copy that goes stale.

## Acceptance details

Add a `--list-ops` flag. With it, the program ignores standard input and any other flags, prints

```json
{"status": "ok", "ops": {"<op>": ["<field>", ...], ...}}
```

and exits with code `0`. Without it, everything is as before.

* `ops` has one key for every operation a step can use (including `branch`), and nothing else. The order of
  the keys doesn't matter.
* Each value lists the names of all the fields a step of that operation may have, required and optional,
  sorted alphabetically, without `op`. For `rename` that is `from`, `mapping` and `to`; for `branch` it is
  `branches` and `merge`. Only a step's own keys are listed (not the keys inside `branches` entries,
  `merge` or `summarize` metrics). An operation with no fields would list `[]`.

## Example

`etl_pipeline --list-ops` prints (shortened here; the real output lists every operation):

```json
{
  "status": "ok",
  "ops": {
    "select": ["columns"],
    "rename": ["from", "mapping", "to"],
    "branch": ["branches", "merge"],
    "lookup": ["as", "column", "default", "table"],
    "...": []
  }
}
```
