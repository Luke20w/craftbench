#!/bin/zsh
# The whole experiment: every variant x change, 2 runs per Claude reader. Resumable: finished runs are reused.
cd "$(dirname "$0")/../.."
R() { env -u ANTHROPIC_API_KEY .venv/bin/python scripts/structure_axes/run.py "$@"; }
R claude-sonnet-5-5 2 all all 4 &
R claude-opus-5-5 2 all all 4 &
wait
echo "DRIVE DONE"
