"""Build the docrender task: the six variants, the golden outputs and the hidden tests.

    python tasks/docrender/gen/make.py

Every variant must render every test document identically, or this stops.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
TASK = HERE.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(TASK.parent.parent))
from cells import FORMATS, KINDS  # noqa: E402
from changes import MODIFIED, NEW_FORMATS, NEW_KINDS  # noqa: E402
from corpus import BASE, CHANGE_DOCS, doc, para, t  # noqa: E402
from emit import README as README_TEXT  # noqa: E402
from emit import VARIANTS, emit  # noqa: E402

from craftbench.analysis import ANALYZERS, size, source_files  # noqa: E402


def render(code: Path, fmt: str, document: dict) -> tuple[int, str, str]:
    res = subprocess.run([sys.executable, str(code / "docrender.py"), "--to", fmt], input=json.dumps(document),
                         capture_output=True, text=True, timeout=30)
    return res.returncode, res.stdout, res.stderr


def render_all(code: Path, jobs: list[tuple[str, str, dict]]) -> dict[tuple[str, str], str]:
    with ThreadPoolExecutor(16) as pool:
        outs = list(pool.map(lambda j: render(code, j[1], j[2]), jobs))
    result = {}
    for (name, fmt, _), (rc, out, err) in zip(jobs, outs):
        assert rc == 0, f"{code.name} {name} {fmt}: {err}"
        result[(name, fmt)] = out
    return result


def golden(cases_id: str, jobs, outputs) -> list[dict]:
    return [{"id": f"{fmt}-{name}", "format": fmt, "document": d, "expected": outputs[(name, fmt)]}
            for name, fmt, d in jobs]


def main():
    variants = TASK / "variants"
    base_jobs = [(name, fmt, d) for fmt in FORMATS for name, d in BASE.items()]
    reference = None
    for v in VARIANTS:
        emit(v, variants / v, FORMATS, KINDS)
        outs = render_all(variants / v, base_jobs)
        if reference is None:
            reference = outs
        bad = [k for k in reference if outs[k] != reference[k]]
        assert not bad, f"{v} differs from {next(iter(VARIANTS))} on {bad[:5]}"
        rc, _, err = render(variants / v, "docx", doc(para(t("x"))))
        assert rc == 2 and err.startswith("error:"), (v, rc, err)
        rc, _, err = render(variants / v, "html", doc({"type": "video", "src": "a.mp4"}))
        assert rc == 2 and err.startswith("error:"), (v, rc, err)
        files = source_files(variants / v, ANALYZERS["python"])
        chars = sum(len(f.read_text()) for f in files)
        loc, nodes, _ = size(variants / v, ANALYZERS["python"])
        print(f"{v:10} files {len(files):3}  loc {loc:5}  nodes {nodes:6}  ~tokens {chars // 4:6}  identical: yes")

    tests = TASK / "tests"
    tests.mkdir(exist_ok=True)
    (tests / "base.json").write_text(json.dumps(golden("base", base_jobs, reference), indent=1, ensure_ascii=False))

    with tempfile.TemporaryDirectory() as tmp:
        for kind, cells in NEW_KINDS.items():
            formats = {f: {**c, kind: cells[f]} for f, c in FORMATS.items()}
            after = Path(tmp) / kind
            emit("by_format", after, formats, KINDS + [kind])
            jobs = [(name, fmt, d) for fmt in FORMATS for name, d in CHANGE_DOCS[kind].items()]
            outs = render_all(after, jobs)
            assert render_all(after, base_jobs) == reference
            (tests / f"{kind}.json").write_text(json.dumps(golden(kind, jobs, outs), indent=1, ensure_ascii=False))
            print(f"change {kind}: {len(jobs)} tests")
        for fmt, cells in NEW_FORMATS.items():
            after = Path(tmp) / fmt
            emit("by_format", after, {**FORMATS, fmt: cells}, KINDS)
            jobs = [(name, fmt, d) for name, d in BASE.items()]
            outs = render_all(after, jobs)
            assert render_all(after, base_jobs) == reference
            (tests / f"{fmt}.json").write_text(json.dumps(golden(fmt, jobs, outs), indent=1, ensure_ascii=False))
            print(f"change {fmt}: {len(jobs)} tests")

        for name, changed in MODIFIED.items():
            formats = {f: {**c, **changed.get(f, {})} for f, c in FORMATS.items()}
            after = Path(tmp) / name
            emit("by_format", after, formats, KINDS)
            jobs = [(doc_name, fmt, d) for fmt in FORMATS for doc_name, d in CHANGE_DOCS[name].items()]
            outs = render_all(after, jobs)
            assert render_all(after, base_jobs) == reference
            (tests / f"{name}.json").write_text(json.dumps(golden(name, jobs, outs), indent=1, ensure_ascii=False))
            print(f"change {name}: {len(jobs)} tests, {sum(1 for f in FORMATS if f in changed)} formats change")

    write_tests(tests)
    write_specs()

    # every change's tests must fail on every starting variant
    for v in VARIANTS:
        for name in [*NEW_KINDS, *NEW_FORMATS, *MODIFIED]:
            case = json.loads((tests / f"{name}.json").read_text())[0]
            rc, out, _ = render(variants / v, case["format"], case["document"])
            assert rc != 0 or out != case["expected"], (v, name)


CHANGES = {"k1_strikethrough": "strikethrough", "k2_callout": "callout", "k3_definition_list": "definition_list",
           "f1_asciidoc": "asciidoc", "f2_textile": "textile", "f3_rst": "rst",
           "s1_list_start": "list_start", "s2_quote_cite": "quote_cite", "s3_default_alt": "default_alt"}

GOLDEN_PY = '''"""Golden cases: render a document to a format and compare with the expected output exactly."""

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
'''

CONFTEST_PY = '''import shlex

import pytest


def pytest_addoption(parser):
    parser.addoption("--entrypoint", action="store", required=True, help="Full command to run the submission")


@pytest.fixture(scope="session")
def entrypoint_argv(request):
    return shlex.split(request.config.getoption("--entrypoint"))
'''

TEST_PY = '''"""Hidden tests for {what}: golden cases in {name}.json (see gen/make.py)."""

import pytest

from golden import cases, check{extra_import}


@pytest.mark.parametrize("case", cases("{name}"), ids=lambda c: c["id"])
def test_golden(entrypoint_argv, case):
    check(entrypoint_argv, case)
{extra}'''

ERROR_TESTS = '''

def test_unknown_format(entrypoint_argv):
    check_error(entrypoint_argv, "docx", {"type": "document", "children": []})


def test_unknown_node_type(entrypoint_argv):
    check_error(entrypoint_argv, "html", {"type": "document", "children": [{"type": "video", "src": "a.mp4"}]})
'''


def write_tests(tests: Path) -> None:
    (tests / "golden.py").write_text(GOLDEN_PY)
    (tests / "conftest.py").write_text(CONFTEST_PY)
    (tests / "test_base.py").write_text(TEST_PY.format(what="the existing behaviour", name="base",
                                                       extra_import=", check_error", extra=ERROR_TESTS))
    for change, name in CHANGES.items():
        (tests / f"test_{change}.py").write_text(TEST_PY.format(what=f"the change {change}", name=name,
                                                                extra_import="", extra=""))


def write_specs() -> None:
    def example(m):
        name, doc_name, fmt = m.group(1), m.group(2), m.group(3)
        case = next(c for c in json.loads((TASK / "tests" / f"{name}.json").read_text())
                    if c["id"] == f"{fmt}-{doc_name}")
        return (f"For example, this document:\n\n```json\n{json.dumps(case['document'], ensure_ascii=False)}\n```\n\n"
                f"renders with `--to {fmt}` as:\n\n````\n{case['expected']}````")
    (TASK / "specs").mkdir(exist_ok=True)
    for f in sorted((HERE / "specs").glob("*.md")):
        text = re.sub(r"\{\{EXAMPLE:(\w+):(\w+):(\w+)\}\}", example, f.read_text())
        (TASK / "specs" / f.name).write_text(text)
    (TASK / "specs" / "base.md").write_text(README_TEXT)


if __name__ == "__main__":
    main()
