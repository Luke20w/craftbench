"""Golden cases for the held-out change chain (h1–h4): CLI flags, stdin, and the expected response minus
the free-form error message. Written by make_chain_tests.py."""

import json
import subprocess
from pathlib import Path


def cases(name):
    return json.loads((Path(__file__).parent / f"{name}.json").read_text())


def part_of(out, part):
    """`ops.select` -> out["ops"]["select"]; a final `__keys__` gives the sorted keys of that object."""
    for key in part.split("."):
        out = sorted(out) if key == "__keys__" else out[key]
    return out


def check(entrypoint_argv, case):
    stdin = case["raw"] if "raw" in case else json.dumps(case["request"])
    res = subprocess.run([*entrypoint_argv, *case["flags"]], input=stdin, capture_output=True, text=True,
                         timeout=10)
    assert res.returncode == case["code"], res.stdout + res.stderr
    out = json.loads(res.stdout)
    if out.get("status") == "error":
        assert out.pop("message").startswith("ETL_ERROR: ")
    if "part" in case:
        out = part_of(out, case["part"])
    assert out == case["expected"]
