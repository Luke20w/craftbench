"""Golden cases: render a document to a format and compare with the expected output exactly."""

import json
import subprocess
from pathlib import Path


def cases(name):
    return json.loads((Path(__file__).parent / f"{name}.json").read_text())


def run(entrypoint_argv, fmt, document):
    return subprocess.run([*entrypoint_argv, "--to", fmt], input=json.dumps(document), capture_output=True,
                          text=True, timeout=10)


def check(entrypoint_argv, case):
    res = run(entrypoint_argv, case["format"], case["document"])
    assert res.returncode == 0, res.stderr
    assert res.stdout == case["expected"]


def check_error(entrypoint_argv, fmt, document):
    res = run(entrypoint_argv, fmt, document)
    assert res.returncode == 2
    assert res.stderr.startswith("error:")
