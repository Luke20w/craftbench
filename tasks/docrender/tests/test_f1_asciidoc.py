"""Hidden tests for the change f1_asciidoc: golden cases in asciidoc.json (see gen/make.py)."""

import pytest

from golden import cases, check


@pytest.mark.parametrize("case", cases("asciidoc"), ids=lambda c: c["id"])
def test_golden(entrypoint_argv, case):
    check(entrypoint_argv, case)
