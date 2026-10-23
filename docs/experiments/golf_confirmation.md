# Does golfed code fool the effort measure?

Golfed code (short names, logic packed onto fewer lines) behaves the same but is less readable, so a sound effort
measure should rate it harder to change. This checks whether reading-based effort gets that right.

## Setup

The ETL reference codebase against a golfed copy, two change requests (limits: every string value in a step
must be short and printable; sub-pipelines: named step sequences invoked with `call`), Haiku extender, 6 runs
each. Four effort measures, all from [effort definitions](effort_definitions.md):

- **`read_to_tts`**: tokens of tool output the extender read before the change first passed.
- **`read_per_test`**: for each hidden test, tokens read by the time it started passing for good, averaged over tests.
- **`nodes_read_to_tts`, `nodes_read_per_test`**: the same, with each code read weighted by the AST nodes per
  character of the code it read, relative to the reference, and never below 1. The unit stays "reference-equivalent
  tokens", so the numbers compare directly with the token measures.

## Result

Positive % = golfed rated HARDER (correct: same behaviour, less readable). p = one-sided permutation test that
golfed > reference; not computed for score ("–").

On the reference the node weight is exactly 1 by construction, so its node-weighted numbers are identical to its
token numbers. Only the golfed copy's numbers change.

| measure | CR | reference mean (runs) | golfed mean (runs) | golfed vs reference | p |
|---|---|---|---|---|---|
| score | limits | 1.00 [1.0, 1.0, 1.0, 1.0, 1.0, 1.0] | 1.00 [1.0, 1.0, 1.0, 1.0, 1.0, 1.0] | +0% | – |
| score | subpipelines | 1.00 [1.0, 1.0, 1.0, 1.0, 1.0, 1.0] | 0.97 [0.94, 1.0, 1.0, 0.94, 0.94, 1.0] | −3% | – |
| read_to_tts | limits | 5076 [5020, 5144, 5089, 5126, 5089, 4984] | 2529 [4168, 2144, 2102, 2312, 2250, 2197] | −50% | 1.000 |
| read_to_tts | subpipelines | 6035 [5427, 7228, 5478, 6989, 5463, 5628] | 4685 [3263, 5227, 5189, 5069, 4640, 4720] | −22% | 1.000 |
| nodes_read_to_tts | limits | 5076 [5020, 5144, 5089, 5126, 5089, 4984] | 4544 [7482, 3900, 3858, 4068, 4005, 3953] | −10% | 0.717 |
| nodes_read_to_tts | subpipelines | 6035 [5427, 7228, 5478, 6989, 5463, 5628] | 8252 [5725, 9228, 9105, 9018, 8152, 8283] | +37% | 0.005 |
| read_per_test | limits | 4253 [4192, 4302, 4277, 4309, 4277, 4162] | 2218 [4168, 1774, 1816, 1918, 1814, 1819] | −48% | 0.999 |
| read_per_test | subpipelines | 5876 [5366, 7119, 5373, 6534, 5357, 5508] | 4295 [3359, 2811, 5137, 5157, 4795, 4511] | −27% | 1.000 |
| nodes_read_per_test | limits | 4253 [4192, 4302, 4277, 4309, 4277, 4162] | 4015 [7482, 3267, 3313, 3410, 3306, 3311] | −6% | 0.534 |
| nodes_read_per_test | subpipelines | 5876 [5366, 7119, 5373, 6534, 5357, 5508] | 7553 [5895, 4831, 9054, 9193, 8408, 7938] | +29% | 0.033 |

## What it means

**Counted in tokens, golf fools the measure.** Golfed code looks 22–50% cheaper to change on every token measure.
**Counted in AST nodes, it mostly doesn't.** Golf is neutral on the small change (limits) and penalized on the
bigger one (sub-pipelines, +29–37%). Pass rates barely move (−3% at most).
