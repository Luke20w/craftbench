# Does the reward favor good modeling?

Question: does reading cost reward code built from a few composable concepts (field types, an op
registry, a runtime context) over the alternatives? Size is held as close to equal as the design allows.
Predictions were written before every paid run. Haiku extender, 2 runs per cell, about $24 in total.
Effort = `nodes_read_per_test` (the grader's measure). Positive % = the alternative was harder to change.

## 1. Small codebase (~400 lines, one file): no

Four behavior-identical bases within 9% of each other in syntax nodes (composable, leaky, special-cased,
if/elif), plus `clean` (wrong-axis registry) and `overengineered` (74 files). Changes: `case`
(a new op made from existing parts), `limits` (a rule on every string field), `sub-pipelines` (a new concept).

- Among the size-matched four, reading followed **file length in characters exactly**. Haiku reads the
  whole file once (~4.5k tokens) in every run. The composable base lost only because its docstrings
  made it 7% longer. 1 of 6 predictions held.
- Coarse failures were still caught: `clean` and `overengineered` cost about 2× as much and failed tests,
  but they're also bigger.
- Places edited did follow modeling: on `limits`, composable 5.5 < special-cased 7 < leaky 8.5 < if/elif 9.5.

## 2. 20 ops, still one file (~7k tokens): no; with a 200-line read window: partly

| if/elif vs composable | full reader | 200-line window |
|---|---|---|
| limits | +6% | +7% |
| case | −1% | +20% |
| sub-pipelines | +8% | +31% |
| geometric mean | +4% | +19% |

The window didn't help on `limits`. Haiku paged through the whole file in 200-line chunks and kept it all
in context, so a window limits each *view*, not *memory*. Edit volume saw the difference (limits: 2 vs 9
syntax-node places, −72% nodes changed), but edit volume is fooled by junk names (−54%) and the misleading
note (−60%), which reading catches. Breadth alone compressed less than expected: the 20-op if/elif base is
only +15% nodes.

## 3. 52 ops across several files (composable ≈11.8k tokens, 15 files; if/elif ≈15.9k, 7 files): yes

Both bases were generated from one op spec, so they behave identically by construction (same results on 274 tests).

| if/elif vs composable | reading | places edited | share of code read | runs that missed tests |
|---|---|---|---|---|
| case | **+93%** | 3 vs 1.5 | 97% vs 67% | 0 / 0 |
| sub-pipelines | **+149%** | 33 vs 11 | 100% vs 48% | 1 / 0 |
| limits | +10% | 33 vs 8 | 52% vs 85% | 1 / 0 |
| geometric mean | **+74%** (env grader: +102%; +80% with a floored density weight) | | | |

The size gap is +34% chars and +47% nodes. The extender read the composable code selectively and the
if/elif code in full. The exception is `limits`. The if/elif base keeps all validation in one file (the
right axis for a rule about validated values), so Haiku read only that file. On the composable base it read
every ops module to confirm that all 52 ops use the field types. It still made 4× fewer edits, and only the
if/elif base missed tests.

## Takeaways

1. **Scale is a requirement.** At ≤7k tokens an LLM extender reads everything, so reading can't see
   modeling. At ~12–16k tokens across files, it rewards modeling strongly on 2 of 3 change types.
   Training tasks need to grow codebases to that size (e.g. long milestone sequences).
2. **What counts as good modeling depends on the change pool.** The first "composable" base had no runtime
   context and paid for it on sub-pipelines; the if/elif base's phase split was the right axis for `limits`.
3. **Log edit volume and missed tests next to reading.** They caught the one change type where reading
   didn't, but edit volume alone is easy to fool.
4. Caveats: n = 2 per cell; synthetic bases; one domain; Haiku only.
