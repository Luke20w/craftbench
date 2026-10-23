# Do different kinds of change separate codebases?

With one easy change, 8 of 9 codebases scored near the ceiling and repeat runs agreed on their ranking at only +0.51
([judge vs extender](judge_vs_extender.md)). This asks whether three change requests of different kinds do better.

## Setup

- **Codebases.** 6 of the [judge vs extender](judge_vs_extender.md) codebases, as one of that experiment's
  extender runs left them after adding checkpoint 3 (C3: `branch` steps, milestone 3 of the ETL task). C1–C3 are
  the ETL task's first three milestones.
- **Changes.** Sub-pipelines (a new capability: named step sequences invoked with `call`), limits (a rule applied
  everywhere: every string value in a step must be short and printable) and trace (cross-cutting: a `--trace`
  flag reporting rows through each step). Specs are in `tasks/etl_pipeline/specs/`.
- **Extender.** Haiku, 40 turns, 2 runs per change. 36 runs, $9.94; no run peeked at the hidden tests.
- **Score.** New-feature pass fraction × regression retained (against the base's own C1–C3 pass count).

## Result

Overall per base, mean over change requests and runs (per-run scores in parentheses):

| base | score | sub-pipelines | limits (rule everywhere) | trace (cross-cutting) | turns | lines changed | files changed | hit turn cap |
|---|---|---|---|---|---|---|---|---|
| sonnet_natural | **0.98** | 1.00 (1.00, 1.00) | 1.00 (1.00, 1.00) | 0.94 (1.00, 0.89) | 37 | 69 | 4.5 | 4/6 |
| haiku_natural | **0.98** | 1.00 (1.00, 1.00) | 1.00 (1.00, 1.00) | 0.94 (0.89, 1.00) | 32 | 136 | 2.3 | 3/6 |
| monolith | **0.95** | 0.85 (0.88, 0.83) | 1.00 (1.00, 1.00) | 1.00 (1.00, 1.00) | 39 | 117 | 5.3 | 4/6 |
| clean | **0.77** | 0.41 (0.04, 0.77) | 1.00 (1.00, 1.00) | 0.89 (0.89, 0.89) | 40 | 150 | 4.3 | 5/6 |
| copypaste | **0.70** | 0.26 (0.36, 0.16) | 0.85 (0.85, 0.85) | 1.00 (1.00, 1.00) | 36 | 174 | 6.5 | 4/6 |
| overengineered | **0.52** | 0.00 (0.00, 0.00) | 0.90 (0.95, 0.85) | 0.67 (0.67, 0.67) | 41 | 149 | 6.3 | 6/6 |

Per change request, each run as new-feature pass · regression retained · turns:

| base | subpipelines | limits | trace |
|---|---|---|---|
| sonnet_natural | 17/17 · 100% · 41t ; 17/17 · 100% · 41t | 20/20 · 100% · 41t ; 20/20 · 100% · 41t | 9/9 · 100% · 25t ; 8/9 · 100% · 33t |
| haiku_natural | 17/17 · 100% · 41t ; 17/17 · 100% · 41t | 20/20 · 100% · 41t ; 20/20 · 100% · 38t | 8/9 · 100% · 15t ; 9/9 · 100% · 17t |
| monolith | 17/17 · 88% · 41t ; 16/17 · 88% · 41t | 20/20 · 100% · 39t ; 20/20 · 100% · 41t | 9/9 · 100% · 41t ; 9/9 · 100% · 31t |
| clean | 3/17 · 24% · 41t ; 15/17 · 88% · 41t | 20/20 · 100% · 41t ; 20/20 · 100% · 41t | 8/9 · 100% · 41t ; 8/9 · 100% · 36t |
| copypaste | 7/17 · 88% · 41t ; 3/17 · 88% · 41t | 17/20 · 100% · 41t ; 17/20 · 100% · 41t | 9/9 · 100% · 25t ; 9/9 · 100% · 25t |
| overengineered | 0/17 · 0% · 41t ; 0/17 · 100% · 41t | 19/20 · 100% · 41t ; 17/20 · 100% · 41t | 6/9 · 100% · 41t ; 6/9 · 100% · 41t |

## What it means

**A mix of changes separates codebases, and repeatably.** Scores spread from 0.52 to 0.98, and run 0 vs run 1 agree
on the base ranking at +0.89 for score and +0.88 for turns (Spearman), against +0.51 with the single easy change.
Sub-pipelines does most of the separating (0.00 to 1.00 across bases); limits and trace move scores less.
