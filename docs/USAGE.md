# Usage

## Grading code

```bash
craftbench grade --code path/to/code --task etl_pipeline_xl_naive
```

This runs the hidden milestone tests (F), then has each extender in the panel (default: Sonnet 5.5 and Opus 5.5,
2 runs each) make every hidden change on its own copy of the code. It prints the reward, the effort per change
and per extender, and some code metrics that are logged but never rewarded.

The rules for counting what an extender read are in [`effort.py`](../craftbench/effort.py). Each one closes a gap
an experiment found. A change's effort is each extender's mean over its runs, then the geometric mean across
extenders, so a reader that reads less across the board scales every rollout the same.

In a training loop, call the environment directly:

```python
env = Environment(load_task("etl_pipeline_xl_naive"))
ep = env.reset()
for prompt in ep.prompts:
    ...  # the policy works in ep.workspace until this milestone is done
reward = env.grade(ep.workspace, ep.dir).reward
```

Any coding-CLI `Agent` can play the policy with `env.run_episode(agent)`.

## Benchmarking models

Builders (the policies being benchmarked) write the task's code from the milestone specs. The extender panel then makes the hidden changes on
every build.

```bash
# One tiny change per model: checks the CLI runs, its tool calls parse with real sizes, and snapshots appear
craftbench smoke --extenders claude-opus-5-5,gpt-6-astra,gemini-4-argon

# Every builder builds the task 3 times; every extender makes every change on every build
craftbench bench --builders claude-opus-5-5,gpt-6-astra,gemini-4-argon \
                 --extenders claude-opus-5-5,gpt-6-astra,gemini-4-argon --runs 3
```

Each model runs in its vendor's coding CLI, picked from the model id (`harness:model` overrides it):

| Model ids | CLI | Install | Auth |
|---|---|---|---|
| `claude-*`, `haiku`, `sonnet`, `opus` | Claude Code | [claude.com/claude-code](https://claude.com/claude-code) | `claude` login or `ANTHROPIC_API_KEY` |
| `gpt-*` | Codex | `npm i -g @openai/codex` | `CODEX_API_KEY` or `codex login` |
| `gemini-*` | Gemini CLI | `npm i -g @google/gemini-cli` | `GEMINI_API_KEY` |

- **Every CLI is measured the same way.** Tool calls are mapped onto Claude Code's names (`read_file` → Read,
  shell → Bash, …). Claude Code snapshots the workspace after every tool call through a hook; Codex and Gemini
  are polled every 0.5 s. User config, web search and subagents are off.
- **Nothing finished is redone.** Rerunning resumes an interrupted benchmark, and adding builds or extenders
  later only runs what's new. Keep runs outside the checkout (`--runs-dir ~/craftbench-runs` or `CRAFTBENCH_RUNS`).
- **Spending.** Only Claude Code has a per-run dollar cap (`--builder-budget`, `--extender-budget`); Codex and
  Gemini stop at a 30-minute timeout. On a Claude subscription, runs pause when the 5-hour window passes
  `--max-5h` (0.8) and stop past `--max-week` (0.5) or once extra usage is billed. `craftbench usage` adds up
  what every run cost.

The report shows each builder's F, reward, effort per change and code size, then each extender's effort per
builder relative to its typical builder. On small tasks the reward mostly tracks size, so read effort next to it.
A result is a model in its own vendor's CLI ("GPT in Codex"), not the model alone.

## Tasks

| task | size | used for |
|---|---|---|
| `etl_pipeline_xl_naive` | 52 operations over 7 milestones, ~12k tokens | the default; "naive" because its specs are plain asks with no structural hints, unlike the retired `etl_pipeline_xl` |
| `etl_pipeline` | 3 milestones, ~400–900 lines | quick checks and the recorded validation runs |
| `docrender` | 20 node kinds × 12 formats, organized 6 ways | structure axes; `gen/make.py` generates it |

A task is a folder; adding one needs no code changes. The README's checkpoints are a task's milestones (built by
the policy) followed by its changes (made by the extenders).

```
tasks/<id>/
  task.toml      how to run the program; [[milestones]] the policy builds, [[changes]] the extenders make
  specs/         one markdown spec per milestone and change
  tests/         hidden pytest tests + conftest.py
  reference/     optional: a good solution
  mutants/       optional: same behaviour, one deliberate flaw each (`control_*`: identical code, only a comment added)
```

`docrender` has no flawed copies: its six organizations in `variants/` behave identically, and `by_format` doubles
as the reference.

- **Tests run the program from the outside** (CLI or HTTP), never import it.
- **Big enough that structure shows.** The reference should reach ~12k tokens across files. Below ~7k a model
  reads everything and the reward only measures size.
- **Specs are plain asks.** Write them the way a user would ("we need X", "we're seeing Y"), plus the observable
  contract the tests check. Don't describe the structure or hint at what comes next: working that out is what's
  being measured.
- **Mix kinds of change**: a new capability, a rule that applies everywhere, a cross-cutting concern, removing
  behaviour, a sibling of something that exists. Each kind exposes a different flaw.

```bash
craftbench check-task --task <id>    # the reference passes the milestones; change tests mostly fail on it
craftbench validate --task <id>      # the reference is rated easier than every mutant (runs the extenders)
```

The ETL tasks adapt specs and tests from [SlopCodeBench](https://github.com/gabeorlanski/scb-problems)
(Apache-2.0, see each task's `LICENSE-slopcodebench`), modified for CraftBench; their canary headers are kept so
training pipelines can filter them.

## Not built yet

- **A rotating change pool.** Each task's changes are fixed. Code that already contains a change is charged as a
  failure, but a large pool would remove the incentive altogether.
- **Containers.** The sandbox copies the workspace, but the interpreter and file system are shared.
- **Gemini against live runs.** Its parser follows the CLI's documented output. Run `smoke` before anything bigger.
