# Design

**Thesis:** good code is code whose structure matches the problem, so changes are cheap. Don't grade
code against a description of good code; measure what a real change costs.

## Episode

1. **Build**: the policy gets milestone specs one at a time and builds in a fresh workspace.
2. **Correctness**: hidden milestone tests → `F`.
3. **Maintain**: for each hidden change, a frozen extender (Haiku) works on its own copy of the code.
   The workspace is snapshotted after every tool call.
4. **Effort**: hidden tests run on every snapshot afterwards (no model calls).
5. **Reward**: `R = F × geomean(E)^(−λ)`, λ = 0.5.

## Effort

- **Reading, not writing.** Tokens of everything the extender's tools returned. Write-side measures
  (lines changed, turns) were fooled by a comment saying "you're done".
- **Per test.** Each hidden test is charged the reading done by the point it passed for good.
- **Code is measured in syntax nodes.** Code reads (Read, Grep/Glob, shell commands that print source) are
  converted to syntax nodes per file, so compressing code, stripping comments or shortening names doesn't
  make it cheaper to read.
- **Snapshots map to successful calls.** The hook doesn't fire for failed tool calls; effort maps snapshot
  numbers back to transcript positions.
- **No free context.** CLAUDE.md / AGENTS.md, which the harness loads unasked, are charged as read.
- **Failure is expensive.** Never-passing tests cost max(all reading, 40k tokens).

## Reward

- **Per rollout.** No batch or reference needed; the trainer compares rollouts within a group.
- **Scale-free.** Bigger changes or more reading scale every reward in a group equally.
- **Geometric mean.** Each change counts by ratio, so big changes don't swamp small ones.
- **F multiplies.** Tidy but broken code can't win.
- **Same changes per task.** Every rollout in a group is graded on the same changes.

## Pluggable

Tasks (folders), policy and extender (`Agent`), sandbox, and code analyzer (per language).

## Not done

- Chained changes (debt compounding) · more extender models
- Tasks must reach ~12k+ tokens across files before reading rewards modeling (see EVIDENCE #9)
- Golf only partly closed on small changes
- Change pool is fixed per task: a policy could learn to pre-build the changes (needs a large rotating pool)
- Containers; Harbor / verifiers integration (reward = `grade().reward`, run async after the rollout)
