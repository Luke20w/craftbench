"""Hidden tests for the held-out change h3_strict: golden cases in h3_strict.json (see make_chain_tests.py)."""

import pytest

from chain_golden import cases, check


@pytest.mark.parametrize("case", cases("h3_strict"), ids=lambda c: c["id"])
def test_golden(entrypoint_argv, case):
    check(entrypoint_argv, case)
