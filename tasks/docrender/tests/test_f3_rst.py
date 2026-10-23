"""Hidden tests for the change f3_rst: golden cases in rst.json (see gen/make.py)."""

import pytest

from golden import cases, check


@pytest.mark.parametrize("case", cases("rst"), ids=lambda c: c["id"])
def test_golden(entrypoint_argv, case):
    check(entrypoint_argv, case)
