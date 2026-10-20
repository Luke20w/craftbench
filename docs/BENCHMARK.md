# Benchmarking models

**Builders** write the task's code from the milestone specs. A fixed **panel of extenders** then makes the
hidden changes on every build. Builders are compared on F (milestone tests passing), effort per change, and
the reward.

## Setup

Each model runs in its vendor's coding CLI. The model id picks the CLI; use `harness:model` to override.

| Model ids | CLI | Install | Auth |
|---|---|---|---|
| `claude-*`, `haiku`, `sonnet`, `opus` | Claude Code | [claude.com/claude-code](https://claude.com/claude-code) | `claude` login or `ANTHROPIC_API_KEY` |
| `gpt-*` | Codex | `npm i -g @openai/codex` | `CODEX_API_KEY` or `codex login` |
| `gemini-*` | Gemini CLI | `npm i -g @google/gemini-cli` | `GEMINI_API_KEY` |

Only Claude Code has a per-run dollar cap (`--builder-budget`, `--extender-budget`). Codex and Gemini stop
at a 30-minute timeout, so set a spending limit in each provider's console.

## Run

```bash
# One tiny change per model: checks the CLI runs, its tool calls parse with real sizes, and snapshots appear
craftbench smoke --extenders claude-opus-5-5,gpt-6-astra,gemini-4-argon

# Every builder builds the task 3 times; every extender makes every change on every build
craftbench bench --builders claude-opus-5-5,gpt-6-astra,gemini-4-argon \
                 --extenders claude-opus-5-5,gpt-6-astra,gemini-4-argon --runs 3
```

## Keeping results

- **Nothing finished is redone.** A finished build is never rebuilt, and each extender run is reused
  for as long as the code, prompt and extender are the same. Rerunning resumes an interrupted
  benchmark; adding builds (`--runs 5`) or extenders (`--extenders ...,gpt-6-astra`) later only runs
  what's new.
- **Keep the runs directory outside the checkout:** `--runs-dir ~/craftbench-runs`, or set
  `CRAFTBENCH_RUNS`. Builds live at `<runs dir>/<task>/bench/<builder>/s<k>`.
- **Commit the reusable part:** `python scripts/export_bench.py ~/craftbench-runs data/bench` copies each
  build's code and grade and each extender run's result (no transcripts or snapshots). To resume from a
  fresh clone, copy it back: `cp -R data/bench/. ~/craftbench-runs/`.

## Usage

Every agent run writes a `run.json` next to its logs: cost at API prices, tokens, and, for Claude
Code, the subscription's 5-hour and weekly usage. `craftbench usage` adds them up by model and role,
and `bench` prints the same summary at the end.

On a Claude subscription, each run checks the latest usage report before it starts. Above `--max-5h`
(default 0.8) it pauses until the 5-hour window resets. Above `--max-week` (default 0.5), or once extra
usage is being billed, it stops; finished work is kept for the next run.

## The report

1. **Builders:** builds, F, reward and effort per change (medians, range in brackets), and code size in
   syntax nodes. Read effort next to size: on small tasks the reward mostly tracks size
   ([EVIDENCE](EVIDENCE.md) #7, #11).
2. **Effort by extender:** each extender's effort for each builder, relative to its typical builder
   (1.00 = typical, lower = easier to change). If an extender rates its own family's code easier than the
   other extenders do, that is self-preference, and the panel is what cancels it.

## How the panel is combined

A change's effort is each extender's mean over its runs, then the geometric mean across extenders. An
extender that reads less across the board (a stronger model) scales every build's reward by the same factor,
so no single reader's scale decides the ranking.

## How each CLI is measured

- **Same tool vocabulary.** Tool calls are mapped onto Claude Code's names (`read_file` → Read, shell →
  Bash, …), so the [effort](DESIGN.md#effort) rules apply to every extender the same way.
- **Snapshots.** Claude Code snapshots after every tool call through a hook. Codex and Gemini are polled
  every 0.5 s, and each snapshot is lined up with the tool calls whose results had arrived by then.
- **What was read.** Codex reports command output directly. Gemini's event stream only carries display
  summaries ("Read 120 lines"), so its reading is taken from the session log it writes.
- **Isolation.** User config is ignored where the CLI allows it (Claude `--setting-sources project`, Codex
  `--ignore-user-config`, Gemini runs with its own home). Web search and subagents are off. Everything
  else, such as reasoning effort and system prompts, is the vendor's default.

## Limits

- **Codex and Gemini are not yet checked against live runs.** Their parsers follow each CLI's documented or
  source-level output format. Run `smoke` before anything bigger.
- **Model plus harness.** Each builder runs in its own vendor's CLI, so a result is "GPT in Codex", not GPT
  alone.
- **One small task.** Structure only shows in reading cost once code is too big to hold in context
  ([EVIDENCE](EVIDENCE.md) #8–9), so rankings on `etl_pipeline` partly reflect who writes less code.
