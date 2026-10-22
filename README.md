# CraftBench

**An objective reward for well-crafted code: grade code by what it costs to change, not by what it looks like.**

Coding RL typically rewards whether tests pass (or some other scorer) for a one-time task. The code that does well in that scenario can be functionally correct, but built for one-time use rather than ongoing maintenance. This matters because a large portion of real-world use is in evolving software, not one-time tasks. Over time, agent-written code tends to accumulate complexity, verbosity, and duplication as it's extended. The usual remedies grade appearance (lint rules, LLM judges), which can be gamed, and can't quite fully represent what "well crafted code" is. Instead, here we measure maintainability/extensibility and the idea is that design patterns that make good code (SOLID, DRY, SOC, etc) may emerge as a result of that incentive.

## How it works

1. **Build:** the policy writes a program from a spec, one milestone at a time. Hidden tests check it works.
2. **Change:** a frozen model (the "extender") gets a few change requests the policy never saw, and implements
   each one on its own copy of the code.
3. **Score:** Measure how much the extender had to read before each new test passed. Less reading = code that's
   easier to change.

```
reward = F × geomean(E)^(−½)

F = share of hidden milestone tests passing     (does it work?)
E = reading until each change's tests passed    (how hard was it to change?)
```

Reading counts code in syntax nodes, so things like code-golf are mostly mitigated. The reward is per rollout, so it plugs into normal group-based RL training.

The maintainer it measures for is an LLM agent, with humans reviewing its work: "easy to change" means cheap for a model to change correctly. Some of what that rewards (less code, one place per rule, invariants you can check locally) helps human readers too; some (how cheaply dense code reads, which differs even between models) is about how today's models read.

The extenders are a panel (Sonnet + Opus by default; add other families with `--extenders`, e.g. `gpt-6-astra` through Codex, which has been checked against live runs). One reader isn't enough: Opus, Sonnet and Codex each measure consistently but disagree with each other about which code is easy to change ([#14](docs/experiments/v_measures.md)), so the reward averages the panel. The same setup benchmarks models as builders: see [benchmarking](docs/BENCHMARK.md).

## Evidence

| # | What we tested | Result | Finding | Details |
|---|---|---|---|---|
| 1 | Can an LLM judge spot good code? A SOLID/DRY rubric judge vs how easy 9 codebases actually were to change | ρ = −0.33. Its top scores went to the worst and third-worst codebases | Code that *looks* well designed isn't necessarily easy to change. Measure a real change instead of judging appearance | [judge vs extender](docs/experiments/judge_vs_extender.md) |
| 2 | An extender making one easy change ("add another step type") on those 9 codebases | 8 of 9 scored 91–98%; repeat runs barely agreed (+0.51) | One easy change can't tell codebases apart. The change requests are the measuring instrument | [judge vs extender](docs/experiments/judge_vs_extender.md) |
| 3 | Three kinds of change: a new capability, a rule that applies everywhere, a cross-cutting feature (6 codebases) | Scores spread 0.52–0.98 and repeat runs agreed (+0.89). Duplicated and over-engineered code failed | Each kind of change exposes a different flaw; copy-pasted logic only hurts when a rule changes everywhere. The mix of changes defines what "good code" means | [change mix](docs/experiments/change_mix.md) |
| 4 | What should "effort" mean? Turns, cost, lines changed or reading, tested on 8 pairs of a codebase and its copy with one deliberate flaw | Reading until the tests pass: 8/8, reliability 0.85. Turns: 0/8 (backwards). Cost: flat, because the extender spends whatever budget it gets. Lines changed: fooled by a "you're done" comment | Effort is how much the maintainer had to *understand*, not how long it worked or how much it typed | [findings](docs/experiments/effort_definitions_FINDINGS.md) |
| 5 | Same code, compressed ("golfed") | Raw token counts rated it 22–50% easier. Counting syntax nodes rated it 29% harder on the bigger change (p = 0.03), no difference on the small one | An LLM isn't slowed down by dense code the way a person is, so measure code in syntax nodes, not characters | [golf check](docs/experiments/golf_confirmation.md) |
| 6 | The packaged reward on a reference solution vs 5 copies with the same behavior and one flaw each | Reference rated easiest against all 5 (9/10 per change) | The environment's grader reproduces the experiments (after fixing a bug that lined snapshots up with the wrong tool calls) | [validation](docs/EVIDENCE.md) |
| 7 | Design patterns vs effort across 6 codebases (400–2,000 lines) | Compact direct code was cheapest to change; lines of code alone predicted outcomes (ρ = −0.99) | On small code, "good design" mostly means less code. Patterns are overhead until there's enough to organize | [pattern check](docs/experiments/pattern_check.md) |
| 8 | Good modeling (a few composable concepts) vs if/elif at the same size, one file of 400–850 lines | Reading tracked file length, not design. Limiting reads to 200 lines at a time only partly helped: the extender paged through the whole file anyway | Below ~7k tokens an LLM reads the whole codebase and keeps it in context, so structure inside it is invisible | [modeling vs scale](docs/experiments/modeling_scale.md) |
| 9 | The same two designs grown to 52 operations across files (~12k vs ~16k tokens) | The if/elif version needed about **2×** the reading (+102%; +111% and +193% on two of three changes, +33% on the third; the size gap is +34%). The extender read the composable code selectively | Good modeling pays off once code is too big to hold in context at once, so training tasks need codebases that grow that big | [modeling vs scale](docs/experiments/modeling_scale.md) |
| 10 | The reference vs its flawed copies again, with Opus as the extender | Reference rated easier than dead code, duplication, indirection and junk names (11/15 per change). The golfed copy came out about 2× *easier* | A stronger reader confirms most of the signal, but isn't slowed by compressed code at all, so golf is still a partially open exploit | [opus + size](docs/experiments/opus_and_size.md) |
| 11 | Size-matched: the reference vs a longer but cleaner refactor (+10% nodes) and a shorter golfed copy (−19%), same behavior | The longer, cleaner version was rated harder on all 3 changes; golfed came out about equal | On this task the reward still mostly tracks size, not quality. This is the biggest open problem | [opus + size](docs/experiments/opus_and_size.md) |
| 12 | Is the signal consistent? The reference and its 6 copies again with Opus, 3 independent runs each | 96–98% of the variation in effort on the two bigger changes comes from the code, not run-to-run noise (66% on the small one). Independent runs rank all 7 codebases at ρ ≈ 0.8 (Haiku: 0.61). Dead code and duplication were caught by every run on the bigger changes; junk names barely registered and golf was rated easier every time | The signal is repeatable, but what it rewards depends on the reader. We could probably get this even better with a panel of extenders from different model families, so one model's blind spots (names, dense code) get averaged out | [reliability](docs/experiments/opus_reliability.md) |
| 13 | Benchmark: Opus 5.5, Sonnet 5.5 and Fable 5.1 each build the task 3 times; Opus makes the changes | All 9 builds pass 97–99% of milestone tests. Opus's code was easiest to change (reward 1.66–2.05), then Sonnet's (1.59–1.61), then Fable's (1.35–1.58), the largest at about 2× Sonnet's lines | Stronger models don't automatically write code that's easier to change, but on this small task the order mostly follows size, and a Claude-only panel can't rule out self-preference | [Claude builders](docs/experiments/claude_builders.md) |
| 14 | Which measure of change cost predicts what code really costs to own? 10 large codebases (reference, if/elif, 4 flawed copies, 4 fresh builds from plain-language specs); answer key = 4 unseen changes applied in sequence by two maintainers | Probes that implement the change predicted the answer key best: Sonnet probe ρ = +0.77, Opus+Sonnet panel +0.73. The Opus probe (the default) only managed +0.31, despite repeating well (+0.83). Plan-only probes, a judge and free metrics all scored ≤ +0.38. Size alone: +0.13 | Implementing the change is what makes a probe work. Which single reader looks best flips with how cost is counted (syntax nodes vs raw tokens), and the two maintainers barely agreed, so "easy to change" is partly "easy for this reader": use a panel, not a winning model. On large code, size no longer decides | [V measures](docs/experiments/v_measures.md) |
| 14 | A bigger task (52 operations, ~14k tokens): composable reference vs the same behaviour as if/elif chains, same size; Opus, 3 runs per change | The if/elif code needed more reading on all 4 changes (+20% to +150%; reward 1.21 vs 1.52). Single runs disagreed on 2 of 4 | At this size the reward sees structure, not just size. It needs several runs per change, and the extender's tools matter (Claude Code truncates big outputs, which flatters big files) | [XL calibration](docs/experiments/xl_calibration.md) |

## What's next

- **More tasks.** Only the ETL domain exists. Add more, with changes covering every kind of change.
- **Bigger codebases.** The reward only sees structure past ~12k tokens, so the default task is `etl_pipeline_xl_naive` (52 operations over 7 milestones, plain-language specs); the small `etl_pipeline` is for quick checks. New domains need the same size.
- **Make a cross-family panel the default V, and test it leave-one-reader-out** ([#14](docs/experiments/v_measures.md)): no single reader was reliably best. Drop tests no run can pass (behaviour the specs leave open) in the shipped grader too.
- **Validate the effort metric against an answer key that isn't reading** (human time, defects introduced later, success within a fixed budget). #14 shows the syntax-node weighting decides whether golf counts as costly.
- **More and stronger extenders.** Only Claude models have been used so far. Codex and Gemini extenders are wired up but need a live check. A panel of models keeps the policy from writing for one reader's quirks.
- **Solve for code-golf.** Counting syntax nodes is better than raw LOC/tokens read but Opus still found golfed code about 2× easier, so dense code needs a penalty (or a separate density check) - also worth thinking about if this is even something worth incentivising (does golfed code actually matter for LLMs).
- **Train with it.** See whether a policy trained on this starts writing composable code on its own.

## Beyond this benchmark

The maintenance phase can wrap most coding tasks whose output lives on: greenfield builds, bug fixes, feature work, etc. More generally: grade any artifact by how well a frozen downstream agent can use or change it.

## Try it

```bash
pip install -e .
craftbench validate --task etl_pipeline --recorded data/recorded/etl_pipeline   # re-grades recorded runs, no model calls
craftbench grade --code path/to/code                        # live grading (needs the `claude` CLI)
craftbench bench --builders opus,gpt-6-astra --extenders opus,gemini-4-argon   # benchmark models
```
