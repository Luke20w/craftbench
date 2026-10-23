# Design

**Thesis:** good code is code whose structure matches the problem, so changes are cheap. Don't grade
code against a description of good code; measure what a real change costs.

## Episode

1. **Build**: the policy gets milestone specs one at a time and builds in a fresh workspace.
2. **Correctness**: hidden milestone tests → `F`.
3. **Maintain**: for each hidden change, each frozen extender in the panel (default: Sonnet 5.5 and
   Opus 5.5, 2 runs each) works on its own copy of the code. The workspace is snapshotted after every tool call.
4. **Effort**: hidden tests run on every snapshot afterwards (no model calls).
5. **Reward**: `R = F × geomean(E)^(−λ)`, λ = 0.5.

## Effort

The rules live in [`effort.py`](../craftbench/effort.py); each one closes a gap an experiment found.

- **Reading, not writing.** Tokens of everything the extender's tools returned. Write-side measures
  (lines changed, turns) were fooled by a comment saying "you're done" ([EVIDENCE](EVIDENCE.md) #4).
- **Per test.** Each hidden test is charged the reading done by the point it passed for good, with ≥ 98% of
  the milestone tests still passing.
- **Code is measured in syntax nodes.** A read of source code (Read, Grep, or a shell command that prints
  files) is weighted by the syntax nodes of the files it read, so compressing code, stripping comments or
  shortening names doesn't make it cheaper to read (#5). Any file that defines or imports code counts as
  code, whatever it is called, and a file that doesn't parse is estimated rather than counted as empty.
- **Nothing reads for less than its tokens.** Weights are at least 1 and averaged by how much code each file
  holds, so docstrings and padding can't dilute the code around them.
- **No credit for what was already there.** Tests that pass on the untouched code aren't charged. A change
  whose tests *all* pass already is charged as a failure: code that contains a feature nobody has asked for
  has learned the change set.
- **No free context.** CLAUDE.md / AGENTS.md / GEMINI.md, which the harness loads unasked, are charged as read.
- **Failure is expensive.** Never-passing tests cost max(all reading, 40k tokens).
- **Snapshots map to successful calls.** The hook doesn't fire for failed tool calls; effort maps snapshot
  numbers back to transcript positions, and the final workspace is always snapshotted.
- **Broken runs aren't scored.** A run cut off by an API error is rerun, not charged as a failure.

## Panel

A change's effort is each extender's mean over its runs, then the geometric mean across extenders, so a
stronger reader's lower reading scales every rollout equally. Readers disagree about which code is easy to
change, and each predicts its own long-run cost best (#20–21), so the panel buys breadth: no future
maintainer is badly served. Add other families with `--extenders` (see [benchmarking](BENCHMARK.md)).

## Reward

- **Per rollout.** No batch or reference needed; the trainer compares rollouts within a group.
- **Scale-free.** Bigger changes or more reading scale every reward in a group equally.
- **Geometric mean.** Each change counts by ratio, so big changes don't swamp small ones.
- **F multiplies.** Tidy but broken code can't win.
- **Same changes per task.** Every rollout in a group is graded on the same changes.

## Pluggable

Tasks (folders, see [adding a task](TASK_AUTHORING.md)), policy and extenders (`Agent`: Claude Code, Codex,
Gemini CLI), sandbox, and code analyzer (per language).

## Not done

- **Precision.** One measurement's noise (~10–15%) is larger than the gap between near-identical rollouts (#28).
- **A rotating change pool.** Each task's changes are fixed; pre-built changes are now charged as failures,
  but a large pool would remove the incentive altogether.
- **Chained changes** in the reward (they are used as the answer key in experiments, not in episodes).
- **Gemini** checked against live runs; containers; Harbor / verifiers integration
  (reward = `grade().reward`, run async after the rollout).
