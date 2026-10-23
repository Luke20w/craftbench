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

| variant | structure | size (syntax nodes) |
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

**Runs:** every variant x change, Opus 5.5 and Sonnet 5.5 as extenders, 2 runs each: 216 runs. All 216
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

**1. The preference flips with the stream, but unevenly.** On new formats, by_kind cost 2.5–4.2x more to
extend than by_format, in all 24 run pairs, for both readers. On new kinds, by_kind was cheaper, but only by
13–21% (18 of 24 run pairs). The transcripts show why the effect is lopsided:
- **Adding a kind to by_format** means adding one method to each of 12 renderers. The extenders wrote one
  script or `sed` loop that inserted the method into every file, after reading one or two renderers. Edits
  that are the same everywhere are cheap for an agent with a shell, however scattered.
- **Adding a format to by_kind** means writing a method in each of 20 node classes, and each one depends on
  that node's fields and children. The extender had to read every class: 1.1x the whole codebase.

So the measure sees the cost of edits that are scattered *and* need understanding, not scatter on its own.

**2. Missing structure costs on both streams.** flat cost 1.3x on K and 3.3x on F. (The stream it is
aligned with by locality, K, still cost more, because its single 9k-token file is read whole.)

**3. Spurious structure mostly costs.** layered cost 1.6–1.9x on F. On K it was 1.36x (Opus) and 0.92x
(Sonnet).

**4. The deeper model is penalized.** families is the smallest codebase. It encodes a real fact about the
domain: most markup formats are the same shapes with different markers. It also needed the smallest changes
(0.60–0.79x the tokens). But it cost 1.4–1.7x more reading on both streams, even on new formats, where it
should do best. To add a format the extender had to learn the base class's ~25 settings and hooks, and to add a kind
it had to see each format's settings, including defaults inherited implicitly from Markdown.

**5. Making the abstraction easier to read didn't help.** A second version, families_explicit, keeps the
abstraction but removes what looked hard to read: every format spells out all of its settings in one table,
nothing is inherited from Markdown, and each format's exceptions are listed apart. It cost slightly *more*
reading than families (1.08–1.14x on every stream and reader, within the 15% that the pre-registered
prediction set for "the abstraction itself costs"). In two independent writings, the abstraction that
compresses the domain cost 1.4–1.9x more to read than one plain class per format. This probably won't change
over a longer stream: in both designs, adding a format means reading a fixed amount (a sibling format, or the
base class and a sibling), so the abstraction's reading cost recurs on every change rather than paying off.

**6. Even on the changes it centralizes, the abstraction barely pays back.** Stream S, reading relative to
by_format (Opus / Sonnet): families 0.70 / 1.01, families_explicit 1.44 / 1.15, by_kind 0.73 / 0.85, flat 0.61 /
0.98, layered 1.45 / 1.17. families touched 0.6x the files and wrote 0.85x the code, but only Opus read less,
and the explicit version read more for both. Each of these changes concerns one node kind, so the code
organized by kind (by_kind, and flat, whose outer branch is the kind) was as cheap or cheaper. Repeat runs
were noisier here (one by_format cell was 5.4k and 1.7k), so these are rougher than the K and F results.

**7. No single alternative measure works.** Tokens of code changed rate by_kind the same as by_format on
*both* streams (0.97–0.98x), because the work is the same amount wherever it lives. That measure doesn't see locality at
all, though it does reward the deeper model. Files touched sees locality exactly (by_kind 0.17x on K, 10.5x
on F), but it rates flat best on both streams (1 file), which is wrong.

## What it means

- **Where structure matters for an AI maintainer, the cost to extend sees it.** It matters when a change
  needs understanding spread across many places. Its biggest signal (2.5–4.2x, every run pair) is the
  structure-vs-stream mismatch, and the codebase is identical between streams, so size, names and style
  can't explain it.
- **It doesn't penalize scattered edits that are the same everywhere.** Agents make them with one script. If
  "good structure" is meant to include avoiding that kind of scatter, this reward won't teach it; for agent
  maintainers it may simply not matter.
- **It penalizes abstraction that compresses the domain, and not because of how it's written.** A memoryless
  extender pays to understand the abstraction on every change, and here that cost outweighed the smaller
  edits in both versions. This is the clearest conflict between "cheap for the next agent to change" and "a
  model that tells you something about the problem": a reward built on reading will push toward plain,
  repetitive, well-aligned code (one class per format) and away from the parameterized model, as finding #7 in
  the README found on the small task. Only change size (and code size) rewards the parameterized model.
  Even on the changes the abstraction centralizes (stream S), its reading cost is at best recovered (Opus
  0.70x by_format) and at worst not (Sonnet 1.01x; the explicit version 1.15–1.44x).

## Limits

- One domain, two Claude readers, 3 changes per stream, single changes rather than sequences.
- Codebases are 5.6–10k syntax nodes, below the ~12k where earlier tasks showed selective reading; flat and
  by_kind-on-F were read whole.
- The abstraction was written two ways by the same author; another design of it could read differently.
- Change size is tokens of normalized source changed (docstrings and formatting removed), counted per token.
  An earlier line-level count inflated by_kind's changes (1.24–1.32x); the corrected numbers are above.
- Under heavy machine load the test runner sometimes failed outright, which the grader read as the extender
  breaking every existing test. `scripts/axes/regrade.py` regrades such runs from their snapshots: 1 of 216 was
  affected (40k -> 4.1k); another showed a real break mid-edit that reproduced.
- Scored with the read-weighting rules as of commit f47f6ee. Branch `Luke20w/review-measure-fixes` (4209447) re-weights shell reads of several files; the runs can be rescored for free by rerunning `scripts/axes/drive.sh` once it lands.

## Predictions

Written before results (`.context/axes/PREDICTIONS.md`):

| | prediction | result |
|---|---|---|
| P1 | by_kind / by_format < 0.8 on K and > 1.25 on F, for each reader | Opus yes (0.79, 2.49); Sonnet no on K (0.87), yes on F (4.23) |
| P2 | flat > by_format on F; flat at most 1.5x by_kind on K | F yes; K yes for Sonnet (1.45), no for Opus (1.68) |
| P3 | families < by_format on F | **no** for reading (1.36, 1.65); yes for change size (0.60–0.61) |
| P4 | layered > by_format on both streams | yes, except Sonnet on K (0.92) |
| P5 | change size flips too, and agrees across readers better | **no flip** (by_kind 0.97–0.98x on both streams) |
| follow-up | families_explicit at most 0.8x families (legibility) vs. within 15% of families (abstraction itself) | within 15%: 1.08–1.14x families |
| S1 | families and families_explicit read < 0.9x by_format on stream S, both readers | **no**: families 0.70 (Opus) / 1.01 (Sonnet); explicit 1.44 / 1.15 |
| S2 | by_kind cheapest of all on S | Sonnet yes (0.85); Opus no (flat 0.61, families 0.70, by_kind 0.73) |
| S3 | families change size < 0.8x by_format on S | **no**: 0.85–0.87 |

Rerun: `python tasks/docrender/gen/make.py` (variants and tests), `scripts/axes/drive.sh`, then
`python scripts/axes/analyze.py`.
