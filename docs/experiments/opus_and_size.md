# Opus as the extender, and a size-matched check

Both use the shipped grader (pure syntax nodes, snapshot alignment, final snapshot) and the ETL task's
three independent changes. Effort = reading until each hidden test passed for good; lower = easier.

## Opus 5.5 as the extender (1 run per cell)

| variant | limits | sub-pipelines | trace | verdict vs reference |
|---|---|---|---|---|
| reference | 2,277 | 4,455 | 4,724 | |
| control: same code + "you're done" note | 2,794 | 5,280 | 4,861 | (control) |
| dead code | 3,220 | 8,155 | 7,759 | harder |
| duplicated logic | 4,402 | 6,679 | 7,190 | harder |
| needless indirection | 3,700 | 5,890 | 5,513 | harder |
| junk names | 4,462 | 5,599 | 4,492 | harder |
| golfed | 2,092 | 1,983 | 2,219 | **easier** |

11/15 per-change comparisons go the right way. Opus reads compressed code so efficiently that counting
syntax nodes doesn't make up for it, so golf remains an open exploit with a strong extender.

## Size-matched check (Haiku, 2 runs per cell)

Same behaviour (identical 115/117 milestone tests passing), three sizes:

| variant | syntax nodes | limits | sub-pipelines | trace |
|---|---|---|---|---|
| golfed (smaller, worse) | 2,670 | 3,458 | 7,466 | 3,769 |
| reference | 3,291 | 4,316 | 5,437 | 4,438 |
| expanded (bigger, cleaner: helper functions, type hints, docstrings) | 3,609 | 4,837 | 7,095 | 22,919* |

\* one of the two trace runs failed 3 of 9 tests, which are charged the failure cost.

The bigger-but-cleaner refactor was rated harder on all three changes, and the golfed copy came out about
equal overall. On this task the reward still mostly tracks size, not quality.
