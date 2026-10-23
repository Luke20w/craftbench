# Tasks

| task | size | role |
|---|---|---|
| [`etl_pipeline_xl_naive`](etl_pipeline_xl_naive) | 52 operations, ~12k tokens | default |
| [`etl_pipeline`](etl_pipeline) | 3 milestones, ~400–900 lines | quick checks; recorded validation runs |
| [`etl_pipeline_xl`](etl_pipeline_xl) | 52 operations, ~12k tokens | detailed change specs; XL calibration runs |
| [`docrender`](docrender) | 20 node kinds × 12 formats | known right structure, organized 6 ways |

Format: [adding a task](../docs/TASK_AUTHORING.md). Folders beyond `reference/` and `mutants/` are fixtures for
specific experiments; each task's README says which.
