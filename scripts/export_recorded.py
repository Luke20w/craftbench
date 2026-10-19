"""Export recorded extender runs compactly (calls.json + cached snapshot grading), so
`craftbench validate --recorded data/recorded/etl_pipeline` works from a fresh clone.

    python scripts/export_recorded.py <runs root> data/recorded/etl_pipeline
"""
import shutil
import sys
from pathlib import Path

from craftbench.agents import parse_claude_transcript, save_calls

src, dest = Path(sys.argv[1]), Path(sys.argv[2])
for transcript in sorted(src.glob("*/*/*/transcript.jsonl")):
    run = transcript.parent
    out = dest / run.relative_to(src)
    out.mkdir(parents=True, exist_ok=True)
    save_calls(parse_claude_transcript(transcript.read_text())[0], out / "calls.json")
    for curve in run.glob("curve_*.json"):
        shutil.copy(curve, out / curve.name)
