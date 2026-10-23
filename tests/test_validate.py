"""The packaged grader reproduces the published validation (docs/EVIDENCE.md), from recorded runs."""

import shutil
from pathlib import Path

from craftbench.cli import main

RECORDED = Path(__file__).parent.parent / "data" / "recorded" / "etl_pipeline"


def test_recorded_validation_matches_the_published_table(tmp_path, capsys):
    for variant in ("reference", "dead_code"):  # a subset of the variants, to keep the test quick
        shutil.copytree(RECORDED / variant, tmp_path / variant)
    main(["validate", "--task", "etl_pipeline", "--recorded", str(tmp_path)])
    out = capsys.readouterr().out
    assert "| reference | 0.98 | 5,018 | 5,922 | 1.331 |" in out
    assert "| dead_code | 0.98 | 8,476 | 10,684 | 1.008 | ✓ harder |" in out
