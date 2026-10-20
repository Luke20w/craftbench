# Calibration: `etl_pipeline_xl`, composable vs if/elif

[`etl_pipeline_xl`](../../tasks/etl_pipeline_xl) grows the ETL task to 52 operations over 7 milestones. Its
reference is composable (one small class per operation, built from shared field kinds, 15 files); its
`if_elif` mutant has the same behaviour as one validation chain and one execution chain. Both are ~1,400
lines (~14k tokens) and pass the same tests. Opus 5.5 made each of the 4 hidden changes on each, 3 runs per
cell.

| change | reference | if/elif | if/elif vs reference |
|---|---|---|---|
| sub-pipelines (new capability) | 6,207 | 10,440 | +68% |
| trace (cross-cutting) | 2,528 | 6,322 | +150% |
| case (new step) | 4,291 | 5,133 | +20% |
| limits (rule for every field) | 4,837 | 6,129 | +27% |
| **reward ×100** | **1.52** | **1.21** | |

Effort is the mean over 3 runs. Every run completed every change.

## Findings

- **The check passes: the if/elif code is harder to change on all 4 changes**, at the same size, so the
  difference is structure rather than amount of code. This is what the small task couldn't show.
- **Single runs aren't enough.** After one run per cell, case and limits came out the other way. The
  if/elif runs vary most (limits: 3.2k–10.1k), because the extender sometimes found the edit sites by
  search and sometimes read the whole validation file.
- **The reader's tools shape the result.** Claude Code shows only a 2 KB preview of any tool output over
  ~30 KB, so `cat` on the if/elif code's 33 KB validation file pushed Opus to `grep`, which made large files
  look cheaper than they are to understand. The composable files are all small enough to read whole.

## What this means for benchmarking

Rank models on this task rather than `etl_pipeline`, with at least 2 extender runs per change, and treat
this pair as the check every scoring change has to pass.
