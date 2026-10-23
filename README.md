# CraftBench

**Measuring well-crafted code**

## Why

RL tasks / evals traditionally reward code by its function (that it passes tests or gets graded well by an LLM judge with a rubric). In reality, code gets changed over and over, and agent-written code currently tends to pile up complexity, verbosity and duplication as it changes. The idea here is to try and reward for well-crafted code.

Even in a world where the cost to read/write code falls close to zero, my belief is that well-crafted code is still quite valuable. Good abstractions and design patterns (SOLID, SoC, DRY, etc) shape a product or platform. For example:

- Unix treats everything as a file, which is what made pipes, and a whole culture of small composable tools,
  possible.
- Git stores snapshots, not diffs, which made branching cheap, and branches and pull requests became how teams work.
- Spreadsheets reduced computation to cells and formulas, which turned a ledger into a tool millions of people
  program with.

## How it works

The idea, at the core, is to grade code based on how easy it is to build upon (or more concretely, how much an extender has to read to build on it).

So we split a project into "checkpoints": feature requests, each with hidden tests.

1. The policy (the agent we're grading) implements the first checkpoints one at a time, each on top of its own code.
2. A panel of extender agents each implement one of the later checkpoints on a copy of the policy's code.
3. We grade by how much (in AST nodes) the extenders had to read before that checkpoint's tests passed.

**reward = F × V<sup>−½</sup>**

- **F**: share of hidden checkpoint tests passing. Does it work?
- **V**: how much the extenders read to make the changes. How hard is it to change?

## Defining the value function (V)

V has to track what code costs to own, and hold up when a policy optimizes against it. That proved to be the
hardest part to get right. To compare candidates we used a few kinds of ground truth.

- **Long-run cost.** We had a model keep maintaining each of 10 codebases through four more changes and measured
  the total effort. A good V should rank the codebases the same way, from much less work.
- **Planted flaws.** Copies of the same code with one flaw (dead code, bad abstractions, duplication, golfing, junk
  names) should score worse.
- **A human.** A blind ranking of 10 pairs of codebases.

**What we tried.** Every candidate estimates how hard the code is to change; they differ in what they measure:

| what we measured | result | |
|---|---|---|
| an LLM judge's score against a SOLID/DRY rubric | ranked codebases *backwards* (ρ = −0.33) | ✗ |
| the code itself: size, duplication, complexity, name quality | weak (ρ ≤ +0.38) | ✗ |
| an extender plans the change without making it: how much it read | weak (ρ = +0.36) | ✗ |
| an extender makes the change: turns taken or dollars spent | turns were backwards (0 of 8 known comparisons); dollars track the budget, not the code | ✗ |
| an extender makes the change: size of what it wrote (lines or syntax nodes) | fooled by a "you're done" comment and by junk names | ✗ |
| **an extender makes the change: how much it read before the tests passed** | **8 of 8 known comparisons; ρ = +0.58 to +0.77 against long-run cost** | ✓ |

### Learnings

- **Count code in syntax nodes, not tokens.** In tokens, golfed code reads 22–50% cheaper. In syntax nodes,
  compressing code, shortening names or stripping comments mostly doesn't help.
- **Use a panel of readers.** Each model is consistent with itself, but models disagree about which code is easy
  to change. A panel of Opus, Sonnet and Astra agreed with a blind human ranking on 8 of 10 pairs; single models got 5–6.
- **Structure only shows at scale.** Below ~7k tokens a model reads everything, so V is just size. Above ~12k
  tokens across files it reads selectively, and composable code wins.
- **It rewards structure that matches the changes, but penalizes over-engineering.** Organizing code on the wrong axis costs 2.5–4.2× more.
- **Hard to game.** Common ways to score well without writing better code:
  - Golfing (short names, packing code onto fewer lines): mostly doesn't help, since code is counted in syntax
    nodes, not characters. Opus still reads dense code a little faster.
  - Stripping comments and docstrings: no help, for the same reason.
  - Padding files with long docstrings to make the code cheaper to read: no help.
  - Hiding code where it isn't counted (files that aren't `.py`, or don't parse): counted anyway.
  - Leaving notes for the extender ("you're done", "the change goes here"): no effect.

  Opus, told to maximize the score by any means, wrote clean code.

Every result, with links to its write-up, is in
[EVIDENCE](docs/EVIDENCE.md).

## Open problems

- **It can't tell slightly different code apart.** It separates very different code reliably, but differences
  smaller than one measurement's noise (~10–15%) are invisible. That's the case RL needs most: rollouts of one
  policy are usually that close (six Sonnet builds cost roughly the same to own).
- **"Easy to change" depends on who's reading.** Models disagree, and each predicts its own maintenance cost best. A panel is a compromise, not ground truth.
- **It can sometimes penalize good abstractions.** An abstraction that compresses the domain sometimes costs *more* to read, because each new maintainer has to learn it first.
- **Expensive.** Each reward takes many agent runs on a codebase of ~12k+ tokens.

## Quickstart

```bash
pip install -e .
craftbench validate --task etl_pipeline --recorded data/recorded/etl_pipeline   # re-grades recorded runs, no model calls
craftbench grade --code path/to/code                                            # live grading (needs the `claude` CLI)
craftbench bench --builders opus,gpt-6-astra --extenders opus,gemini-4-argon    # benchmark models as builders
```

## Repository

```
craftbench/   the environment: tasks, agents (Claude Code, Codex, Gemini CLI), grading, effort, reward, CLI
tasks/        each task is a folder of specs and hidden tests (see tasks/README.md)
docs/         DESIGN (how the reward works), EVIDENCE (every result), BENCHMARK, TASK_AUTHORING;
              experiments/ has one write-up per experiment
scripts/      runners for experiments that needed more than the CLI
data/         recorded runs, so validation and the benchmark re-grade without model calls
tests/
```
