# Change mix: three kinds of change request (exp2)

6 codebases (all at milestone 3 of the ETL task), 3 change requests of different kinds, Haiku extender, 2 runs each.
Run-to-run agreement on the ranking: +0.89 (vs +0.51 with the single easy change in [judge_vs_extender.md](judge_vs_extender.md)).


Bases = run-1 codebases after C3. Extender = Haiku, 40 turns. Score = new-feature pass fraction × regression retained (vs the base's own C1–C3 pass count).

## Overall per base (mean over change requests and runs)

| base | score | sub-pipelines | limits (rule everywhere) | trace (cross-cutting) | turns | lines changed | files changed | hit turn cap |
|---|---|---|---|---|---|---|---|---|
| sonnet_natural | **0.98** | 1.00 (1.00, 1.00) | 1.00 (1.00, 1.00) | 0.94 (1.00, 0.89) | 37 | 69 | 4.5 | 4/6 |
| haiku_natural | **0.98** | 1.00 (1.00, 1.00) | 1.00 (1.00, 1.00) | 0.94 (0.89, 1.00) | 32 | 136 | 2.3 | 3/6 |
| monolith | **0.95** | 0.85 (0.88, 0.83) | 1.00 (1.00, 1.00) | 1.00 (1.00, 1.00) | 39 | 117 | 5.3 | 4/6 |
| clean | **0.77** | 0.41 (0.04, 0.77) | 1.00 (1.00, 1.00) | 0.89 (0.89, 0.89) | 40 | 150 | 4.3 | 5/6 |
| copypaste | **0.70** | 0.26 (0.36, 0.16) | 0.85 (0.85, 0.85) | 1.00 (1.00, 1.00) | 36 | 174 | 6.5 | 4/6 |
| overengineered | **0.52** | 0.00 (0.00, 0.00) | 0.90 (0.95, 0.85) | 0.67 (0.67, 0.67) | 41 | 149 | 6.3 | 6/6 |

## Per change request: new-feature pass / regression retained / turns

| base | subpipelines | limits | trace |
|---|---|---|---|
| sonnet_natural | 17/17 · 100% · 41t ; 17/17 · 100% · 41t | 20/20 · 100% · 41t ; 20/20 · 100% · 41t | 9/9 · 100% · 25t ; 8/9 · 100% · 33t |
| haiku_natural | 17/17 · 100% · 41t ; 17/17 · 100% · 41t | 20/20 · 100% · 41t ; 20/20 · 100% · 38t | 8/9 · 100% · 15t ; 9/9 · 100% · 17t |
| monolith | 17/17 · 88% · 41t ; 16/17 · 88% · 41t | 20/20 · 100% · 39t ; 20/20 · 100% · 41t | 9/9 · 100% · 41t ; 9/9 · 100% · 31t |
| clean | 3/17 · 24% · 41t ; 15/17 · 88% · 41t | 20/20 · 100% · 41t ; 20/20 · 100% · 41t | 8/9 · 100% · 41t ; 8/9 · 100% · 36t |
| copypaste | 7/17 · 88% · 41t ; 3/17 · 88% · 41t | 17/20 · 100% · 41t ; 17/20 · 100% · 41t | 9/9 · 100% · 25t ; 9/9 · 100% · 25t |
| overengineered | 0/17 · 0% · 41t ; 0/17 · 100% · 41t | 19/20 · 100% · 41t ; 17/20 · 100% · 41t | 6/9 · 100% · 41t ; 6/9 · 100% · 41t |

Run-to-run agreement of the base ranking (run 0 vs run 1, Spearman): score +0.89, turns +0.88

Runs: 36. Spend: $9.94. Peeked at hidden tests: 0.
