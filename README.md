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

The maintainer it measures for is an LLM agent, with humans reviewing its work: "easy to change" means cheap for a model to change correctly. Some of what that rewards (less code, one place per rule, code organized along the changes that arrive) helps human readers too; some (how cheaply dense code reads, which differs even between models) is about how today's models read.

The extenders are a panel (Sonnet + Opus by default; add other families with `--extenders`, e.g. `gpt-6-astra` through Codex, which has been checked against live runs). One reader isn't enough: Opus, Sonnet and Codex each measure consistently but disagree with each other about which code is easy to change ([evidence](docs/EVIDENCE.md#readers) #20–21), so the reward averages the panel. The same setup benchmarks models as builders: see [benchmarking](docs/BENCHMARK.md).

## What we've found

Details and links for every result are in [EVIDENCE](docs/EVIDENCE.md).

1. **Measure a real change, not how code looks.** A SOLID/DRY judge was anti-correlated with real outcomes. Reading
   until the tests pass, counted in syntax nodes, got every known pair right. (#1–7)
2. **Structure only shows at scale.** Below ~7k tokens a model reads everything, so the reward is a size count. At
   ~12k+ tokens across files it reads selectively, and composable code beats the same behaviour as if/elif. (#8–14)
3. **It sees the structure that matters to a model.** Organizing on the wrong axis costs 2.5–4.2×. Uniform scattered
   edits cost little (agents script them), and an abstraction that compresses the domain costs *more*: a
   maintainer without memory relearns it on every change. (#15–18)
4. **"Easy to change" depends on the reader.** Models are each consistent but disagree, so the reward uses a panel.
   A three-family panel matched a blind human ranking on 8 of 10 pairs. (#19–22)
5. **Robust, not yet precise.** Every exploit found is fixed, but one measurement's noise (~10–15%) exceeds the gap
   between near-identical rollouts. (#23–31)

## What's next

- **Precision**: more runs or bigger probes, so it can rank similar rollouts (#28).
- **Readers**: add a third family to the default panel; Opus predicts long-run cost weakly (#17, #20).
- **Abstraction**: test longer streams of changes, where learning an abstraction once could pay off (#16).
- **An answer key outside the LLM loop**: changes that modify behaviour, so defects show (#7).
- **More large tasks**: new domains need ~12k+ tokens. Golf: whether dense code *should* cost more is open (#5, #20).
- **A rotating change pool, then train with it.**

## Beyond this benchmark

The maintenance phase can wrap most coding tasks whose output lives on: greenfield builds, bug fixes, feature work, etc. More generally: grade any artifact by how well a frozen downstream agent can use or change it.

## Repository

```
craftbench/   the environment: tasks, agents (Claude Code, Codex, Gemini CLI), grading, effort, reward, CLI
tasks/        each task is a folder of specs and hidden tests (see tasks/README.md)
docs/         DESIGN (how the reward works), EVIDENCE (what we've found), BENCHMARK, TASK_AUTHORING;
              experiments/ has one write-up per experiment
scripts/      runners for experiments that needed more than the CLI, one folder per write-up
data/         recorded runs, so validation and the benchmark re-grade without model calls
tests/
```

## Try it

```bash
pip install -e .
craftbench validate --task etl_pipeline --recorded data/recorded/etl_pipeline   # re-grades recorded runs, no model calls
craftbench grade --code path/to/code                        # live grading (needs the `claude` CLI)
craftbench bench --builders opus,gpt-6-astra --extenders opus,gemini-4-argon   # benchmark models
```
