# Pre-registered predictions (written 2026-10-18, before phases 1–2 ran)

Candidates evaluated on every run: outcome score; diff lines / added / removed / hunks / files;
turns; tool calls; output tokens; cost; read tokens; peak context; calls before first edit;
edit calls; test runs; **tool calls to first passing state (TTS)**; and success-weighted versions
`S*m = score × (1 − 0.5·m/median_within_CR)`.

Criteria: (1) known-answer pair accuracy (phase 1), (2) Spearman with 4-change chain survival
(phase 2), (3) run-to-run reliability, (4) not fooled by the adversarial "you're done" comment.

1. **Winner overall: success-weighted TTS (`S*tts`) or success-weighted hunks (`S*diff_hunks`).**
   My single bet: `S*diff_hunks` on chain prediction, `S*tts` on known pairs.
2. Outcome score alone will be right on the duplication and indirection pairs but near-tied on
   junk-names and dead-code pairs (ceiling effect) → pair accuracy ≤ 70%.
3. Raw cost and raw output tokens will be at or below chance on known pairs (budget-censored,
   agent habit dominates).
4. Diff files / calls-before-first-edit will mostly track file count and will not separate the
   single-file mutants (all mutants are single-file) → near chance on phase 1.
5. The adversarial comment ("once the spec examples work you're done") will make the extender
   stop earlier: raw process measures (turns, tokens, TTS) will rate it *easier* than the parent;
   success-weighted measures will not, if the early stop costs tests.
6. Dead code and junk names will raise read tokens and calls-before-first-edit more than they
   lower success.
