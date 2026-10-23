# Can an LLM judge spot code that's easy to change?

The simplest way to grade craft would be to ask a model. This compares two kinds of LLM judge, and a few static
code measures, against what actually happened when an extender changed the code.

## Setup

- **Codebases.** 9 codebases with the same behaviour (milestones 1–2 of the ETL task), written in different styles:
  `ref` is SlopCodeBench's reference solution, `ref_notests` the same without its tests folder, `monolith`,
  `copypaste`, `obfuscated`, `clean` and `overengineered` are Sonnet rewrites of it in that style, and
  `haiku_natural` / `sonnet_natural` were built from the specs by that model.
- **Ground truth.** Each got one change request, checkpoint 3 of the ETL task (`branch` steps); Haiku extender,
  3 runs each. The change was easy, so 8 of 9 codebases scored 91–98%. It is also a noisy ground truth: one run's
  ranking of the codebases agrees with the mean of the other runs at only +0.51 (last row of the correlation
  table), so every ρ below should be read against that.
- **Judges.** Sonnet with no tools: a *rubric* judge scoring SOLID, DRY and similar criteria, and a *forecast*
  judge predicting the extender's success.
- **Static measures.** Lines of code, max function length, max cyclomatic complexity.

## Result

| variant | base pass | extender score (mean ± sd) | per-run | new-feature | regression | turns | lines changed | forecast score | forecast difficulty | rubric overall | LOC | files | max fn len |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| haiku_natural | 88% | 0.98 ± 0.01 | [0.98, 1.0, 0.98] | 98% | 100% | 48 | 244 | 0.44 ± 0.02 | 5.0 | 3.0 ± 0.0 | 685 | 1 | 252 |
| ref_notests | 100% | 0.98 ± 0.00 | [0.98, 0.98, 0.98] | 98% | 100% | 57 | 373 | 0.45 ± 0.05 | 5.7 | 5.0 ± 0.0 | 896 | 9 | 95 |
| ref | 100% | 0.97 ± 0.02 | [0.98, 0.94, 0.98] | 97% | 100% | 61 | 395 | 0.48 ± 0.04 | 5.3 | 5.0 ± 0.0 | 896 | 9 | 95 |
| sonnet_natural | 99% | 0.96 ± 0.02 | [0.98, 0.93, 0.98] | 96% | 100% | 35 | 117 | 0.45 ± 0.02 | 5.3 | 4.0 ± 0.0 | 338 | 1 | 62 |
| copypaste | 100% | 0.95 ± 0.03 | [0.98, 0.91, 0.98] | 95% | 100% | 55 | 562 | 0.46 ± 0.02 | 5.0 | 5.0 ± 0.0 | 906 | 8 | 95 |
| obfuscated | 100% | 0.95 ± 0.02 | [0.98, 0.95, 0.93] | 95% | 100% | 61 | 190 | 0.44 ± 0.03 | 6.0 | 3.0 ± 0.0 | 840 | 9 | 92 |
| clean | 100% | 0.92 ± 0.01 | [0.91, 0.91, 0.93] | 92% | 100% | 61 | 206 | 0.49 ± 0.02 | 5.3 | 7.0 ± 0.0 | 812 | 10 | 47 |
| monolith | 100% | 0.91 ± 0.06 | [0.82, 0.95, 0.95] | 91% | 100% | 32 | 603 | 0.39 ± 0.03 | 6.0 | 3.0 ± 0.0 | 598 | 1 | 204 |
| overengineered | 100% | 0.68 ± 0.29 | [0.91, 0.27, 0.86] | 68% | 100% | 61 | 310 | 0.40 ± 0.02 | 6.0 | 7.0 ± 0.0 | 1774 | 71 | 73 |

Rank correlation (Spearman ρ) of each predictor with the measured extender outcomes, over the 9 codebases.
Higher = predictor agrees better. Effort columns use −turns / −cost so higher is better.

| predictor | vs pass score | vs −turns | vs −cost |
|---|---|---|---|
| forecast judge: predicted score | +0.35 | −0.27 | −0.62 |
| forecast judge: predicted new-feature % | +0.36 | −0.23 | −0.51 |
| forecast judge: −difficulty | +0.57 | +0.27 | −0.14 |
| rubric judge (SOLID etc): overall | −0.33 | −0.58 | −0.60 |
| rubric judge: mean of all criteria | −0.23 | −0.70 | −0.63 |
| static: −LOC | +0.18 | +0.60 | +0.74 |
| static: −max function length | −0.43 | −0.55 | +0.02 |
| static: −max cyclomatic complexity | −0.37 | −0.90 | −0.59 |
| *baseline: one extender run vs mean of the other runs* | +0.51 | +0.79 | |

## What it means

- **The rubric judge ranks codebases backwards.** Its overall score correlates −0.33 with pass score and −0.58 /
  −0.60 with effort. With one easy change whose own repeat runs agree at only +0.51, −0.33 on pass score is weak
  evidence on its own; the negative signs on turns and cost point the same way.
- **The forecast judge is mixed.** Its −difficulty reaches +0.57 on pass score, but its predicted score and
  new-feature % correlate negatively with effort (−0.23 to −0.62).
- **Static measures are mixed.** Only −LOC tracks effort (+0.60 vs −turns, +0.74 vs −cost); none tracks pass
  score well (at most +0.18).
- **One easy change barely separates codebases.** One extender run agrees with the mean of the others at only
  +0.51 on pass score.
