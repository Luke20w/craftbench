"""Hidden tests for milestone 7_rows: golden cases in m7_rows.json."""

import pytest

from golden import cases, check


@pytest.mark.parametrize("case", cases("m7_rows"), ids=lambda c: c["id"])
def test_golden(entrypoint_argv, case):
    check(entrypoint_argv, case)
