"""Hidden tests for the probe change ignore_case_columns: golden cases in big_ignore_case_columns.json (see make_big_tests.py)."""

import pytest

from chain_golden import cases, check


@pytest.mark.parametrize("case", cases("big_ignore_case_columns"), ids=lambda c: c["id"])
def test_golden(entrypoint_argv, case):
    check(entrypoint_argv, case)
