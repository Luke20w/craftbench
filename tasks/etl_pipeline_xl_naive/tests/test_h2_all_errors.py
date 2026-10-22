"""Hidden tests for the held-out change h2_all_errors: golden cases in h2_all_errors.json (see make_chain_tests.py)."""

import pytest

from chain_golden import cases, check


@pytest.mark.parametrize("case", cases("h2_all_errors"), ids=lambda c: c["id"])
def test_golden(entrypoint_argv, case):
    check(entrypoint_argv, case)
