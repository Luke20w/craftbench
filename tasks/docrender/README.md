# docrender

A CLI that renders a JSON document tree (20 node kinds) to 12 markup formats. Which structure is right depends
only on which changes arrive, so it tests whether the reward sees structure.

* `variants/`: the same 240 rendering rules organized six ways, byte-identical on every test. `reference` and
  `mutants` in `task.toml` point here; no variant is "the" good one.
* Changes come in three streams: `k*` new node kinds, `f*` new formats, `s*` shared behaviour.
* `gen/`: `python tasks/docrender/gen/make.py` rebuilds variants, specs and tests from one table of rules, and
  stops if any two variants differ.

Used by [structure axes](../../docs/experiments/structure_axes.md).
