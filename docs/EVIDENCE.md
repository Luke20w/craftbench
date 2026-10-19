# Evidence

Multi-stage CLI data-pipeline task, Claude Haiku as the extender. Raw notes in [experiments/](experiments/).

## Findings

| # | Question | Result |
|---|---|---|
| 1 | Can an LLM judge grade good code? | **No.** A SOLID/DRY rubric judge was *anti*-correlated with real outcomes (ρ = −0.33) |
| 2 | Does an extender give a usable signal? | **Yes, with varied changes.** Duplication and over-engineering clearly penalised; run-to-run agreement +0.89 |
| 3 | What's the best "effort" measure? | **Reading until the code works**: 8/8 known pairs, reliability +0.85, not fooled by a "you're done" comment |
| 4 | Do turns / cost / lines changed work? | **No.** Turns 0/8 (inverted); lines changed and turns gamed by a comment |
| 5 | Does the 90% cutoff matter? | **No.** 70–100% and per-test all 8/8; we use per-test (no threshold) |
| 6 | Can golfed code fool it? | **Raw reading yes** (−22 to −50%). **Measured in syntax nodes: partly fixed** (+29% on the big change, −6% n.s. on the small one) |
| 7 | Does the packaged reward reproduce this? | **Yes.** Reference beats 5/5 degraded copies; 9/10 per change |
| 8 | Does it reward design patterns? | **Not at this size.** At 400–2,000 lines, compact direct code was cheapest to change; size dominates ([notes](experiments/pattern_check.md)) |
| 9 | Does it reward good modeling (a few composable concepts) at equal size? | **Not below ~7k tokens:** the extender reads the whole file, so reading tracks file length. **Yes at ~12–16k tokens across files:** an if/elif version needed +93% / +149% more reading on 2 of 3 change types (+74% overall, size gap +34%) ([notes](experiments/modeling_scale.md)) |
| 10 | Does the env's grader reproduce #9? | **Yes**, +102% overall on the same runs (case +111%, sub-pipelines +193%, limits +33%). A floored variant that charges comments as tokens gave +80%; part of the difference is that the composable version is better documented, which pure node counting doesn't charge for |
| 11 | Does splitting one big file into modules pay off at ~22k tokens (circuit_eval, same code)? | **Yes:** the one-file version needed +68–141% more reading. Descriptive names didn't matter. With a 200-line reading window the direction flipped (small n), so what gets rewarded depends on how the extender reads |
| 12 | Does a clean fixture tempt agents to special-case (`if name == X`) instead of using the existing model? | **No:** 18/18 Haiku and Sonnet runs used the model correctly. Catching special-casing needs realistic pressure (legacy special cases, size, weak docs); hidden "clone/sibling" tests do catch it when it happens |

Predictions for #3 were written down before running ([PREDICTIONS.md](experiments/PREDICTIONS.md)),
including some that turned out wrong.

## Validation (`craftbench validate --recorded data/recorded/etl_pipeline`)

| variant | effort: limits | effort: sub-pipelines | verdict |
|---|---|---|---|
| reference | 4,268 | 5,921 | |
| misleading note (same code) | 4,232 | 5,538 | ≈ reference ✓ |
| dead code | 7,187 | 10,655 | harder ✓ |
| duplicated logic | 6,987 | 9,068 | harder ✓ |
| golfed | 4,112 | 8,832 | harder ✓ |
| needless indirection | 4,542 | 9,157 | harder ✓ |
| junk names | 4,746 | 9,533 | harder ✓ |

Grader check (2026-10-19), all free re-scoring of recorded runs:
- **Snapshot alignment fixed.** The snapshot hook doesn't fire for failed tool calls (43 of 44 recorded
  runs had some, 10.7 per run on average), so snapshot *k* is the k-th *successful* call. The grader now
  maps it back to the transcript. Most gaps above grew by a few points; verdicts didn't change.
- **Code is measured in syntax nodes** (no floor), per file, for Read, Grep/Glob and shell commands that
  print source. A floored variant (charge tokens or nodes, whichever is larger) gave the same validation
  verdicts; pure nodes was kept because it's simpler and doesn't reward stripping comments.
- **Auto-loaded instruction files** (CLAUDE.md, AGENTS.md) are now charged as read; before, the policy
  could hand the extender free context.
- **Final snapshot.** The extender's last edit can happen in a failed tool call, which the hook skips, so
  the final workspace is always snapshotted too.

## Caveats

- Small n; one domain; one extender model.
- Degraded copies are mostly *longer*, so part of the signal may be brevity. Size-matched tests (#9) show
  reading rewards structure beyond size only once codebases are too big to read in one go.
- The final measure's refinements were chosen after seeing data; needs a fresh confirmation run.
- Below ~7k tokens an LLM reader takes in the whole codebase, so structure inside it is invisible (#9).
- Untested attacks: pre-building hidden changes, stripping comments, prompt injection.
