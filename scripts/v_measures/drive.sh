#!/bin/zsh
# Resumable queue: every stage skips runs that already finished. Two passes, so the second picks up
# codebases that appeared (or changed) during the first.
cd "${0:A:h}/../.."
R() { env -u ANTHROPIC_API_KEY .venv/bin/python scripts/v_measures/run.py "$@"; }
for pass in 1 2; do
  R chain claude-sonnet-5-5 1 all 4
  R chain claude-opus-5-5 1 all 4
  R probe claude-opus-5-5 2 all 4
  R probe claude-sonnet-5-5 2 all 4
  R plan claude-sonnet-5-5 1 all 4
  R judge claude-sonnet-5-5 2 all 4
done
echo "DRIVE DONE"
