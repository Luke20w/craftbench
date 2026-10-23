# On a big enough task, is composable code easier to change than an if/elif chain?

`etl_pipeline_xl` grows the ETL task to 52 operations over 7 milestones. It was later replaced by
`etl_pipeline_xl_naive`, which has the same reference and mutant but writes each spec as a plain ask; the
`etl_pipeline_xl` fixture and these runs are in git history.

Its reference is composable: one small class per operation, built from shared field kinds, in 15 files. Its
`if_elif` mutant has the same behavior, written as one validation chain and one execution chain, in 7 files. Both
are ~1,400 lines and pass the same tests, but the if/elif code is denser: ≈15.9k tokens against ≈11.8k (+34% in
characters, +47% in AST nodes). This is the same pair as section 3 of [modeling scale](modeling_scale.md). Opus 5.5
made each of the 4 hidden changes on each, 3 runs per cell.

| change | reference | if/elif | if/elif vs reference |
|---|---|---|---|
| sub-pipelines (new capability) | 6,207 | 10,440 | +68% |
| trace (cross-cutting) | 2,528 | 6,322 | +150% |
| case (new step) | 4,291 | 5,133 | +20% |
| limits (rule for every field) | 4,837 | 6,129 | +27% |
| **reward ×100** | **1.52** | **1.21** | |

Effort is the mean over 3 runs. Every run completed every change.

## Findings

- **Yes: the if/elif code is harder to change on all 4 changes.** On sub-pipelines (+68%) and trace (+150%) the
  gap is well beyond the size gap (+34–47%), so structure, not amount of code, drives it. On case (+20%) and
  limits (+27%) it is within the size gap, so those two could be size alone. The small task couldn't show this.
- **Single runs aren't enough.** After one run per cell, case and limits came out the other way. The if/elif runs
  vary most (limits: 3.2k–10.1k), because the extender sometimes found the edit sites by search and sometimes
  read the whole validation file.
- **The reader's tools shape the result.** Claude Code shows only a 2 KB preview of any tool output over ~30 KB.
  So `cat` on the if/elif code's 33 KB validation file pushed Opus to `grep`, which made large files look cheaper
  than they are to understand. The composable files are all small enough to read whole.

## What it means

Rank models on the 52-operation task (now `etl_pipeline_xl_naive`) rather than `etl_pipeline`, with at least 2
extender runs per change, and treat this pair as the check every scoring change has to pass.
