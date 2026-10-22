# Explain a Pipeline

Our data team wants column lineage: before a pipeline runs, they want to see, step by step, which columns
each step uses and which columns it creates, changes or deletes, so they can tell what a change to a source
column will break downstream. Today they work it out by reading the pipeline by hand.

## Acceptance details

Add an `--explain` flag. Without it, everything is exactly as before.

With `--explain`, the request is validated exactly as usual (a request that fails validation gives exactly the
same error response as without the flag), but nothing is normalized into the output and the pipeline is never
run, even with `--execute`. The response is

```json
{"status": "ok", "explain": [<entry>, ...]}
```

with exit code `0`, and one entry per step at any depth:

```json
{"path": "pipeline.steps[1].branches[0].steps[0]", "op": "map", "reads": ["price", "qty"], "writes": ["total"], "removes": []}
```

* `path` uses the same notation as error paths; `op` is the normalized op name.
* Entries are in the order steps start: steps in order, and a `branch` step's own entry before the entries of
  the steps inside it, branch by branch (recursively for nested branches). An empty branch adds nothing.
* Column names are the normalized values of the step's fields.
* `reads`: the columns whose value or presence the step looks at in a row. This includes every column name
  used in the step's expressions (`true`, `false`, `null`, `and`, `or`, `not` and quoted strings are not
  column names). A column the step only sets, without looking at it first, is not read.
* `writes`: the columns the step may give a new value: columns it sets, overwrites or creates, columns it
  changes in place, and the new names of columns it renames. A column the step only keeps or moves, with its
  value unchanged, is not written.
* `removes`: the columns the step may delete from a row, including the old names of columns it renames and
  columns it moves into another column.
* `"*"` in a list stands for columns the step affects without naming them: every column of the row, every
  column other than the ones it names, or columns whose names come from the data.
* Each list is sorted by code point (`"*"` like any other string) and has no repeats. Steps that only drop,
  keep or add rows have empty lists, unless they evaluate expressions or look at columns.
* A `branch` step's own entry reads the column names in its `when` expressions and writes and removes nothing;
  the steps inside it have their own entries.

## Example

*Input* (with `--explain`)
```json
{
  "pipeline": {"steps": [
    {"op": "filter", "where": "qty > 0"},
    {"op": "map", "as": "total", "expr": "price * qty"},
    {"op": "rename", "from": "total", "to": "amount"},
    {"op": "group_count", "by": ["city"], "as": "orders"}
  ]},
  "dataset": []
}
```

*Output*
```json
{
  "status": "ok",
  "explain": [
    {"path": "pipeline.steps[0]", "op": "filter", "reads": ["qty"], "writes": [], "removes": []},
    {"path": "pipeline.steps[1]", "op": "map", "reads": ["price", "qty"], "writes": ["total"], "removes": []},
    {"path": "pipeline.steps[2]", "op": "rename", "reads": ["total"], "writes": ["amount"], "removes": ["total"]},
    {"path": "pipeline.steps[3]", "op": "group_count", "reads": ["city"], "writes": ["orders"], "removes": ["*"]}
  ]
}
```
