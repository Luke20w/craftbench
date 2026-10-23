# Which measure of change cost predicts what code really costs to own?

CraftBench's reward rests on one number per codebase: how much it costs to change (V). This experiment compares
ways of computing V against an answer key none of them sees: long-run cost, what it really costs a model to keep
maintaining each codebase through a sequence of unseen changes.

## Setup

**Task.** [`etl_pipeline_xl_naive`](../../tasks/etl_pipeline_xl_naive), the 52-operation ETL task (~8–16k AST
nodes). Every change request is a plain ask ("we need X" / "we're seeing Y") plus the observable contract the tests
check. No spec says how to structure the code or what comes next. The held-out changes and bigger probes below were
later removed from the task (in git history).

**10 starting codebases**, all passing the same milestone tests (291–292 of 294):

- **The reference** (composable) and its if/elif copy.
- **Four flawed copies** of the reference, one known flaw each, with byte-identical behaviour on ~38k inputs: dead
  code, duplicated (shared validation inlined, ~2× the size), junk names, golfed.
- **Four fresh builds** from the plain-language milestones: Sonnet 5.5 ×2 (single file) and Opus 5.5 ×2 (8 and 18
  files).

**Answer key (long-run cost).** Four held-out changes, each applied to the previous result: date operations (new
capability), report every broken step at once (cross-cutting control flow), strict field checking (a rule for every
op), and list every op's fields (introspection). Each has 32–42 hidden tests; milestone and earlier held-out tests
gate regressions. Cost is reading until each step's tests pass (the effort rules of the time; see
[below](#which-effort-rules-these-numbers-use)), as a geometric mean over the 4 steps and over two maintainers (Opus,
Sonnet) running two independent chains (the 4 changes in sequence) each.

**Candidates for V**, all measured on the starting code with the task's 4 probe changes (not the held-out ones):

| candidate | what it does |
|---|---|
| probe (Opus / Sonnet) | as in the reward: a frozen extender implements each probe change on its own copy; reading until tests pass. 2 runs |
| panel | geometric mean of the Opus and Sonnet probes |
| plan-only (Sonnet) | the extender only writes a plan for each change: no edits, no tests; total reading |
| judge (Sonnet) | sees the whole codebase and the 4 changes, estimates lines to read |
| static | free metrics: size, compressibility, clone share, complexity, name quality |

**Untestable tests are dropped.** Some held-out and probe tests depend on behaviour the milestone specs left open
(for example which of a branch's problems counts as "first"), which a build that legitimately chose differently can
never pass. A test that every run on a codebase fails is left out of that codebase's score, for the answer key and
the probes alike: 4–7 tests per fresh build, one on the if/elif copy, none on the reference or the four flawed
copies.

## Results

| candidate | ρ vs answer key | 95% CI | after removing size | catches golf | $ per codebase |
|---|---|---|---|---|---|
| **probe, Sonnet (2 runs)** | **+0.77** | [+0.22, +0.96] | +0.85 | yes | 1.29 |
| panel, Opus + Sonnet (2 runs) | +0.73 | [+0.20, +0.99] | +0.81 | yes | 4.33 |
| probe, Sonnet (1 run) | +0.68 | [−0.02, +1.00] | +0.76 | yes | 0.65 |
| panel (1 run each) | +0.58 | [−0.04, +0.93] | +0.65 | yes | 2.17 |
| plan-only, Sonnet | +0.36 | [−0.34, +0.81] | +0.53 | yes | 0.62 |
| static: clone share | +0.38 | [−0.34, +0.80] | +0.43 | no | 0 |
| static: name quality | +0.32 | [−0.47, +0.89] | +0.60 | yes | 0 |
| **probe, Opus (2 runs): the default extender at the time** | **+0.31** | [−0.42, +0.86] | +0.41 | **no** | 3.04 |
| judge, Sonnet | +0.30 | [−0.41, +0.90] | +0.01 | no | 0.28 |
| static: AST nodes (size) | +0.13 | [−0.57, +0.90] | – | no | 0 |

Costs are at API prices; the whole experiment cost ~$100. "After removing size" regresses log size out of both the
measure and the answer key, then correlates what's left.

How well each piece repeats (Spearman between independent repeats):

| | ρ |
|---|---|
| answer key, all chains of round 1 vs round 2 | +0.88 |
| same maintainer, two chains: Sonnet / Opus | +0.78 / +0.56 |
| Opus maintainer vs Sonnet maintainer | +0.16 |
| probe repeat: Opus / Sonnet | +0.83 / +0.62 |

**Cost to own each flaw**, relative to the reference (answer key): if/elif 1.39×, dead code 1.41×, duplicated
1.19×, golfed 1.39×, junk names 1.82×.

**Without planted flaws** (the 6 codebases with none: reference, if/elif, 4 builds): panel +0.77, Sonnet probe +0.66,
Opus probe +0.60.

## Findings

1. **Making the change is what makes a probe work.** Every Sonnet probe and panel that makes the change and runs the
   tests (+0.58 to +0.77) beat every candidate that doesn't: plan-only, the judge and all free metrics (≤ +0.38, every
   interval includes 0). The Opus probe (+0.31) did not (finding 2); rescored with the later read weighting it rises
   to +0.71 and the split is clean ([below](#which-effort-rules-these-numbers-use)). Planning reads about as much but
   doesn't track the outcome.
2. **Opus, the default extender at the time, was consistent but measured the wrong thing** (under these rules).
   Opus probes repeat well (+0.83) yet predict the answer key weakly (+0.31), and predict even Opus's own chains
   (+0.24) worse than Sonnet probes do (+0.44). Opus reads compressed code so efficiently that it rated golfed code
   *easier* than the reference, while the maintainers found it 1.39× more expensive to own (Opus 1.29×, Sonnet
   1.51×). It also rated the Opus builds much harder than their owners found them.
3. **Sonnet probes were the best single measure, and the cheapest real probe** (under this definition of cost and
   these rules; see Robustness and [below](#which-effort-rules-these-numbers-use)). They catch golf, junk names and
   dead code. They miss the duplicated copy, which they and the Sonnet maintainer found easy and Opus found expensive.
4. **Even the answer key depends on the reader.** Each maintainer is consistent with itself, but the two barely
   agree (+0.16). The clearest case: the Sonnet maintainer found the Sonnet-built single-file code the cheapest of
   all; the Opus maintainer found it clearly harder than the reference. "Easy to change" partly means "easy *for
   this reader*", so a V that serves many future maintainers needs a panel, and so does the answer key.
5. **On large code, size no longer decides.** Size alone predicts the answer key at +0.13 (on the small task it was
   −0.99 vs effort). The small task's cleaner-but-bigger problem mostly disappears at this scale, and every measure
   that works still works after removing size.
6. **Chained changes penalize golf and junk names.** Single-change probes missed both on the small task. Over four
   chained changes, both cost clearly more to own.
7. **Two runs per probe matter.** One run loses about 0.1–0.15 of correlation, for both the Sonnet probe and the
   panel.

## Robustness: does the answer depend on how "cost" is defined?

Everything above counts reading until the tests pass, in AST nodes. Recomputing the answer key from the same runs
under other definitions (no new model calls):

| answer-key definition | maintainers agree | best candidate | Opus probe | Sonnet probe | panel |
|---|---|---|---|---|---|
| reading until tests pass, AST nodes (above) | +0.16 | Sonnet probe | +0.31 | +0.77 | +0.73 |
| all reading in the run, AST nodes | −0.08 | Sonnet probe | +0.50 | +0.70 | +0.72 |
| all reading in the run, raw tokens | +0.49 | Opus probe | +0.93 | +0.26 | +0.76 |
| dollars | +0.38 | Opus probe | +0.77 | −0.10 | +0.39 |

The two node-weighted definitions agree (ρ = +0.85), so *until the tests pass* vs *all reading* barely matters.
Raw tokens flip the winner: golfed code really is cheaper for Opus in raw tokens (0.85× the reference) but costs
1.41× in AST nodes. So "golf is costly" is partly built into the metric: node weighting is a choice about what to
reward, which this experiment can't confirm. Only the panel stays near the top under every definition.

## What this settles and what it doesn't

- **Fairly solid:** probes that make the change and pass the tests predict long-run cost better than plan-only
  probes, judges and static metrics, under every node-weighted definition (for Opus probes, only once rescored).
  Any single reader's verdict is partly about that reader.
- **Not settled: which reader.** Sonnet led under node weighting (level with Opus once rescored) and Opus under raw
  tokens, on 10 codebases from one task, so picking a model from this would fit the sample. The defensible choice
  is a panel; testing whether it generalizes needs a reader it wasn't built from (leave one reader out, with a third
  model family).
- **Not tested: whether reading is the right notion of cost at all.** The answer key is itself LLM reading, so this
  validates one-shot probes as a shortcut for long-run LLM reading cost, not the effort metric. That needs an answer
  key that isn't reading: human time, later defects, or success within a fixed budget (failures were too rare here
  to use).
- **Scope:** one task, 10 codebases, 2 reader models.

## Which effort rules these numbers use

The tables above, and the reader and human rows of round 2, use the effort rules of round 1 (raw numbers in
[`v_measures_data.json`](v_measures_data.json)). Two things changed afterwards.

- **One timed-out run.** One Sonnet probe run on `golfed` (change `case`) was charged as a failure (all the run's
  reading, at least 40k tokens) because its regression suite timed out under machine load at the final snapshot
  (292 → 239 old tests on code identical to the snapshot before; 292 when regraded). Regraded, it costs 10.4k, so the
  Sonnet probe rates golfed at 1.31× the reference rather than 1.72×, and still catches golf. The tables above keep
  the failure charge.
- **Read weighting.** After round 1, reads were weighted by the code each file holds and never cost less than their
  tokens (this closed the exploits in round 2). The [follow-ups](review_followups.md) rescored the same runs this
  way, with no new model calls ([`review_followups_data.json`](review_followups_data.json); the timed-out run still
  charged as a failure):

| | round-1 rules | rescored |
|---|---|---|
| probe, Sonnet (2 runs) | +0.77 | +0.70 |
| probe, Opus (2 runs) | +0.31 | +0.71 |
| panel, Opus + Sonnet (2 runs) | +0.73 | +0.84 |
| plan-only, Sonnet | +0.36 | +0.25 |
| judge, Sonnet | +0.30 | +0.55 |
| static: clone share | +0.38 | +0.35 |
| Opus maintainer vs Sonnet maintainer | +0.16 | +0.30 |
| golfed vs reference: Opus probe / answer key | 0.93× / 1.39× | 0.80× / 1.23× |

Rescored, the Opus and Sonnet probes are level, the panel leads, and every probe that makes the change beats every
candidate that doesn't. Findings 2 and 3 (Opus probes weak, Sonnet the best single measure) hold only under the
round-1 rules; Opus still rates golfed code cheaper than the reference.

## Round 2: other readers, independent witnesses, exploits, optimization

Run after the results above, on the same task, one experiment per row (runners [below](#runners-in-git-history)).

| question | result |
|---|---|
| Does a third model family (`gpt-6-astra`, run through Codex) agree? | Not much. The three maintainers' long-run costs agree at ρ = +0.16 (Opus–Sonnet), +0.37 (Opus–Codex), −0.01 (Sonnet–Codex), though each repeats itself (+0.56 to +0.82). All three agree the reference is cheapest and the planted flaws cost more. Rescored with the later read weighting, they agree at +0.30, +0.28, +0.21 ([follow-ups](review_followups.md#4-a-third-reader)) |
| Does a panel predict a reader it wasn't built from? | Weakly: +0.67, +0.22, +0.27 for the held-out Opus, Sonnet and Codex maintainer (all probe runs). A three-reader panel predicts the three-maintainer answer key at +0.83 [+0.38, +1.00], better than any single reader (+0.52 to +0.67), partly because each reader is on both sides. The [follow-ups](review_followups.md#4-a-third-reader) rescore the same runs with the later read weighting and one run per probe: +0.67, +0.47, +0.50 for the held-out reader. Rescored with all runs, the three-reader panel scores +0.87 against +0.32 to +0.79 for single readers |
| Does it agree with a human? (the author ranked 10 pairs of codebases blind) | The three-reader panel agreed on 8/10 (5/5 of the confident picks); single-reader probes on 5–6/10; the Opus maintainer's long-run cost on 9/10, the Sonnet maintainer's on 4/10. One rater, half the picks low-confidence. Rescored with the later read weighting, the panel agrees on 5/10 and single readers on 5–6/10 |
| Can it be gamed? (9 hand-built exploits, live Sonnet and Opus runs) | Three exploits worked: pre-implementing the fixed hidden changes (reward ×7.1), files that don't parse as Python (×2.9, counted as zero size) and docstring padding that diluted read weights (×1.29). All three are fixed in `effort.py`/`analysis.py` (×0.37, ×0.93, ×1.01 after); everything else stayed within ±7%. Grader-targeted notes and a maintainer guide did nothing |
| What does an optimizer that knows the scoring do? (Opus told to maximize the score by any means) | It wrote a clean table-driven design with a map for the next maintainer: the best probe scores, and as cheap to own as the reference (5.2k vs 4.8k), cheaper than all four honest builds (6.4–7.5k). One run |
| Does selecting by the reward make code better? (best of 3 Opus continuations per milestone, 2 seeds) | No: the selected codebases cost 7.2k and 8.0k to own, the plain builds 6.4k and 7.5k |
| Can it pick the better of near-identical siblings? (12 candidates for the last milestone, 6 per seed, bigger probes) | Across seeds, yes: the bigger probes (explain, column types, case-insensitive columns) track the Sonnet answer key at ρ = +0.69 [+0.23, +0.89] over all 12, where the original small probes had it backwards (−1.00 on the 6 that had both). Within a seed, nothing can: siblings' cost to own spans only 1.12–1.19×, and two clean answer-key chains rank one seed's 6 siblings at ρ = −0.20, so the differences are inside one measurement's noise. (An API outage had scored 7 runs as failures; they were removed and CraftBench now refuses to score such runs.) |
| Do real open-source changes agree? (9 expert refactors in click, arrow, pluggy, more-itertools, itsdangerous; 11 later real changes replayed before and after) | Inconclusive: the change was cheaper after the refactor in 8/22 (change, reader) cells. The real fixes needed only ~500–1,000 tokens of reading, too small to show a difference |
| Does it predict real history? (21 werkzeug modules, 2.5 years after the snapshot) | Not in this pilot: modules that cost more to change later had fewer bug fixes (ρ = −0.51) and somewhat more co-changed files (+0.36) |
| Does the idea carry over to docs? (5 READMEs, 10 use-tasks checked against the real tool) | Readers agree closely, but the cost mostly tracks README length (agents read all of a short document). No human ranked the READMEs |

**What this adds.** The measure detects large differences in how well code is built (planted flaws, the reference
against weaker builds, one trajectory's structure against another's) and, with a panel scored under the round-1
rules, agrees with a human on most of them (8/10 pairs; 5/10 rescored). It can't resolve small ones: one
measurement's noise (~10–15%) exceeds the gap between near-identical candidates, so as a per-rollout RL reward
among similar rollouts it would mostly rank noise. Bigger probes help with structural differences, not noise. The
witnesses outside the LLM loop (real history, real refactors) are so far null or slightly negative.

## Diagnosis: the idea or the parts?

Mostly the parts. Where code really was built differently, measuring the cost of an actual change found it. The
failures trace to choices inside the grader:

- **The probe changes.** Swapping the 4 small probes for 3 bigger ones (explain, column types, case-insensitive
  columns) turned the two best-of-N trajectories from ranked backwards (−1.00) to ranked right (+0.69), on the same
  code with the same grader.
- **Codebase size.** Below roughly 7–12k tokens the extender reads everything and the score tracks length; structure
  only shows above that.
- **The real-repo witnesses** used fixes that needed ~500–1,000 tokens of reading, too little for design to matter.
- **The exploits** were weighting details, now fixed.
- **Reader disagreement** may be a setting: under the round-1 rules a three-family panel matched the human better than any
  single reader (8/10 against 5–6/10). Rescored, it doesn't (5/10).

Closer to the idea itself:

- **Noise is inherent.** One extender run varies ~10–15% on the same code, so separating candidates ~5% apart takes
  on the order of 10–40 runs each, which is expensive for a per-rollout RL reward.
- **"Easy to change" is reader-relative.** A panel averages it out, but the score always means "easy for these
  readers".
- **Validation is mostly circular.** Almost every check compares LLM reading with LLM reading. The human ranking (10
  pairs, one rater) and real history (null) are the only outside witnesses so far.
- **The sibling test may have had nothing to find.** Near-identical siblings differed by 1.12–1.19× in cost to own,
  inside the noise of the answer key itself.

## What to change next

1. **Bigger, more varied probe changes**, sampled from a large pool per episode (also the structural fix for
   pre-implementation).
2. **Bigger codebases**, past the size where the extender can read everything.
3. **Several runs per candidate** over a panel of model families, accepting the cost. Measure how many runs the
   differences between real rollouts need.
4. **Tests where rollouts genuinely differ in design**, not near-identical siblings, and more non-LLM witnesses
   (more blind human rankings; real-repo changes big enough to need exploration).

If the measure still can't separate candidates after 1–3, the problem is the idea, not the parts.

## Runners (in git history)

In `scripts/v_measures/` (removed from the repo): `build.py` (builds), `run.py` (probe / bigprobe / plan / judge /
chain runs, resumable), `drive.sh` (the first round's queue), `analyze.py` (this report; raw numbers in `v_measures_data.json`),
`best_of_n.py` and `more_siblings.py` (selection), `redteam_build.py`, `readme_evolve.py` / `readme_use.py` (docs),
`realrepo_run.py` (real-repo probes, built by `realrepo/`).
