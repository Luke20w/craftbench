# Can the reward rank one policy's rollouts?

Group-based RL compares rollouts of one policy on the same task, so the reward only helps if those rollouts differ
in what it measures by more than one measurement's noise. Earlier, near-identical siblings couldn't be ranked
([V measures, round 2](v_measures.md#round-2-other-readers-independent-witnesses-exploits-optimization)). Why: is
the measurement too noisy, or do the rollouts not differ?

## Setup

On `etl_pipeline_xl_naive`, Sonnet 5.5 built the task from scratch 6 times, a group from one policy. Each build got
Sonnet probes (4 changes × 2 runs) and two Sonnet answer-key chains: the answer key is long-run cost, a maintainer's
reading over the 4 held-out changes applied in sequence. The same analysis covers every earlier V-measures codebase.

All runs were rescored with the effort rules in `craftbench/effort.py` (reads weighted by the code each file holds,
never below their tokens), except the rule that tests already passing on the untouched code aren't charged (most
runs predate it), dropping tests no run on a codebase ever passed. Spread and noise are standard deviations of log
cost, shown as factors.

## Results

| codebases | probe spread | probe noise | answer-key spread | answer-key noise |
|---|---|---|---|---|
| reference + 5 flawed copies | ×1.27 | ×1.10 (panel) | ×1.17 | ×1.12 |
| 6 builds by different models and pipelines | ×1.22 | ×1.08 (panel) | ×1.22 | ×1.04 |
| 6 siblings from one milestone-6 state (each seed) | ×1.04 | ×1.08 (bigger probes, seed 0) | ×1.00–1.02 | ×1.07–1.08 |
| **6 Sonnet builds from scratch** | ×1.06 | ×1.05 (Sonnet) | **×1.00** (95% bound ×1.13) | ×1.16 |

Siblings are 6 continuations of the last milestone from the same codebase after milestone 6, for each of 2 seeds;
the bigger probes are the 3 larger probe changes used on them (explain, column types, case-insensitive columns).
Both are from [V measures, round 2](v_measures.md#round-2-other-readers-independent-witnesses-exploits-optimization).

Within the Sonnet group, probe cost ranked against answer-key cost at ρ = −0.77, which means nothing when the
answer key shows no spread.

**Where the variance comes from.** Variance of log probe effort over the 12 codebases in the first two rows:
codebase 0.032, codebase × change 0.015, codebase × reader 0.014, codebase × change × reader 0.019, run to run
0.078. As a measure of cost over *unseen* changes and readers, the default probe design (4 changes × 2 readers ×
2 runs) has reliability 0.64. The same budget spent on 8 changes × 1 run gives 0.68; 16 changes × 1 run gives 0.75.

## Findings

1. **The rollouts don't differ, so there is nothing to rank.** Six Sonnet builds from scratch cost the same to own
   within the answer key's noise (true spread at most ~13%), and so do within-seed siblings. The probes still rank
   them, by reader- and probe-specific differences that don't carry over to long-run cost. As a group-RL reward on
   this task, that ranking would be noise.
2. **Across policies, it works.** Builds by different models and pipelines differ by ~20% in cost to own, and both
   the probes and the answer key measure that reliably (answer-key reliability 0.96).
3. **More changes beat more runs.** Which changes are asked moves the probe half as much as the codebase does, so
   spend runs on more changes, not repeats.
4. **Batch effects are real.** Stored efforts mixed grader versions: one sibling's two chains, scored by different
   versions, differed by up to ~50%. Rescoring removed that. A second batch of Sonnet chains still came out higher
   on all 4 builds, so interleave runs when comparing.

## Limits

One task, one policy (Sonnet, which writes one file every time), 6 builds, 2 chains each. Opus builds varied more
(8 and 18 files) and are the obvious next group.

## Runners (in git history)

In `scripts/precision/` (removed from the repo): `drive.py` (builds, probes, chains), `rescore.py` (rescores every
run with the `craftbench/effort.py` rules, no model calls), `noise.py` (spread vs noise), `components.py`
(variance components).
