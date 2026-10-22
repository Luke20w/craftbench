"""Hidden tests for the held-out change h1_dates: golden cases in h1_dates.json (see make_chain_tests.py)."""

import pytest

from chain_golden import cases, check


@pytest.mark.parametrize("case", cases("h1_dates"), ids=lambda c: c["id"])
def test_golden(entrypoint_argv, case):
    check(entrypoint_argv, case)
