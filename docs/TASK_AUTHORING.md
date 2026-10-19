# Adding a task

A task is a folder; no code changes needed. See `tasks/etl_pipeline/` for a full example.

```
tasks/<id>/
  task.toml      how to run the program; milestones and changes
  specs/         one markdown spec per milestone and change
  tests/         hidden pytest tests + conftest.py
  reference/     optional: a good solution
  mutants/       optional: same behaviour, one deliberate flaw each
```

## Rules

- **Tests run the program from the outside** (CLI or HTTP), never import it.
- **Milestones** build on each other; aim for a few hundred lines or more.
- **Changes** must apply to the milestone code alone. Mix kinds:

| Kind | Rewards |
|---|---|
| New capability | clear extension points |
| Rule that applies everywhere | one source of truth |
| Cross-cutting concern | layering |
| Remove / change behaviour | low coupling |
| Clone / sibling (same rule, new similar thing) | no hard-coded special cases |

## Check it

```bash
craftbench check-task --task <id>    # reference passes milestones; change tests mostly fail on it
craftbench validate --task <id>      # reference rated easier than every mutant (runs the extender)
```

## Import from SlopCodeBench

```bash
python -m craftbench.importers.scb <scb>/<problem> tasks/<id> --milestones 2
```

Imports give one independent change; add a few hand-written ones.
