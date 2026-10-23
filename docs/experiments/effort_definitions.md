# What is "effort to change"? — findings (2026-10-18)

48 Haiku extender runs. Single domain (the ETL task), single extender model (Haiku 4.5).

## Answer

**Effort to change = how much the maintainer has to read before the change first works.**

`read_to_tts` = tokens of tool output the extender took in (file reads, greps, command and test
output) up to the first snapshot where the code passes ≥ 90 % of the new tests and keeps ≥ 98 %
of the old ones. Runs that never get there are charged their full reading.

| criterion | read_to_tts | best runner-up from the pre-registered bets |
|---|---|---|
| known-answer pairs (8) | **8/8** | S*diff_hunks 5.5/8, S*tts_calls 5.5/8 |
| signal / noise | **2.8** | S*diff_hunks 2.5 |
| predicts chain changes 2–4 (n = 6) | **+1.00** (weak: see caveats) | S*diff_hunks +0.94 |
| run-to-run reliability | **+0.85** | diff_hunks +0.84 |
| fooled by "you're done" note | **no** | diff-, turn- and TTS-based measures all fooled |

As a reward (superseded: the environment now uses the per-rollout `R = F × geomean(E)^(−½)`, see craftbench/reward.py): `R = F · success · (1 − λ · read_to_tts / median_in_group)`.

## What failed and why

* **Turns, tool calls, test runs: 0/8 pairs (inverted).** On easy code the agent finishes early
  and then burns its budget on cheap re-checks; on hard code each call is bigger, so it hits the
  spend cap after *fewer* turns.
* **Cost / output tokens: at or below chance.** The agent spends whatever budget it is given.
* **Outcome alone: 5.5/8.** Most degradations still get solved; pass rate saturates.
* **Lines changed / places edited / time-to-solution:** reliable and predictive, but the
  misleading maintainer note made the extender do less and these measures called that "easier".
  A policy could game them with comments.
* **Files touched / reads before first edit:** mostly count files, so they favour single-file code.

## Pre-registered predictions (effort_definitions_predictions.md) — scorecard

1. Winner S*diff_hunks / S*tts — **wrong**; reading cost won. S*diff_hunks was best at chain prediction among my bets.
2. Outcome alone ≤ 70 % pairs — **right** (69 %).
3. Raw cost / output tokens ≤ chance — **right**, and turns were worse than chance.
4. Files / reads-before-first-edit near chance on single-file mutants — **right**.
5. Note fools process measures — **right**; success-weighting did not protect them (the note caused no failures).
6. Dead code / junk names raise reading — **right for dead code (+65–70 %)**, small for junk names (+3–12 %).

## Caveats

* The `read_*` refinements (to-solution, code-only) were added **after** seeing that raw reading
  led. The whole reading family agreeing is more convincing than one lucky measure, but it needs
  a fresh confirmation run.
* Junk names and indirection raised reading only 3–12 %; the 8/8 rests on means of 2 runs.
* Chain prediction: only sonnet_natural reached a passing state on change 1; the other five are
  charged full reading and differ by < 15 %. Treat +1.00 as "consistent with", not proof.
* One extender model; one small domain; two change requests in phase 1.
* Possible hack: code whose commands print less output lowers reading. `read_code_to_tts`
  (file reads/greps only) avoids that: 8/8 pairs, chain +0.83, reliability +0.61.
* Phase 3 (Sonnet extender, second domain) was not run.

## Update: is the 90 % cutoff arbitrary? (free re-analysis of all 851 snapshots)

| measure | known pairs | signal/noise | chain pred | reliability |
|---|---|---|---|---|
| read to 70 % | 8/8 | 4.6 | +0.94 | +0.85 |
| read to 80 % | 8/8 | 5.0 | +0.94 | +0.92 |
| read to 90 % | 8/8 | 2.5 | +0.94 | +0.72 |
| read to 100 % | 8/8 | 3.0 | +0.94 | +0.76 |
| **read per test** (no cutoff) | 8/8 | 2.8 | +0.94 | +0.83 |

The ranking does not depend on the cutoff. Recommended form: **read_per_test** — for each hidden
test, tokens read when it started passing and stayed passing to the end (old tests intact);
never-passing tests are charged the run's full reading; average over tests. No free threshold,
edge cases count as much as easy cases, and correctness is folded in (no separate success term needed).

## Update: node-weighted per-test reading vs code golf (6 runs per cell)

| measure | golf vs parent, limits | golf vs parent, sub-pipelines |
|---|---|---|
| read_to_tts / read_per_test | −50% / −48% (fooled, p≈1) | −22% / −27% (fooled, p≈1) |
| nodes_read_to_tts | −10% (n.s.) | **+37%** (p = 0.005) |
| nodes_read_per_test | −6% (n.s.) | **+29%** (p = 0.03) |

Per-test vs first-90% makes no difference here; node weighting is what matters. Golf goes from
"strongly rewarded" to "neutral on small changes, penalised on bigger ones". The extender
(Haiku) genuinely isn't slowed by golfed code on the small change, so the remaining gap needs a
separate density guard rather than a better effort measure.
