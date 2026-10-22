# Experiment notes (archived as written)

Raw notes and result tables from the experiments summarised in [../EVIDENCE.md](../EVIDENCE.md).
Paths inside refer to the original scratch workspace (`.context/exp*`), which is not part of this repo.

* `PREDICTIONS.md`: pre-registered predictions for the effort-definition study
* `effort_definitions_FINDINGS.md`, `effort_definitions_RESULTS.md`: that study's write-up and full scoreboard
* `golf_confirmation.md`: 6-run golf check of the node-weighted measure
* `modeling_scale.md`: does the reward favor composable designs over if/elif at equal size
* `judge_vs_extender.md`: LLM judges vs measured change outcomes on 9 codebases
* `pattern_check.md`: static design-pattern indicators vs change outcomes on 6 codebases
* `change_mix.md`: three kinds of change request (new capability, rule everywhere, cross-cutting) on 6 codebases
* `opus_and_size.md`: Opus as the extender, and a size-matched check (bigger-but-cleaner vs smaller-but-golfed)
* `opus_reliability.md`: is the extender's signal consistent? Opus, 3 runs per cell, vs recorded Haiku runs
* `claude_builders.md`: benchmark of Claude Opus 5.5, Sonnet 5.5 and Fable 5.1 as builders (3 builds each, Opus extender)
* `xl_calibration.md`: the 52-operation task's calibration check, composable reference vs if/elif mutant
* `v_measures.md`: which way of computing change cost (probe models, panel, plan-only, judge, static metrics) predicts the real cost of owning code, measured by chains of held-out changes on the plain-language XL task
