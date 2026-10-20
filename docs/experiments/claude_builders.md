# Benchmark: Claude models as builders

Claude Opus 5.5, Sonnet 5.5 and Fable 5.1 each built `etl_pipeline` 3 times in Claude Code. Opus 5.5 was the
only extender, with one run per change. The runs are in [`data/bench`](../../data/bench) and can be
re-graded or extended with more extenders without rebuilding (see [BENCHMARK](../BENCHMARK.md)).

| builder | F | reward ×100 (range) | effort: limits | effort: sub-pipelines | effort: trace | lines | files | syntax nodes |
|---|---|---|---|---|---|---|---|---|
| Opus 5.5 | 0.98 | 1.80 (1.66–2.05) | 1,778 | 6,286 | 1,849 | 611–638 | 2–7 | 3,895 |
| Sonnet 5.5 | 0.98 | 1.60 (1.59–1.61) | 2,090 | 5,640 | 4,399 | 413–459 | 1 | 3,221 |
| Fable 5.1 | 0.98 | 1.45 (1.35–1.58) | 3,970 | 9,758 | 2,807 | 738–857 | 1 | 4,952 |

Effort and size are medians over the 3 builds. Scored after Opus's shell reads (`cd <dir> && cat …`) were
counted in syntax nodes like other code reads; before that fix Opus and Sonnet overlapped.

## Findings

- **Correctness doesn't separate them.** Every build passes 97–99% of the milestone tests, and the
  extender completed every change on every build. The ranking comes from effort alone.
- **Opus's code was the easiest to change, Fable's the hardest; the ranges don't overlap.** Opus splits
  the program into 2–7 files, and its cross-cutting change (trace) cost less than half Sonnet's reading.
  Fable writes the most code (about twice Sonnet's lines, 1.5× the syntax nodes), all in one file.
- **Size explains most of it.** Syntax nodes alone rank the 9 builds at ρ = 0.7 against effort. Beyond
  size, Opus's multi-file builds came out 5–29% cheaper than their size predicts.

## Caveats

- **A small task.** This is the regime where size dominates ([EVIDENCE](../EVIDENCE.md) #7, #11); see
  [`etl_pipeline_xl`](xl_calibration.md) for a task big enough that structure shows.
- **One extender, from the same family as the builders.** Opus rating Opus's code easiest can't be told
  apart from self-preference until GPT and Gemini extenders are added.
