# Does the cost to extend see structure? A domain where the right structure is known

## Question

Earlier checks compared the reference with flawed copies (dead code, duplication, if/elif), so "good" was
whatever the reference author did. Here the right structure is known by construction. The same behaviour is
organized in different ways, and which way is right depends only on which changes arrive. If the cost to
extend measures structure, its preference should flip when the stream of changes flips.

## Setup

**Task** (`tasks/docrender`): a CLI that renders a JSON document tree (20 node kinds) to 12 markup formats
(HTML, Markdown, LaTeX, MediaWiki, Org, Jira, ...). It is a classic two-axis problem: every (kind, format) pair
needs its own rule.

**Six organizations of the same rules**, generated from one table of 240 rendering rules (`gen/`), and
checked byte-identical on all 122 hidden tests:

| variant | structure | size (AST nodes) |
|---|---|---|
| by_kind | a class per node kind, a method per format | 7.4k |
| by_format | a renderer class per format, a method per kind | 7.1k |
| families | by_format, plus a base class for the 9 line-based markups, which become marker settings | 5.6k |
| families_explicit | the same abstraction, written to be read: each format lists every setting in one table, no inherited defaults (follow-up) | 5.8k |
| flat | one module: `if kind`, then `if format` | 7.0k |
| layered | by_format plus registries, factories, middleware and a class per (kind, format) | 10.1k |

**Two streams of changes**, written as plain asks with the output contract:
- **K, new node kinds:** strikethrough, callouts, definition lists. Right structure: by_kind.
- **F, new formats:** AsciiDoc, Textile, reStructuredText. Right structure: by_format, ideally families
  (all three are line-based markups).
- **S, changes to shared behaviour** (follow-up): lists that start from a given number, quote attributions,
  and alt text defaulting to the file name. Each adds an optional field. In families most of each change is
  one edit in the shared base class; in by_format it is one edit per format; in by_kind and flat it is one
  node kind's code.

**Runs:** every variant × change, Opus 5.5 and Sonnet 5.5 as extenders, 2 runs each: 216 runs. All 216
passed every test, so only effort differs. Run-to-run noise: the median ratio between repeat runs was 1.11.

Predictions were written before the results ([below](#predictions)).

## Results

Reading (CraftBench's effort) relative to by_format, geomean over each stream's three changes:

| variant | K, Opus | K, Sonnet | F, Opus | F, Sonnet |
|---|---|---|---|---|
| by_format | 1.00 | 1.00 | 1.00 | 1.00 |
| by_kind | **0.79** | **0.87** | 2.49 | 4.23 |
| families | 1.66 | 1.49 | 1.36 | 1.65 |
| families_explicit | 1.85 | 1.70 | 1.47 | 1.81 |
| flat | 1.33 | 1.26 | 3.35 | 3.31 |
| layered | 1.36 | 0.92 | 1.56 | 1.88 |

**1. The preference flips with the stream, but unevenly.** On new formats, by_kind cost 2.5–4.2× more to
extend than by_format, in all 24 run pairs, for both readers. On new kinds, by_kind was cheaper, but only by
13–21% (18 of 24 run pairs). The transcripts show why the effect is lopsided:
- **Adding a kind to by_format** means adding one method to each of 12 renderers. The extenders wrote one
  script or `sed` loop that inserted the method into every file, after reading one or two renderers. Edits
  that are the same everywhere are cheap for an agent with a shell, however scattered.
- **Adding a format to by_kind** means writing a method in each of 20 node classes, and each one depends on
  that node's fields and children. The extender had to read every class: 1.1× the whole codebase.

So the measure sees the cost of edits that are scattered *and* need understanding, not scatter on its own.

**2. Missing structure costs on both streams.** flat cost 1.3× on K and 3.3× on F. (The stream it is
aligned with by locality, K, still cost more, because its single 9k-token file is read whole.)

**3. Spurious structure mostly costs.** layered cost 1.6–1.9× on F. On K it was 1.36× (Opus) and 0.92×
(Sonnet).

**4. The deeper model is penalized.** families is the smallest codebase. It encodes a real fact about the
domain: most markup formats are the same shapes with different markers. It also needed the smallest changes
(0.60–0.79× the tokens). But it cost 1.4–1.7× more reading on both streams, even on new formats, where it
should do best. To add a format the extender had to learn the base class's ~25 settings and hooks, and to add a kind
it had to see each format's settings, including defaults inherited implicitly from Markdown.

**5. Making the abstraction easier to read didn't help.** A second version, families_explicit, keeps the
abstraction but removes what looked hard to read: every format spells out all of its settings in one table,
nothing is inherited from Markdown, and each format's exceptions are listed apart. It cost slightly *more*
reading than families (1.08–1.14× on every stream and reader, within the 15% that the pre-registered
prediction set for "the abstraction itself costs"). In two independent writings, the abstraction that
compresses the domain cost 1.4–1.9× more to read than one plain class per format. This probably won't change
over a longer stream: in both designs, adding a format means reading a fixed amount (a sibling format, or the
base class and a sibling), so the abstraction's reading cost recurs on every change rather than paying off.

**6. Even on the changes it centralizes, the abstraction barely pays back.** Stream S, reading relative to
by_format (Opus / Sonnet): families 0.70 / 1.01, families_explicit 1.44 / 1.15, by_kind 0.73 / 0.85, flat 0.61 /
0.98, layered 1.45 / 1.17. families touched 0.6× the files and wrote 0.85× the code, but only Opus read less,
and the explicit version read more for both. Each of these changes concerns one node kind, so the code
organized by kind (by_kind, and flat, whose outer branch is the kind) was as cheap or cheaper. Repeat runs
were noisier here (one by_format cell was 5.4k and 1.7k), so these are rougher than the K and F results.

**7. No single alternative measure works.** Tokens of code changed rate by_kind the same as by_format on
*both* streams (0.97–0.98×), because the work is the same amount wherever it lives. That measure doesn't see locality at
all, though it does reward the deeper model. Files touched sees locality exactly (by_kind 0.17× on K, 10.5×
on F), but it rates flat best on both streams (1 file), which is wrong.

**8. Memory doesn't rescue the abstraction; it removes later reading for both designs.** The three new
formats applied in sequence on by_format and families (Sonnet ×2, Opus ×1). *Fresh*: a new extender per step.
*Memory*: one resumed session, charged only for each step's own reading.

| families / by_format, total over 3 steps | fresh | memory |
|---|---|---|
| reading | 1.61, 1.61, 1.62 | 1.72, 1.83, 0.91 |
| output tokens (reasoning and edits) | 1.03, 0.97, 1.01 | 1.26, 1.20, 0.78 |
| code changed | 0.61, 0.63, 0.61 | 0.62, 0.65, 0.65 |

With memory, steps 2 and 3 read almost nothing in either design (2–655 tokens, against 2–6k fresh): the agent
remembers the code and writes the next format straight away. So reading becomes the cost of learning the code
once, and families' first step still cost more in 2 of 3 runs. The agent also generated about as many output
tokens on families as on by_format, though it wrote about 38% less code. Code changed was the steadiest
measure in the experiment (0.61–0.65 in all six comparisons).

## What it means

- **Where structure matters for an AI maintainer, the cost to extend sees it.** It matters when a change
  needs understanding spread across many places. Its biggest signal (2.5–4.2×, every run pair) is the
  structure-vs-stream mismatch, and the codebase is identical between streams, so size, names and style
  can't explain it.
- **It doesn't penalize scattered edits that are the same everywhere.** Agents make them with one script. If
  "good structure" is meant to include avoiding that kind of scatter, this reward won't teach it; for agent
  maintainers it may simply not matter.
- **It penalizes abstraction that compresses the domain, and not because of how it's written.** A memoryless
  extender pays to understand the abstraction on every change, and here that cost outweighed the smaller
  edits in both versions. This is the clearest conflict between "cheap for the next agent to change" and "a
  model that tells you something about the problem": a reward built on reading will push toward plain,
  repetitive, well-aligned code (one class per format) and away from the parameterized model, as the
  [pattern check](pattern_check.md) found on small code ([EVIDENCE](../EVIDENCE.md) #8). Only change size (and code size) rewards
  the parameterized model.
  Even on the changes the abstraction centralizes (stream S), its reading cost is at best recovered (Opus
  0.70× by_format) and at worst not (Sonnet 1.01×; the explicit version 1.15–1.44×). Giving the extender
  memory doesn't change that: later changes become nearly free to read in both designs, and what's left is
  the one-time cost of learning the code, which is higher for families.
- **With memory, reading stops measuring ongoing cost at all.** For agents that remember, structure's
  ongoing cost would have to show up in what they write or reason, and here families saved code but not
  output tokens. The one measure that consistently favours the domain model is the size of the code itself.
- **A maintainer with memory is a worse grader, though maybe a more realistic maintainer.** Its later changes
  cost almost nothing to read whatever the structure, so all its signal comes from the first change, which is
  an ordinary fresh probe: no more information, run in sequence, and noisier. Fresh extenders on every change
  remain the better grader. What memory changes is the reading of the score: for agents that remember, a
  reading-based reward mostly measures how costly code is to learn once.

## Related checks

**Change size on the V-measures chains** (no model calls). In [V measures](v_measures.md), three maintainers (Opus,
Sonnet, and `gpt-6-astra` run through Codex) each applied 4 held-out changes in sequence to the 10 ETL codebases;
their reading is the long-run cost. Here the saved code after every step is compared before and after (with a
cruder line-level count than above). How much a step changed agreed across maintainers far better than how much
it read:

| | Opus–Sonnet | Opus–Codex | Sonnet–Codex |
|---|---|---|---|
| reading (V-measures round-1 rules) | +0.16 | +0.37 | −0.01 |
| reading (rescored, later read weighting) | +0.30 | +0.28 | +0.21 |
| tokens changed | +0.60 | +0.53 | +0.84 |
| definitions modified | +0.66 | +0.72 | +0.75 |

Change size and reading (round-1 rules) were almost unrelated there (ρ = +0.04), and change size rated the golfed,
dead-code and junk-name copies as cheap as the reference: it sees how much has to change, not how hard it is to
find or read. On the 10 blind human-ranked pairs from V measures, change size (geometric mean over the three
maintainers) matched the human's pick on 7, and the three maintainers' reading on 6. (The 8/10 reported in V
measures is a different measure: the three-reader probe panel.)

**Combining the two.** √(reading × change size) per run, relative to by_format, both readers pooled:

| | by_kind | families | families_explicit | flat | layered |
|---|---|---|---|---|---|
| new kinds | 0.90 | 1.08 | 1.21 | 1.04 | 1.08 |
| new formats | 1.78 | **0.95** | 1.05 | 1.74 | 1.37 |
| shared behaviour | 0.91 | **0.85** | 1.06 | 0.80 | 1.11 |

It keeps the alignment flip (weaker on new kinds), still penalizes layered, and lets the original families
come out slightly ahead where its abstraction applies. But it softens the penalty on flat (0.80 on shared
behaviour), and the explicit rewrite of the same abstraction doesn't benefit, so it isn't yet a clean answer.

## What to try next

- **Weighting, on the existing runs (free):** reading plus a code-size term, at the weights that keep every
  ordering already established (the alignment flip, flat, layered, the ETL flaws) while letting the domain
  model win, if any such weights exist.
- **A long chain (10+ changes):** whether families' smaller growth per change eventually makes it cheaper to
  learn than by_format, the one argument left for it under a reading reward.
- **Correctness under pressure:** a weaker extender or a tight budget, plus hidden consistency tests (the new
  node inside every container), so that missed sites and drift, which good structure should prevent, show up
  as failures. All 216 runs here passed every test.
- **Domain questions on a reading budget:** answered from the code alone and graded against the rule table, as
  a direct test of "the abstractions tell you about the problem". Easy to game with notes that state the
  answers.
- **Fill-in-the-blank predictability:** rewrite a deleted method from its surroundings. Likely to reward
  copy-paste as much as abstraction.
- **A non-Claude reader** (`gpt-6-astra` through Codex) on the same grid.

## Limits

- One domain, two Claude readers, 3 changes per stream; sequences only in the 3-step memory chains.
- Codebases are 5.6–10k AST nodes (flat's single file is ~9k tokens), at or below the ~12k tokens across files
  above which earlier tasks showed selective reading; flat and by_kind-on-F were read whole.
- The abstraction was written two ways by the same author; another design of it could read differently.
- Change size is tokens of normalized source changed (docstrings and formatting removed), counted per token.
  An earlier line-level count inflated by_kind's changes (1.24–1.32×); the corrected numbers are above.
- Under heavy machine load the test runner sometimes failed outright, which the grader read as the extender
  breaking every existing test, and charged the failure cost (at least 40k tokens). Regrading from the saved
  snapshots fixed 1 of 216 runs (40k → 4.1k); another showed a real break mid-edit that reproduced.
- Scored before reads were weighted by the code each file holds. Rescoring 126 of the runs with that weighting
  raised every variant's effort by 2–4%, so the ratios above move by about 2% at most.

## Predictions

Written before results ([structure_axes_predictions.md](structure_axes_predictions.md)):

| | prediction | result |
|---|---|---|
| P1 | by_kind / by_format < 0.8 on K and > 1.25 on F, for each reader | Opus yes (0.79, 2.49); Sonnet no on K (0.87), yes on F (4.23) |
| P2 | flat > by_format on F; flat at most 1.5× by_kind on K | F yes; K yes for Sonnet (1.45), no for Opus (1.68) |
| P3 | families < by_format on F | **no** for reading (1.36, 1.65); yes for change size (0.60–0.61) |
| P4 | layered > by_format on both streams | yes, except Sonnet on K (0.92) |
| P5 | change size flips too, and agrees across readers better | **no flip** (by_kind 0.97–0.98× on both streams) |
| follow-up | families_explicit at most 0.8× families (legibility) vs. within 15% of families (abstraction itself) | within 15%: 1.08–1.14× families |
| S1 | families and families_explicit read < 0.9× by_format on stream S, both readers | **no**: families 0.70 (Opus) / 1.01 (Sonnet); explicit 1.44 / 1.15 |
| S2 | by_kind cheapest of all on S | Sonnet yes (0.85); Opus no (flat 0.61, families 0.70, by_kind 0.73) |
| S3 | families change size < 0.8× by_format on S | **no**: 0.85–0.87 |
| M1 | with memory, families' total reading over 3 steps ≤ by_format's | **no**: 1.72, 1.83, 0.91 (geomean 1.42) |
| M2 | memory cuts families' later steps below half its first, but not by_format's | **no**: both fall to almost nothing |

Per-run numbers: [structure_axes_data.json](structure_axes_data.json) (216 single-change runs, 12 memory chains).

Runners: `python tasks/docrender/gen/make.py` builds the variants and tests. The rest were in `scripts/structure_axes/`
(removed; in git history): `drive.sh` (single changes), then `regrade.py` (runs hit by load) and `analyze.py`. The
memory-chain and change-size runners weren't kept.
