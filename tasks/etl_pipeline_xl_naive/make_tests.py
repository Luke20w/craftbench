"""Fill in the expected output of every golden case in tests/m*.json by running the reference.

Each case is {"id", "steps", "dataset"}; a dataset of null means normalize only (no --execute). Rerun this
after changing a case or the reference:

    python tasks/etl_pipeline_xl/make_tests.py
"""
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
for path in sorted((HERE / "tests").glob("m*.json")):
    cases = json.loads(path.read_text())
    for case in cases:
        execute = case["dataset"] is not None
        request = {"pipeline": {"steps": case["steps"]}, "dataset": case["dataset"] if execute else []}
        res = subprocess.run([sys.executable, str(HERE / "reference" / "etl_pipeline.py"), *(["--execute"] if execute else [])],
                             input=json.dumps(request), capture_output=True, text=True, timeout=10)
        out = json.loads(res.stdout)
        out.pop("message", None)  # only its ETL_ERROR: prefix is checked
        case["code"], case["expected"] = res.returncode, out
    path.write_text(json.dumps(cases, indent=1) + "\n")
    print(f"{path.name}: {len(cases)} cases, {sum(c['code'] for c in cases)} errors")
