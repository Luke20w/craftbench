# Phase 1–3 results: which definition of effort-to-change holds up?

## Phase 1 raw: parent vs single-change degradations (mean of 2 runs)

| variant | CR | score | tts reached | tts calls | diff lines | hunks | turns | out tokens | read tokens | calls before 1st edit | test runs |
|---|---|---|---|---|---|---|---|---|---|---|---|
| parent | limits | 1.00 | 2/2 | 8 | 50 | 9 | 50 | 21666 | 7706 | 2.5 | 34.0 |
| parent | subpipelines | 1.00 | 2/2 | 18 | 116 | 22 | 49 | 20075 | 7496 | 2.0 | 28.0 |
| junk_names | limits | 1.00 | 2/2 | 12 | 16 | 8 | 45 | 16528 | 8112 | 2.5 | 25.0 |
| junk_names | subpipelines | 0.91 | 1/2 | 26 | 76 | 12 | 42 | 21549 | 7099 | 3.5 | 26.5 |
| dead_code | limits | 1.00 | 2/2 | 8 | 50 | 19 | 48 | 22556 | 10538 | 2.5 | 28.5 |
| dead_code | subpipelines | 1.00 | 2/2 | 19 | 122 | 25 | 44 | 19176 | 12980 | 2.0 | 14.0 |
| duplicated | limits | 1.00 | 2/2 | 12 | 36 | 16 | 44 | 21354 | 12648 | 2.5 | 21.0 |
| duplicated | subpipelines | 0.97 | 2/2 | 18 | 138 | 24 | 44 | 20816 | 9376 | 2.0 | 23.5 |
| indirection | limits | 1.00 | 2/2 | 8 | 24 | 9 | 32 | 15432 | 7760 | 2.5 | 18.0 |
| indirection | subpipelines | 0.91 | 1/2 | 28 | 113 | 26 | 44 | 21008 | 8572 | 2.5 | 24.0 |
| adversarial_note | limits | 1.00 | 2/2 | 7 | 18 | 8 | 41 | 20310 | 7785 | 2.0 | 28.5 |
| adversarial_note | subpipelines | 1.00 | 2/2 | 12 | 88 | 18 | 42 | 19714 | 7281 | 2.0 | 25.5 |

## Scoreboard

* **pair acc**: share of (parent, degraded copy) comparisons where the measure says the parent is easier to change (4 known-answer degradations × 2 change requests; 0.5 = chance).
* **signal/noise**: average parent-vs-copy gap divided by the run-to-run spread.
* **chain pred**: Spearman between the measure on change 1 of the chain and the average outcome on changes 2–4 (n = 6 codebases; + = predicts correctly).
* **reliability**: run 0 vs run 1 agreement across the 12 (variant, CR) cells.
* **adversarial**: 1 = rated the copy with the misleading 'you're done' note as easier than the identical parent (fooled), 0 = not fooled.

| measure | pair acc | signal/noise | chain pred | reliability | adversarial |
|---|---|---|---|---|---|
| read_code_tokens | 1.00 | 2.25 | +0.83 | +0.45 | 0.50 |
| read_to_tts | 1.00 | 2.81 | +1.00 | +0.85 | 0.50 |
| read_code_to_tts | 1.00 | 2.81 | +0.83 | +0.61 | 0.50 |
| read_to_70 | 1.00 | 4.62 | +0.94 | +0.85 | 0.00 |
| read_to_80 | 1.00 | 5.04 | +0.94 | +0.92 | 0.00 |
| read_to_90 | 1.00 | 2.46 | +0.94 | +0.72 | 0.50 |
| read_to_100 | 1.00 | 2.95 | +0.94 | +0.76 | 1.00 |
| read_per_test | 1.00 | 2.79 | +0.94 | +0.83 | 0.50 |
| S*read_tokens | 1.00 | 2.23 | +0.77 | +0.33 | 0.50 |
| S*read_code_tokens | 1.00 | 2.74 | +0.89 | +0.66 | 0.50 |
| S*read_to_tts | 1.00 | 3.58 | +0.71 | +0.80 | 0.50 |
| S*read_code_to_tts | 1.00 | 3.53 | +0.89 | +0.78 | 0.50 |
| S*read_to_70 | 1.00 | 5.87 | +0.77 | +0.92 | 0.00 |
| S*read_to_80 | 1.00 | 6.27 | +0.77 | +0.92 | 0.00 |
| S*read_to_90 | 1.00 | 3.02 | +0.77 | +0.72 | 0.50 |
| S*read_to_100 | 1.00 | 3.59 | +0.77 | +0.85 | 1.00 |
| S*read_per_test | 1.00 | 4.06 | +0.77 | +0.79 | 0.50 |
| read_tokens | 0.88 | 1.91 | +0.94 | +0.41 | 0.50 |
| S*cost_usd | 0.75 | 1.06 | +0.49 | +0.17 | 1.00 |
| score | 0.69 | 1.24 | +0.49 | +0.52 | 0.50 |
| diff_hunks | 0.69 | 2.37 | +0.84 | +0.84 | 1.00 |
| tts_calls | 0.69 | 0.76 | +0.77 | +0.74 | 1.00 |
| S*diff_hunks | 0.69 | 2.54 | +0.94 | +0.58 | 1.00 |
| S*diff_files | 0.69 | 1.24 | +0.93 | +0.52 | 0.50 |
| S*calls_before_first_edit | 0.69 | 0.37 | +0.89 | -0.32 | 0.75 |
| S*tts_calls | 0.69 | 0.81 | +0.77 | +0.23 | 1.00 |
| calls_before_first_edit | 0.62 | 0.39 | +0.88 | -0.40 | 0.75 |
| tts_tokens | 0.62 | 1.37 | +0.31 | +0.70 | 0.50 |
| S*tts_tokens | 0.62 | 1.30 | +0.60 | +0.34 | 0.50 |
| diff_files | 0.50 | inf | +0.88 | +nan | 0.50 |
| out_tokens | 0.50 | 1.11 | -0.26 | +0.08 | 1.00 |
| S*diff_lines | 0.50 | 1.69 | +0.67 | +0.67 | 1.00 |
| S*out_tokens | 0.50 | 1.30 | +0.37 | +0.22 | 1.00 |
| diff_lines | 0.38 | 1.44 | +0.43 | +0.92 | 1.00 |
| cost_usd | 0.38 | 1.20 | +0.60 | +0.20 | 1.00 |
| turns | 0.00 | 1.33 | +0.29 | +0.09 | 1.00 |
| tool_calls | 0.00 | 1.25 | +0.29 | +0.15 | 1.00 |
| test_runs | 0.00 | 1.28 | -0.94 | -0.11 | 1.00 |
| S*turns | 0.00 | 1.06 | +0.54 | +0.15 | 1.00 |
| S*tool_calls | 0.00 | 0.98 | +0.54 | +0.12 | 1.00 |
| S*test_runs | 0.00 | 1.19 | -0.43 | -0.17 | 1.00 |

## Phase 2: chain outcomes per base (score per step: C4 → limits → trace → C5)

| base | C4 | limits | trace | C5 | mean 2–4 | step-1 tts calls | step-1 hunks |
|---|---|---|---|---|---|---|---|
| sonnet_natural | 1.00 | 1.00 | 1.00 | 0.87 | 0.96 | 24 | 22 |
| haiku_natural | 0.78 | 0.95 | 1.00 | 0.90 | 0.95 | 40 | 17 |
| monolith | 0.83 | 1.00 | 0.89 | 0.87 | 0.92 | 30 | 25 |
| copypaste | 0.88 | 1.00 | 0.82 | 0.87 | 0.90 | 39 | 41 |
| overengineered | 0.00 | 1.00 | 0.89 | 0.63 | 0.84 | 55 | 28 |
| clean | 0.83 | 1.00 | 0.67 | 0.20 | 0.62 | 43 | 41 |

Runs: phase 1 = 24, phase 2 = 24.
