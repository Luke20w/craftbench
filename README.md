# CraftBench

An attempt at an objective reward for well-crafted code: grade code by what it costs to change.

## Why

RL environments and evals traditionally reward code for functional correctness (it passes hidden tests, or an LLM judge grades it well against a rubric). In reality, code gets changed over and over, and agent-written code currently tends to pile up complexity, verbosity and duplication as it changes. The idea here is to try and reward for well-crafted code.

Even in a world where the cost to read/write code falls close to zero, my belief is that well-crafted code is still quite valuable. Good abstractions and design patterns (SOLID, SoC, DRY, etc) shape a product or platform. For example:

- Unix treats everything as a file, which is what made pipes, and a whole culture of small composable tools, possible.
- Git stores snapshots, not diffs, which made branching cheap, and branches and pull requests became how teams work.
- Spreadsheets reduced computation to cells and formulas, which ended up being a simple model that could represent complex analysis

## How it works

The idea, at the core, is to grade code based on effort to build on it (or more concretely, how much an extender has to read to build on it).

So we split a project into "checkpoints": feature requests, each with hidden tests.

1. The policy (the model being trained or evaluated) implements the first checkpoints one at a time, each on top of its own code.
2. A panel of extender agents each implement one of the later checkpoints on a copy of the policy's code.
3. We grade by how much (in AST nodes) the extenders had to read before that checkpoint's tests passed.

**reward = F / √V**

- **F**: pass rate on the hidden checkpoint tests. Does it work?
- **V**: how much the extenders read to make the changes, in AST nodes. How hard is it to change?

## Measuring change cost (V)

V has to track what code costs to own, and resist reward hacking when a policy optimizes against it. That proved
to be the hardest part to get right. We validated candidate measures against three references:

- **Long-run cost.** We had a model keep maintaining each of 10 codebases through four more changes and measured
  the total effort. A good V should rank the codebases the same way (Spearman ρ), from much less work.
- **Planted flaws.** Perturbation tests: copies of the same code with one flaw (dead code, bad abstractions,
  duplication, golfing, junk names) should score worse. The main test used 8 such pairs (four flaws × two changes).
- **A human.** A blind ranking of 10 pairs of codebases.

**What we tried.** Every candidate estimates how hard the code is to change; they differ in what they measure:

| what we measured | result | |
|---|---|---|
| an LLM judge's score against a SOLID/DRY rubric | ranked codebases *backwards* (ρ = −0.33) | ✗ |
| the code itself: size, duplication, complexity, name quality | weak (ρ ≤ +0.38) | ✗ |
| an extender plans the change without making it: how much it read | weak (ρ = +0.36) | ✗ |
| an extender makes the change: turns taken or dollars spent | turns were backwards (0 of 8 planted-flaw pairs); dollars track the budget, not the code | ✗ |
| an extender makes the change: size of what it wrote (lines or AST nodes) | fooled by a "you're done" comment and by junk names | ✗ |
| **an extender makes the change: how much it read before the tests passed** | **8 of 8 planted-flaw pairs; ρ = +0.58 to +0.77 against long-run cost** | ✓ |

### Learnings

- **Count code in AST nodes, not tokens.** In tokens, golfed code reads 22–50% cheaper. In AST nodes,
  compressing code, shortening names or stripping comments mostly doesn't help.
- **Use a panel of extenders from different model families.** Each model is consistent with itself, but models disagree about which code is easy
  to change. A panel of Opus, Sonnet and Astra agreed with a blind human ranking on 8 of 10 pairs; single models got 5–6.
- **Structure only shows at scale.** Below ~7k tokens a model reads everything, so V is just size. Above ~12k
  tokens across files it reads selectively, and composable code wins.
- **It rewards structure that matches the changes, but penalizes over-engineering.** Organizing code on the wrong axis costs 2.5–4.2× more.
- **Robust to the reward hacks we tried.**
  - Golfing (short names, packing code onto fewer lines): mostly doesn't help, since code is counted in AST
    nodes, not characters. Opus still reads dense code a little faster.
  - Stripping comments and docstrings: no help, for the same reason.
  - Padding files with long docstrings to make the code cheaper to read: no help.
  - Hiding code where it isn't counted (files that aren't `.py`, or don't parse): counted anyway.
  - Leaving notes for the extender ("you're done", "the change goes here"): no effect.

  Red-teamed: Opus, told to maximize the score by any means, wrote clean code.

Every result, with links to its write-up, is in
[EVIDENCE](docs/EVIDENCE.md).

## Open problems

- **It can't tell slightly different code apart.** It separates very different code reliably, but differences
  smaller than one measurement's noise (~10–15%) are invisible. That's the case RL needs most: group-relative
  methods like GRPO compare rollouts of one policy on the same task, and those are usually that close (six Sonnet
  builds cost roughly the same to own).
- **"Easy to change" depends on who's reading.** Models disagree, and each predicts its own maintenance cost best. A panel is a compromise, not ground truth.
- **It can sometimes penalize good abstractions.** An abstraction that compresses the domain sometimes costs *more* to read, because each new maintainer has to learn it first.
- **Expensive.** Each reward takes many agent rollouts on a codebase of ~12k+ tokens.

## Other uses

This could be added as a second reward to existing RL coding tasks: hold back one follow-up change and grade by
how much the extenders read to make it.

It also isn't specific to code. Anything you can break into checkpoints works the same way: grade what one
checkpoint leaves behind (a report, a notebook, a Lean library, an agent's notes) by how much the next agent has to
read to build on it.

## Quickstart

```bash
pip install -e .
craftbench validate --task etl_pipeline --recorded data/recorded/etl_pipeline   # re-grades recorded runs, no model calls
craftbench grade --code path/to/code                                            # live grading (needs the `claude` CLI)
craftbench bench --builders opus,gpt-6-astra --extenders opus,gemini-4-argon    # benchmark models as the policy ("builders")
```

## Repository

```
craftbench/   the environment: tasks, agents (Claude Code, Codex, Gemini CLI), grading, effort, reward, CLI
tasks/        each task is a folder of specs and hidden tests, plus the reference and flawed copies
docs/         USAGE (grading, benchmarking, adding a task), EVIDENCE (every result),
              experiments/ (one write-up per experiment)
data/         recorded extender runs, so `validate --recorded` re-grades without model calls
tests/
```
