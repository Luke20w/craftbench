# Do classic design patterns go with code that's easier to change?

A free check, with no model calls. For the 6 graded codebases, we detected design patterns from the syntax tree
and ran the open-source `scb-check` static-quality tool, then compared both with how cheap each codebase was to
change. This is **descriptive only**: n = 6, the outcomes were already known, and 4 of the 6 are deliberate styles.

The two outcome columns come from earlier Haiku runs on the ETL task. **Single-change score** is the mean pass
score (new-feature pass rate × old tests retained) over the independent runs of [change mix](change_mix.md) and
its repeat runs (sub-pipelines, limits, trace). **Chain score** is the mean score on changes 2–4 of the
four-change sequence in [effort definitions](effort_definitions.md) (sub-pipelines → limits → trace → libraries).

| codebase | LOC | erosion (scb) | dispatch tables | longest op if/elif | classes | ABC classes | single-change score | chain score |
|---|---|---|---|---|---|---|---|---|
| sonnet_natural | 409 | 0.82 | 1 | 6 | 2 | 0 | 0.99 | 0.96 |
| haiku_natural | 828 | 0.88 | 0 | 6 | 1 | 0 | 0.95 | 0.95 |
| monolith | 834 | 0.99 | 2 | 6 | 2 | 0 | 0.95 | 0.92 |
| copypaste | 1042 | 0.47 | 3 | 6 | 10 | 0 | 0.62 | 0.90 |
| clean | 971 | 0.36 | 2 | 1 | 11 | 0 | 0.78 | 0.62 |
| overengineered | 1933 | 0.24 | 2 | 1 | 100 | 27 | 0.49 | 0.84 |

Rank correlation with outcomes (+ = goes with easier-to-change code):

| indicator | single-change | chain |
|---|---|---|
| lines of code | −0.99 | −0.83 |
| classic pattern signals (dispatch tables, classes, ABCs, named Factory/Visitor/…) | −0.4 to −0.8 | −0.4 to −0.8 |
| long if/elif switch on op name | +0.63 | +0.83 |
| scb-check erosion (higher = "worse" by that tool) | +0.75 | +0.71 |

## Findings

- **Patterns didn't pay at this size.** Compact, direct code (one file, a long if/elif on the op name) was
  cheapest to change. Pattern-heavy designs were the most expensive.
- **Size dominates.** Lines of code predicts outcomes almost perfectly, so this data can't separate the effect of
  patterns from brevity.
- **CraftBench and a static quality tool disagree.** The codebase scb-check calls most eroded (concentrated
  complexity) is among the cheapest to change.
- **An ambiguous spec drowned one change.** On sub-pipelines, extenders added `"defs": {}` to the normalized
  output and broke 14 old tests in 5 of 6 runs. The spec didn't say whether that's wanted. The regression gate
  (snapshots count only while ≥ 98% of old tests pass) turns any such break into a total failure: every test is
  charged the failure cost, max(all reading in the run, 40k tokens) (`FAILURE_TOKENS` in `craftbench/effort.py`).
  All 5 runs got that charge, so that change gave no gradation.

## What it means

- **Patterns need room to pay.** For them to emerge, tasks need the size and kinds of change where they win
  (e.g. many new step types, where a registry beats an if/elif). At ~400–2,000 lines, the reward favors simple code.
- **Sub-pipelines spec: fixed.** It now says `normalized` includes `defs` only when the request has `defs`
  (`tasks/etl_pipeline/specs/subpipelines.md`).
- **The all-or-nothing regression gate compresses scores.** Whether a softer penalty for broken old tests would
  give more gradation without rewarding regressions is an open question.
