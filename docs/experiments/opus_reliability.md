# Does the extender give the same verdict run after run? (Opus, 3 runs per cell)

Opus 5.5 made all 3 changes (limits, sub-pipelines, trace) on the ETL reference and its 6 copies with the same
behavior (dead code, duplicated logic, needless indirection, junk names, golfed, and the "you're done" note
control; see [Opus and size](opus_and_size.md)), 3 independent runs each (63 runs), scored by the grader as
packaged at the time. Recorded Haiku runs (2–6 per cell, 2 changes) are shown for comparison.

## Consistency

| | Opus | Haiku |
|---|---|---|
| Share of effort variation due to the codebase (rest is run-to-run noise) | 66% / 96% / 98% (limits / sub-pipelines / trace) | 61% / 58% (limits / sub-pipelines) |
| Median run-to-run spread for the same code and change | 15% / 9% / 2% | 2% / 17% |
| Two independent runs ranking all 7 codebases (Spearman) | +0.75, +0.86, +0.82 (mean +0.81) | +0.61 |

## Does a single run get each verdict right?

A verdict is right when the flawed copy needs more effort than the reference. Each cell compares each of the 3
flawed-copy runs with each of the 3 reference runs (9 pairs).

| flaw | limits | sub-pipelines | trace |
|---|---|---|---|
| dead code | 5/9 | 9/9 | 9/9 |
| duplicated logic | 5/9 | 9/9 | 9/9 |
| needless indirection | 5/9 | 8/9 | 6/9 |
| junk names | 3/9 | 5/9 | 4/9 |
| golfed | 0/9 | 0/9 | 0/9 (about 2× easier every time) |

## What it means

- **The signal is repeatable**, especially on the bigger changes.
- **What it rewards depends on the reader.** Opus reliably penalizes structural problems (dead code,
  duplication), ignores naming, and is consistently fooled by compressed code. A panel of extenders from
  different model families should average out single-reader blind spots like these.
