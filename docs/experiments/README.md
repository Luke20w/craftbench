# Experiments

One write-up per experiment, in the order they ran, kept as written; [EVIDENCE](../EVIDENCE.md) summarises them.
Experiments with their own runners have a matching folder in [`scripts/`](../../scripts).

| write-up | question | runner |
|---|---|---|
| [effort_definitions](effort_definitions.md) ([predictions](effort_definitions_predictions.md), [results](effort_definitions_results.md)) | what "effort to change" should mean | |
| [golf_confirmation](golf_confirmation.md) | does compressed code fool it | |
| [judge_vs_extender](judge_vs_extender.md) | LLM judges vs measured changes | |
| [change_mix](change_mix.md) | which kinds of change separate codebases | |
| [pattern_check](pattern_check.md) | do design patterns predict cost on small code | |
| [modeling_scale](modeling_scale.md) | composable vs if/elif as code grows | |
| [opus_and_size](opus_and_size.md) | a stronger reader; size-matched variants | |
| [opus_reliability](opus_reliability.md) | is one reader consistent | |
| [claude_builders](claude_builders.md) | benchmark of Claude builders | `craftbench bench` |
| [xl_calibration](xl_calibration.md) | composable vs if/elif at 52 operations | `craftbench validate` |
| [v_measures](v_measures.md) | which measure predicts long-run cost; exploits, selection, real repos | [v_measures](../../scripts/v_measures) |
| [review_followups](review_followups.md) | notes, defects, invariants, a third reader | [review_followups](../../scripts/review_followups) |
| [structure_axes](structure_axes.md) | a domain where the right structure is known | [structure_axes](../../scripts/structure_axes) |
| [precision](precision.md) | can it rank one policy's rollouts | [precision](../../scripts/precision) |

Early write-ups refer to scratch paths (`.context/exp*`) that aren't part of the repo.
