# Benchmark: Claude models as builders

Claude Opus 5.5, Sonnet 5.5 and Fable 5.1 each built `etl_pipeline` 3 times in Claude Code. Opus 5.5 was the
only extender, with one run per change. The runs are in [`data/bench`](../../data/bench) and can be
re-graded or extended with more extenders without rebuilding (see [BENCHMARK](../BENCHMARK.md)).

| builder | F | reward ×100 (range) | effort: limits | effort: sub-pipelines | effort: trace | lines | files | syntax nodes |
|---|---|---|---|---|---|---|---|---|
| Opus 5.5 | 0.98 | 1.63 (1.53–1.86) | 2,054 | 7,742 | 2,170 | 611–638 | 2–7 | 3,895 |
| Sonnet 5.5 | 0.98 | 1.58 (1.58–1.62) | 2,147 | 5,580 | 4,572 | 413–459 | 1 | 3,221 |
| Fable 5.1 | 0.98 | 1.37 (1.29–1.48) | 5,144 | 10,150 | 2,906 | 738–857 | 1 | 4,952 |

Effort and size are medians over the 3 builds.

## Findings

- **Correctness doesn't separate them.** Every build passes 97–99% of the milestone tests, and the
  extender completed every change on every build. The ranking comes from effort alone.
- **Fable's code was the hardest to change, on all 3 builds.** It writes the most code (about twice
  Sonnet's lines, 1.5× the syntax nodes), all in one file, and the extender read the most before each
  change passed.
- **Opus and Sonnet tie overall but differ by change.** Opus splits the program into 2–7 files, and its
  cross-cutting change (trace) cost half as much reading as Sonnet's. Sonnet's single compact file was
  cheapest for adding a new capability (sub-pipelines).

## Caveats

- **Size still dominates on this task.** The order matches code size except where Opus's file split
  helped. This is the known limit of a small task ([EVIDENCE](../EVIDENCE.md) #7, #11).
- **One extender, from the same family as the builders.** Opus rating Opus's code easiest can't be told
  apart from self-preference until GPT and Gemini extenders are added.
- **3 builds per model.** Opus's range overlaps Sonnet's; Fable's doesn't overlap either.
