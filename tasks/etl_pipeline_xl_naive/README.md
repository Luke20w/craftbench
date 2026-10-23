# etl_pipeline_xl_naive

The default task: a CLI ETL tool grown to 52 operations over 7 milestones (~1,400 lines across 15 files in the
reference, ~12k tokens), with every spec written as a plain ask plus the contract the tests check.

* `reference/`: composable, one small class per operation built from shared field kinds.
* `mutants/`: same behaviour, one known flaw each (`if_elif`, `dead_code`, `duplicated`, `junk_names`, `golfed`).
* `[[held_out]]` changes `h1`–`h4`: applied in sequence, the answer key for what a codebase costs to own;
  `chain_reference/` is the reference after each step.
* `[[big_changes]]`: probes that touch most operations; `big_reference/` implements each.
* `exploits/`: attempts to raise the reward without better code ([status](exploits/README.md)).
* `trust_gap/`: the reference with one guarantee expressed four ways.
* `make_*tests.py` refill the golden tests from the references.

`etl_pipeline_xl` is the same code and tests with the earlier, more detailed change specs. Milestones 1–3 and
sub-pipelines are adapted from [SlopCodeBench](https://github.com/gabeorlanski/scb-problems) (Apache-2.0, see
`LICENSE-slopcodebench`).
