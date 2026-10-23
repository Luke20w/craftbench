# Pre-registered predictions: docrender axes experiment

Written 2026-10-22 before any extender results were seen (only a 4-run pilot was running, unread).

## Setup
Same behaviour (12 formats × 20 node kinds), five organizations, verified byte-identical on 122 tests:

| variant | structure | right for |
|---|---|---|
| by_kind | a class per node kind, a method per format | stream K (new kinds) |
| by_format | a renderer class per format, a method per kind | stream F (new formats) |
| families | by_format + LineMarkup base: 9 of 12 formats are marker settings | stream F, deeper model |
| flat | one module, `if kind` then `if fmt` | (outer branch is kind, so locality like by_kind) |
| layered | by_format + registries, factories, middleware, a class per cell | neither (spurious structure) |

Streams: K = strikethrough, callout, definition_list. F = asciidoc, textile, rst.
Measures: reading (CraftBench `effort`, AST nodes read per test), change size (tokens of normalized source
changed), files touched, tests passed.

## Predictions
- **P1 (primary): the preference flips.** Reading on by_kind / by_format: geomean ratio < 0.8 on stream K
  and > 1.25 on stream F. Must hold for each reader separately.
- **P2: no structure costs more than the right structure.** flat > by_format on F. On K, flat is at most
  by_kind's cost × 1.5 (its kind branches are local, but the file is read as a whole).
- **P3: the deeper model is cheaper.** families < by_format on F (reading and change size).
- **P4: spurious structure costs.** layered > by_format on both streams.
- **P5: change size shows P1 too, and agrees across readers better than reading does.**

## What would count against "cost to extend measures structure"
P1 failing for a reader (no flip, or a flip under 1.25× either way), or the stream F ranking not putting
by_kind and flat above by_format and families.

## Follow-up (written 2026-10-22, before any families_explicit run)
families_explicit: the same LineMarkup abstraction, but every format lists every setting in one complete
LineStyle (no defaults inherited from Markdown), with its own-way shapes listed separately. 5.8k AST nodes.
- **If the cost was this abstraction's legibility:** families_explicit reads at most 0.8× families on both
  streams, and at most by_format's cost on new formats (F).
- **If abstraction itself costs a memoryless reader:** families_explicit stays within 15% of families
  (about 1.4–1.7× by_format).

## Stream S (written 2026-10-23, before any stream S run)
S = changes to behaviour the formats share, each an optional field: list `start` (7 formats change), quote
`cite` (12 formats), default `alt` from the file name (11 formats). In families/families_explicit most of
each change is one edit in the LineMarkup base (plus html, bbcode, latex); in by_format it is one edit per
format; in by_kind it is one file (list, quote, image + figure).
- **S1: the abstraction pays back here.** families and families_explicit read less than by_format on S
  (ratio < 0.9), for both readers.
- **S2:** by_kind is cheapest of all on S (each change lives in one or two node files).
- **S3:** change size: families < by_format on S (< 0.8).
If S1 fails, reading penalizes this abstraction even on the changes it was built for.

## Memory chains (written 2026-10-23, before any memory-chain result)
The 3 new formats applied in sequence (asciidoc → textile → rst) on by_format and families. fresh: a new
extender per step. memory: one resumed session, charged only for each step's own reading.
- **M1:** with memory, families' total reading over the 3 steps is at most by_format's (ratio ≤ 1.0); fresh,
  it stays around 1.4× (as in the single changes).
- **M2:** memory cuts steps 2–3 much more for families than for by_format: families' step 2–3 reading falls
  below half its step 1, by_format's doesn't.
If M1 fails, the abstraction penalty isn't only about memorylessness.
