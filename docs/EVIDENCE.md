# Evidence

Every result so far, grouped by question. Setup, predictions and raw tables are in each write-up. The runners,
fixtures and raw runs behind them (`scripts/`, `data/bench/`, `tasks/etl_pipeline_xl/`, and the exploit, trust-gap,
held-out and big-change fixtures of `etl_pipeline_xl_naive`) aren't part of the package; they're in git history at
commit `150eb05`.

## What to measure

| # | Question | Result | Write-up |
|---|---|---|---|
| 1 | Can an LLM judge spot code that's easy to change? | **No.** A SOLID/DRY rubric was anti-correlated with one easy change (ρ = −0.33), and scored +0.30 against long-run cost (#6) | [judge](experiments/judge_vs_extender.md) |
| 2 | Does one easy change separate codebases? | **No.** 8 of 9 scored 91–98%; repeat runs agreed at +0.51 | [judge](experiments/judge_vs_extender.md) |
| 3 | Do different kinds of change? | **Yes.** Scores spread 0.52–0.98, repeats agreed at +0.89; each kind exposed a different flaw | [change mix](experiments/change_mix.md) |
| 4 | What should effort mean? | **Reading until the tests pass**: 8/8 planted-flaw pairs (Haiku, counting tokens). Turns were inverted, cost flat, lines changed fooled by a note telling the maintainer to stop early | [effort](experiments/effort_definitions.md) |
| 5 | Does compressed code fool it? | **Raw tokens, yes** (22–50% easier). **AST nodes, mostly not** (+29% on the bigger change, n.s. on the small one) | [golf](experiments/golf_confirmation.md) |
| 6 | Must the extender make the change? | **Mostly.** Sonnet probes and the panel predict long-run cost at +0.58 to +0.77; plans, a judge and static metrics ≤ +0.38. Opus probes did no better (+0.31). Round-1 rules, see caveats | [V measures](experiments/v_measures.md) |
| 7 | Can defects be an answer key that isn't reading? | **Not with additive changes**: 0 broken answers in 50 chains. Needs changes that modify behaviour | [follow-ups](experiments/review_followups.md) |

## Size and structure

| # | Question | Result | Write-up |
|---|---|---|---|
| 8 | Design patterns at 400–2,000 lines? | **No.** Lines of code alone predicted cost (ρ = −0.99) | [patterns](experiments/pattern_check.md) |
| 9 | Composable vs if/elif, one file ≤ 7k tokens? | **No.** The extender reads the whole file; reading tracks length | [scale](experiments/modeling_scale.md) |
| 10 | …at 12–16k tokens across files? | **Yes.** if/elif needed +74% more reading (size gap +34%) | [scale](experiments/modeling_scale.md) |
| 11 | One file vs modules at ~22k tokens, same code? | **Modules win**: one file needed +68–141% more | not archived |
| 12 | Small task, size-matched: cleaner but longer? | **Rated harder** on all 3 changes. Small tasks reward size | [opus + size](experiments/opus_and_size.md) |
| 13 | 52 operations, composable vs if/elif (if/elif +34% larger)? | **Composable wins all 4 changes** (+20% to +150%), but only 2 by more than the size gap; single runs disagreed on 2 | [XL calibration](experiments/xl_calibration.md) |
| 14 | Does size decide on large code? | **No**: ρ = +0.13 with long-run cost | [V measures](experiments/v_measures.md) |
| 15 | Known right structure (renderer, 6 organizations): does the preference flip with the changes? | **Yes, unevenly.** Wrong axis cost 2.5–4.2× on new formats; the right axis saved only 13–21% on new kinds, where edits are the same everywhere and agents script them | [axes](experiments/structure_axes.md) |
| 16 | Does it reward an abstraction that compresses the domain? | **No, it penalizes it**: 1.4–1.7× more reading despite the smallest code and edits; still 1.08–1.14× with the abstraction rewritten to be read, at best break-even (0.70 / 1.01) on the changes it centralizes, and with a maintainer that remembers (later changes become nearly free in both designs) | [axes](experiments/structure_axes.md) |
| 17 | Does stating or enforcing an invariant save reading? | **No.** Sonnet already trusts the design; Opus reads every op regardless | [follow-ups](experiments/review_followups.md) |
| 18 | Does a clean fixture tempt special-casing (`if name == X`)? | **No**: 18/18 runs used the model | not archived |

## Readers

| # | Question | Result | Write-up |
|---|---|---|---|
| 19 | Is one reader consistent? | **Yes.** 96–98% of effort variance on bigger changes comes from the code | [reliability](experiments/opus_reliability.md) |
| 20 | Do readers agree? | **No.** Opus rates golfed code 2× easier. Opus probes predict long-run cost at +0.31, Sonnet at +0.77; the two maintainers agree at +0.16 | [V measures](experiments/v_measures.md) |
| 21 | A third family (Codex)? | **Sonnet and Codex predict themselves best; Opus doesn't** (Codex → Codex +0.92, Sonnet → Codex +0.01). A three-family panel predicts the three-maintainer cost at +0.83 | [V measures](experiments/v_measures.md), [follow-ups](experiments/review_followups.md) |
| 22 | Does it agree with a human? | **8 of 10 blind pairs** for the three-family panel; single readers 5–6 | [V measures](experiments/v_measures.md) |

## As a reward

| # | Question | Result | Write-up |
|---|---|---|---|
| 23 | Does the packaged grader reproduce the experiments? | **Yes**, [below](#validation) | |
| 24 | Can it be gamed? (9 exploits) | **Three worked and were fixed**: pre-built changes ×7.1 → ×0.37, unparseable files ×2.9 → ×0.93, docstring padding ×1.29 → ×1.01. `big_file` is still open | [exploits](experiments/exploits.md) |
| 25 | Can notes steer the extender? | **Not at this size**; telling it to ignore notes added 16–42% reading | [follow-ups](experiments/review_followups.md) |
| 26 | What does an optimizer told to game it do? | **Writes clean code**, as cheap to own as the reference (one run) | [V measures](experiments/v_measures.md) |
| 27 | Does best-of-3 selection make code cheaper to own? | **No** | [V measures](experiments/v_measures.md) |
| 28 | Can it rank one policy's rollouts? | **There's nothing to rank yet**: 6 Sonnet builds from scratch, like siblings from one state, cost the same to own within noise (true spread ≤ ~13%); the probes' ranking of them is noise. Across policies it works. More changes beat more runs | [precision](experiments/precision.md) |
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
- Counting AST nodes rather than tokens is a choice, and it decides whether golf is costly (#5, #20).
- Older write-ups predate later grader fixes. Most numbers shift by a few percent, but the reader comparisons
  (#6, #20–22) move more: rescored with the current read weighting, Opus probes rise from +0.31 to +0.71, the Opus +
  Sonnet panel from +0.73 to +0.84, and the three-family panel's agreement with the human falls from 8/10 to 5/10
  ([V measures](experiments/v_measures.md#which-effort-rules-these-numbers-use)).
