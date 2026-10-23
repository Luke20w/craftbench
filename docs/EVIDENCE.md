# Evidence

Every result so far, grouped by question. Setup, predictions and raw tables are in each write-up.

## What to measure

| # | Question | Result | Write-up |
|---|---|---|---|
| 1 | Can an LLM judge spot code that's easy to change? | **No.** A SOLID/DRY rubric was anti-correlated with the real outcome (ρ = −0.33) | [judge](experiments/judge_vs_extender.md) |
| 2 | Does one easy change separate codebases? | **No.** 8 of 9 scored 91–98%; repeat runs agreed at +0.51 | [judge](experiments/judge_vs_extender.md) |
| 3 | Do different kinds of change? | **Yes.** Scores spread 0.52–0.98, repeats agreed at +0.89; each kind exposed a different flaw | [change mix](experiments/change_mix.md) |
| 4 | What should effort mean? | **Reading until the tests pass**: 8/8 known pairs. Turns were inverted, cost flat, lines changed fooled by a "you're done" comment | [effort](experiments/effort_definitions.md) |
| 5 | Does compressed code fool it? | **Raw tokens, yes** (22–50% easier). **Syntax nodes, mostly not** (+29% on the bigger change, n.s. on the small one) | [golf](experiments/golf_confirmation.md) |
| 6 | Must the extender make the change? | **Yes.** Implementing probes predict long-run cost at +0.58 to +0.77; plans, a judge and static metrics ≤ +0.38 | [V measures](experiments/v_measures.md) |
| 7 | Can defects be an answer key that isn't reading? | **Not with additive changes**: 0 broken answers in 50 chains. Needs changes that modify behaviour | [follow-ups](experiments/review_followups.md) |

## Size and structure

| # | Question | Result | Write-up |
|---|---|---|---|
| 8 | Design patterns at 400–2,000 lines? | **No.** Lines of code alone predicted cost (ρ = −0.99) | [patterns](experiments/pattern_check.md) |
| 9 | Composable vs if/elif, one file ≤ 7k tokens? | **No.** The extender reads the whole file; reading tracks length | [scale](experiments/modeling_scale.md) |
| 10 | …at 12–16k tokens across files? | **Yes.** if/elif needed +74% more reading (size gap +34%) | [scale](experiments/modeling_scale.md) |
| 11 | One file vs modules at ~22k tokens, same code? | **Modules win**: one file needed +68–141% more | not archived |
| 12 | Small task, size-matched: cleaner but longer? | **Rated harder** on all 3 changes. Small tasks reward size | [opus + size](experiments/opus_and_size.md) |
| 13 | 52 operations, composable vs if/elif, same size? | **Composable wins all 4 changes** (+20% to +150%); single runs disagreed on 2 | [XL calibration](experiments/xl_calibration.md) |
| 14 | Does size decide on large code? | **No**: ρ = +0.13 with long-run cost | [V measures](experiments/v_measures.md) |
| 15 | Known right structure (renderer, 6 organizations): does the preference flip with the changes? | **Yes, unevenly.** Wrong axis cost 2.5–4.2× on new formats; the right axis saved only 13–21% on new kinds, where edits are the same everywhere and agents script them | [axes](experiments/structure_axes.md) |
| 16 | Does it reward an abstraction that compresses the domain? | **No, it penalizes it**: 1.4–1.7× more reading despite the smallest code and edits | [axes](experiments/structure_axes.md) |
| 17 | Does stating or enforcing an invariant save reading? | **No.** Sonnet already trusts the design; Opus reads every op regardless | [follow-ups](experiments/review_followups.md) |
| 18 | Does a clean fixture tempt special-casing (`if name == X`)? | **No**: 18/18 runs used the model | not archived |

## Readers

| # | Question | Result | Write-up |
|---|---|---|---|
| 19 | Is one reader consistent? | **Yes.** 96–98% of effort variance on bigger changes comes from the code | [reliability](experiments/opus_reliability.md) |
| 20 | Do readers agree? | **No.** Opus rates golfed code 2× easier. Opus probes predict long-run cost at +0.31, Sonnet at +0.77; the two maintainers agree at +0.16 | [V measures](experiments/v_measures.md) |
| 21 | A third family (Codex)? | **Each reader predicts itself best** (Codex → Codex +0.92, Sonnet → Codex +0.01). A three-family panel predicts the three-maintainer cost at +0.83 | [follow-ups](experiments/review_followups.md) |
| 22 | Does it agree with a human? | **8 of 10 blind pairs** for the three-family panel; single readers 5–6 | [V measures](experiments/v_measures.md) |

## As a reward

| # | Question | Result | Write-up |
|---|---|---|---|
| 23 | Does the packaged grader reproduce the experiments? | **Yes**, [below](#validation) | |
| 24 | Can it be gamed? (9 exploits) | **Three worked, all fixed**: pre-built changes ×7.1 → ×0.37, unparseable files ×2.9 → ×0.93, docstring padding ×1.29 → ×1.01 | [exploits](../tasks/etl_pipeline_xl_naive/exploits/README.md) |
| 25 | Can notes steer the extender? | **Not at this size**; telling it to ignore notes added 16–42% reading | [follow-ups](experiments/review_followups.md) |
| 26 | What does an optimizer told to game it do? | **Writes clean code**, as cheap to own as the reference | [V measures](experiments/v_measures.md) |
| 27 | Does best-of-3 selection make code cheaper to own? | **No** | [V measures](experiments/v_measures.md) |
| 28 | Can it rank near-identical rollouts? | **Not yet**: siblings differ by less than one measurement's noise (~10–15%) | [V measures](experiments/v_measures.md) |
| 29 | Do real open-source refactors agree? | **Inconclusive**: real changes needed too little reading | [V measures](experiments/v_measures.md) |
| 30 | Does it predict real project history? | **Not in a 21-module pilot** | [V measures](experiments/v_measures.md) |
| 31 | Does it carry over to docs? | **Not yet**: README cost tracked length | [V measures](experiments/v_measures.md) |
| 32 | Benchmark of Claude builders (small task) | **Opus > Sonnet > Fable**, mostly following size | [builders](experiments/claude_builders.md) |

## Validation

`craftbench validate --task etl_pipeline --recorded data/recorded/etl_pipeline` re-grades recorded Haiku runs with
the current grader, no model calls:

| variant | effort: limits | effort: sub-pipelines | reward ×100 |
|---|---|---|---|
| reference | 5,018 | 5,922 | 1.33 |
| misleading note (same code) | 5,039 | 5,603 | 1.35 |
| dead code | 8,476 | 10,684 | 1.01 |
| duplicated logic | 8,383 | 9,229 | 1.05 |
| golfed | 4,596 | 8,557 | 1.24 |
| needless indirection | 5,479 | 9,292 | 1.16 |
| junk names | 5,578 | 9,533 | 1.15 |

Every flawed copy scores lower; 9 of 10 per-change comparisons go the right way (golf on `limits` doesn't).

## Caveats

- Two domains; Claude and Codex readers.
- The answer key is LLM reading too; checks outside that loop (#7, #29–30) are null so far.
- Counting syntax nodes rather than tokens is a choice, and it decides whether golf is costly (#5, #20).
- Older write-ups predate later grader fixes; their numbers shift by a few percent.
