# Adding a task

A task is a folder; no code changes needed. See `tasks/etl_pipeline_xl_naive/` for a full example.

```
tasks/<id>/
  task.toml      how to run the program; milestones and changes
  specs/         one markdown spec per milestone and change
  tests/         hidden pytest tests + conftest.py
  reference/     optional: a good solution
  mutants/       optional: same behaviour, one deliberate flaw each
```

`task.toml` can also list `[[held_out]]` changes (never graded in episodes; applied in sequence, they are the
answer key for what a codebase costs to own) and `[[big_changes]]` (larger probes that touch most of the
design). Both are used by experiments, not by the reward.

## Rules

- **Tests run the program from the outside** (CLI or HTTP), never import it.
- **Big enough that structure shows.** The finished reference should reach ~12k tokens across files; below
  ~7k an LLM reads everything and the reward only measures size ([EVIDENCE](EVIDENCE.md) #8–10).
- **Specs are plain asks.** Write milestones and changes the way a user would ("we need X", "we're seeing Y"),
  plus the observable contract the tests check. Don't describe the structure, list every place a change
  applies, or hint at what comes next: working that out is what's being measured.
- **Changes** must apply to the milestone code alone. Mix kinds:

| Kind | Rewards |
|---|---|
| New capability | clear extension points |
| Rule that applies everywhere | one source of truth |
| Cross-cutting concern | layering |
| Remove / change behaviour | low coupling (and a missed call site shows up as a wrong answer, #7) |
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
