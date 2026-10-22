# Reusable sub-pipelines

Our users keep pasting the same few steps into many pipelines (the same normalization in a dozen places,
with different numbers each time). They want to define a group of steps once, give it a name, and call it
with parameters.

## Acceptance details

A request may have a top-level `defs` object: each key is a name (case-sensitive) and each value is
`{"steps": [...]}`. Unused definitions are fine. A new `call` step runs a definition:

```json
{"op": "call", "name": "Normalize", "params": {"mean": 100, "std": 20}}
```

* `name` must match `^[A-Za-z_][A-Za-z0-9_]*$`; `params` is optional (default `{}`) and must be an object
  whose values are scalars or arrays, not objects. Otherwise `SCHEMA_VALIDATION_FAILED` at that field.
* Inside a definition's steps, expressions can read parameters as `params.<key>`; a parameter that wasn't
  passed is `null`. `params` is reserved: a row field called `params` can't be read.
* Calling a name that isn't defined: `UNKNOWN_DEF` at the call's `name`. A definition that calls itself,
  directly or through other definitions: `RECURSION_FORBIDDEN` at the offending call's `name`.
* Problems inside a definition are reported at `defs[<Name>].steps[k]...`.
* Without `--execute`, `normalized` includes `defs` (normalized) only when the request has `defs`;
  otherwise the output is exactly as before. `call` works anywhere a step can appear.

## Example

With `--execute`:

```json
{
  "defs": {"Normalize": {"steps": [{"op": "map", "as": "z", "expr": "(value - params.mean) / params.std"}]}},
  "pipeline": {"steps": [{"op": "call", "name": "Normalize", "params": {"mean": 100, "std": 20}},
                         {"op": "select", "columns": ["id", "z"]}]},
  "dataset": [{"id": 1, "value": 120}, {"id": 2, "value": 80}]
}
```

gives `{"status": "ok", "data": [{"id": 1, "z": 1}, {"id": 2, "z": -1}], "metrics": {"rows_in": 2, "rows_out": 2}}`.
