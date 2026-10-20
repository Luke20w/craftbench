# etl_pipeline_xl

`etl_pipeline` grown to 52 operations over 7 milestones. Milestones 1–3 are unchanged; milestones 4–7 add
column, text, number/grouping and row operations in batches, so a builder that models operations well early
gains on every later batch. The finished reference is ~1,400 lines across 15 files (~12k tokens), past the
size at which reading cost starts to reflect structure rather than size.

* `reference/`: composable design, one small class per operation built from shared field kinds.
* `mutants/if_elif/`: the same behaviour written as one if/elif chain for validation and one for execution.
  It should always rate as harder to change; that's this task's calibration check.
* `tests/m*.json`: golden cases for milestones 4–7; `make_tests.py` refills their expected outputs from the
  reference.

Milestones 1–3, `subpipelines` and `trace` come from `etl_pipeline` (milestone 1–3 and sub-pipeline specs and
tests are adapted from [SlopCodeBench](https://github.com/gabeorlanski/scb-problems), Apache-2.0, see
`LICENSE-slopcodebench`). `case` and the 52-operation `limits` are new.
