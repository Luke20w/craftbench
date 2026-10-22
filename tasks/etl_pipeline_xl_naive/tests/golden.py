"""Golden cases: a request, and the reference's response (minus the free-form error message)."""

import json
import subprocess
from pathlib import Path


def cases(name):
    return json.loads((Path(__file__).parent / f"{name}.json").read_text())


def check(entrypoint_argv, case):
    execute = case["dataset"] is not None
    request = {"pipeline": {"steps": case["steps"]}, "dataset": case["dataset"] if execute else []}
    res = subprocess.run([*entrypoint_argv, *(["--execute"] if execute else [])], input=json.dumps(request),
                         capture_output=True, text=True, timeout=10)
    out = json.loads(res.stdout)
    assert res.returncode == case["code"], out
    if out.get("status") == "error":
        assert out.pop("message").startswith("ETL_ERROR: ")
    assert out == case["expected"]
