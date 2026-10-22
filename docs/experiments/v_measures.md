# Which measure of change cost predicts what code really costs to own?

CraftBench's reward rests on one number per codebase: how much it costs to change (call it V). This
experiment compares ways of computing V against an answer key that none of them sees: the real cost of
maintaining each codebase through a sequence of unseen changes.

## Setup

**Task:** [`etl_pipeline_xl_naive`](../../tasks/etl_pipeline_xl_naive), the 52-operation ETL task (~8–16k
syntax nodes) with every change request rewritten as a plain ask ("we need X" / "we're seeing Y") plus the
observable contract the tests check. Nothing in any spec says how to structure the code or what comes next.

**10 starting codebases**, all passing the same milestone tests (291–292 of 294):

* the composable reference and its if/elif copy;
* four copies of the reference with one known flaw each and byte-identical behaviour on ~38k inputs:
  dead code, duplicated (inlined shared validation, ~2× the size), junk names, golfed;
* four fresh builds from the plain-language milestones: Sonnet 5.5 ×2 (single file) and Opus 5.5 ×2
  (8 and 18 files).

**Answer key (ground truth):** four held-out changes, applied in sequence, each on the previous result:
date operations (new capability), report every broken step at once (cross-cutting control flow), strict
field checking (a rule for every op), and list every op's fields (introspection). 32–42 hidden tests each,
with milestone and earlier held-out tests as the regression gate. Cost = reading until each step's tests
pass (the shipped effort rules), geometric mean over the 4 steps. Two maintainers (Opus, Sonnet) × two
independent chains each, combined by geometric mean.

**Candidates for V**, all measured on the starting code with the task's 4 probe changes, which are
different from the held-out ones:

| candidate | what it does |
|---|---|
| probe (Opus / Sonnet) | CraftBench today: a frozen extender implements each probe change on its own copy; reading until tests pass. 2 runs |
| panel | geometric mean of the Opus and Sonnet probes |
| plan-only (Sonnet) | the extender only writes a plan for each change: no edits, no tests; total reading |
| judge (Sonnet) | sees the whole codebase and the 4 changes, estimates lines to read |
| static | free metrics: size, compressibility, clone share, complexity, name quality |

**Untestable tests are dropped.** Some held-out and probe tests depend on behaviour the milestone specs
left open (for example which of a branch's problems counts as "first"). A build that legitimately chose
differently can never pass them. A test that every run on a codebase fails is left out of that codebase's
score, the same way for the answer key and for the probes. This dropped 1–5 tests per build and none on
the reference or its flawed copies.

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
| **probe, Opus (2 runs): CraftBench default** | **+0.31** | [−0.42, +0.86] | +0.41 | **no** | 3.04 |
| judge, Sonnet | +0.30 | [−0.41, +0.90] | +0.01 | no | 0.28 |
| static: syntax nodes (size) | +0.13 | [−0.57, +0.90] | – | no | 0 |

Costs are at API prices; the whole experiment was ~$100. "After removing size" correlates what's left of
each measure and of the answer key once log size is regressed out of both.

How reliable each piece is (Spearman between independent repeats):

| | ρ |
|---|---|
| answer key, all chains of round 1 vs round 2 | +0.88 |
| same maintainer, two chains: Sonnet / Opus | +0.78 / +0.56 |
| Opus maintainer vs Sonnet maintainer | +0.16 |
| probe repeat: Opus / Sonnet | +0.83 / +0.62 |

Cost to own each known flaw, relative to the reference (answer key): if/elif 1.39×, dead code 1.41×,
duplicated 1.19×, golfed 1.39×, junk names 1.82×.

Restricted to the 6 codebases nobody planted a flaw in (reference, if/elif, 4 builds): panel +0.77,
Sonnet probe +0.66, Opus probe +0.60.

## Findings

1. **Implementing the change is what makes a probe work.** Every candidate that actually makes the change
   and runs the tests (+0.58 to +0.77) beat every candidate that doesn't: plan-only, the judge and all free
   metrics (≤ +0.38, every interval includes 0). Planning without testing reads about as much but doesn't
   track the outcome.
2. **The default extender is reliable but measures the wrong thing.** Opus probes repeat well (+0.83) yet
   predict the answer key weakly (+0.31), and predict even Opus's own chains (+0.24) worse than Sonnet
   probes do (+0.44). Opus reads compressed code so efficiently that it rated golfed code *easier* than the
   reference, while both maintainers found it 1.39× more expensive to own. It also rated the Opus builds
   much harder than their owners found them.
3. **Sonnet probes were the best single measure on this definition, and also the cheapest real probe**
   (but see Robustness: the winning reader depends on how cost is counted). They catch golf, junk
   names and dead code. They miss the duplicated copy, which they (and the Sonnet maintainer) found easy
   while Opus found it expensive.
4. **Even the answer key depends on the reader.** Each maintainer is consistent with itself, but the two
   barely agree with each other (+0.16). The clearest case: the Sonnet maintainer found the Sonnet-built
   single-file code the cheapest of all, and the Opus maintainer found it clearly harder than the
   reference. "Easy to change" is partly "easy *for this reader*", so a V that serves many future
   maintainers needs a panel, as does the answer key.
5. **On large code, size no longer decides.** Size alone predicts the answer key at +0.13 (on the small
   task it was −0.99 vs effort). The cleaner-but-bigger problem from the small task mostly disappears at
   this scale, and every measure that works still works after removing size.
6. **A sequence of real changes penalizes golf and junk names.** These were the two blind spots of
   single-change probes on the small task. Over four chained changes, both cost clearly more to own.
7. **Two runs per probe matter.** One run costs about 0.1–0.15 of correlation for both the Sonnet probe and
   the panel.

## Robustness: does the answer depend on how "cost" is defined?

The answer key and the probes above both use reading until the tests pass, in syntax nodes. Recomputing the
answer key from the same runs with other definitions (no new model calls):

| answer-key definition | maintainers agree | best candidate | Opus probe | Sonnet probe | panel |
|---|---|---|---|---|---|
| reading until tests pass, syntax nodes (above) | +0.16 | Sonnet probe | +0.31 | +0.77 | +0.73 |
| all reading in the run, syntax nodes | −0.08 | Sonnet probe | +0.50 | +0.70 | +0.72 |
| all reading in the run, raw tokens | +0.49 | Opus probe | +0.93 | +0.26 | +0.76 |
| dollars | +0.38 | Opus probe | +0.77 | −0.10 | +0.39 |

The two node-weighted definitions agree with each other (ρ = +0.85), so *until the tests pass* vs *all
reading* barely matters. Counting raw tokens instead flips the winner, because golfed code really is cheaper
for Opus in raw tokens (0.85× the reference) but costs 1.41× in syntax nodes. So "golf is costly" is partly
built into the metric. Node weighting is a choice about what we want to reward, not something this
experiment can confirm. The panel is the only candidate that stays near the top under every definition.

## What this settles and what it doesn't

* **Fairly solid:** probes that implement the change and pass the tests predict long-run cost better than
  plan-only probes, judges and static metrics under every node-weighted definition. Any single reader's
  verdict is partly about that reader.
* **Not settled:** which reader. Sonnet came out ahead under the node-weighted definitions and Opus under
  raw tokens, on 10 codebases from one task. Choosing a model from this would be fitting to this sample.
  The defensible choice is a panel, and testing whether a panel generalizes needs a reader it wasn't built
  from (leave one reader out, with a third model family).
* **Not tested by this experiment:** whether reading cost is the right notion of cost at all. The answer key
  is itself LLM reading, so this validates one-shot probes as a shortcut for long-run LLM reading cost, not
  the effort metric. That needs an answer key that isn't reading: human time, defects introduced later,
  or success within a fixed budget (failures were too rare here to use).
* **Scope:** one task, 10 codebases, 2 reader models.

## Reproduce

`scripts/v_measures/`: `build.py` (builds), `run.py` (probe / plan / judge / chain runs, resumable),
`drive.sh` (the whole queue), `analyze.py` (this report, raw numbers in `v_measures_data.json`).
