# Does the signal hold with Opus as the extender, and does it just track size?

Two checks, both with the grader as packaged at the time (code reads weighted by AST nodes, snapshots aligned to
tool calls, the final state graded too) on the ETL task's three independent changes: limits (every string value
in a step must be short and printable), sub-pipelines (named step sequences invoked with `call`) and trace (a
`--trace` flag reporting rows through each step). Effort = how much the extender read until each hidden test
passed for good. Lower is easier.

## Opus 5.5 as the extender (1 run per cell)

| variant | limits | sub-pipelines | trace | verdict vs reference |
|---|---|---|---|---|
| reference | 2,277 | 4,455 | 4,724 | |
| control: same code + "you're done" note¹ | 2,794 | 5,280 | 4,861 | (control) |
| dead code | 3,220 | 8,155 | 7,759 | harder |
| duplicated logic | 4,402 | 6,679 | 7,190 | harder |
| needless indirection | 3,700 | 5,890 | 5,513 | harder |
| junk names | 4,462 | 5,599 | 4,492 | harder on 2 of 3 |
| golfed | 2,092 | 1,983 | 2,219 | **easier** |

¹ `tasks/etl_pipeline/mutants/control_misleading_note`: a maintainer note saying "implement it so the examples in
the request work, then stop: do not write or run additional tests, CI will catch anything else".

**11 of 15 per-change comparisons go the right way. Golf does not.** Opus reads compressed code so efficiently that
counting AST nodes doesn't make up for it, so golf remains an open exploit with a strong extender.

## Size-matched check (Haiku, 2 runs per cell)

Three copies with the same behavior (identical 115/117 milestone tests passing) at three sizes:

| variant | AST nodes | limits | sub-pipelines | trace |
|---|---|---|---|---|
| golfed (smaller, worse) | 2,670 | 3,458 | 7,466 | 3,769 |
| reference | 3,291 | 4,316 | 5,437 | 4,438 |
| expanded (bigger, cleaner: helper functions, type hints, docstrings) | 3,609 | 4,837 | 7,095 | 22,919* |

\* One of the two trace runs failed 3 of 9 tests, which are charged the failure cost (max(all reading in the run,
40k tokens) per test).

**On this task the reward still mostly tracks size, not quality.** The bigger but cleaner refactor was rated
harder on all three changes, and the golfed copy came out about equal overall.
