"""Hidden tests for the change f2_textile: golden cases in textile.json (see gen/make.py)."""

import pytest

from golden import cases, check


@pytest.mark.parametrize("case", cases("textile"), ids=lambda c: c["id"])
def test_golden(entrypoint_argv, case):
    check(entrypoint_argv, case)
