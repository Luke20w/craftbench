# Free pattern check (no model calls)

Do the 6 graded codebases' design patterns line up with how cheap they were to change? Static
detection (syntax tree) + the open-source `scb-check` static-quality tool. n = 6, outcomes were already known, 4 of the
6 are deliberate styles: **descriptive only**.

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

1. **Patterns didn't pay at this size.** Compact, direct code (one file, a long if/elif on the op
   name) was cheapest to change; pattern-heavy designs were the most expensive.
2. **Size dominates.** Lines of code predicts outcomes almost perfectly here, so pattern effects
   can't be separated from brevity with this data.
3. **CraftBench and a static quality metric disagree.** The codebase scb-check calls most eroded
   (concentrated complexity) is among the cheapest to change.
4. **Spec ambiguity drowned one change.** On sub-pipelines, extenders added `"defs": {}` to the
   normalized output and broke 14 old tests in 5 of 6 runs. The spec never says whether that's
   wanted, and the regression gate turns any such break into a total failure (all 5 hit the 40k
   floor), so that change gave no gradation.

## Implications

- For patterns to *emerge*, tasks need size and change types where they pay (e.g. many new step
  types, where a registry beats an if/elif). At ~400–2,000 lines, the reward favours simple code.
- Fix the sub-pipelines spec (state the normalized output format) before calibrating scores.
- The all-or-nothing regression gate compresses scores; consider a softer penalty.
