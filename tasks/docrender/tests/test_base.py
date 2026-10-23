"""Hidden tests for the existing behaviour: golden cases in base.json (see gen/make.py)."""

import pytest

from golden import cases, check, check_error


@pytest.mark.parametrize("case", cases("base"), ids=lambda c: c["id"])
def test_golden(entrypoint_argv, case):
    check(entrypoint_argv, case)


def test_unknown_format(entrypoint_argv):
    check_error(entrypoint_argv, "docx", {"type": "document", "children": []})


def test_unknown_node_type(entrypoint_argv):
    check_error(entrypoint_argv, "html", {"type": "document", "children": [{"type": "video", "src": "a.mp4"}]})
