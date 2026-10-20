"""Copy the reusable part of graded runs (benchmark builds and `validate` runs) into the repo: each
build's code and grade, and each extender run's result, calls and cached grading (no transcripts or
snapshots). Copied back into a runs directory, `craftbench bench` and `validate` reuse all of it:
finished builds aren't rebuilt and finished extender runs aren't rerun.

    python scripts/export_bench.py ~/craftbench-runs data/bench
    cp -R data/bench/. ~/craftbench-runs/          # to resume from a fresh clone
"""
import shutil
import sys
from pathlib import Path

from craftbench.sandbox import IGNORE

KEEP = ("grade.json", "build/done", "build/milestone_*/run.json", "build/milestone_*/calls.json",
        "maintain/*/*/run_*/result.json", "maintain/*/*/run_*/run.json", "maintain/*/*/run_*/calls.json",
        "maintain/*/*/run_*/curve_*.json")

src, dest = Path(sys.argv[1]), Path(sys.argv[2])
for grade in sorted(src.glob("*/bench/*/s*/grade.json")) + sorted(src.glob("*/validate_*/grade.json")):
    build = grade.parent
    out = dest / build.relative_to(src)
    if (build / "build" / "code").exists():  # validate runs grade the task's own reference and mutants
        shutil.copytree(build / "build" / "code", out / "build" / "code", dirs_exist_ok=True,
                        ignore=lambda _, names: [n for n in names if n in IGNORE])
    for pattern in KEEP:
        for f in build.glob(pattern):
            (out / f.relative_to(build)).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(f, out / f.relative_to(build))
    print(f"exported {build.relative_to(src)}")
