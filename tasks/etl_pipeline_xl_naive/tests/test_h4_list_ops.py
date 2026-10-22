"""Hidden tests for the held-out change h4_list_ops: golden cases in h4_list_ops.json (see make_chain_tests.py)."""

import pytest

from chain_golden import cases, check


@pytest.mark.parametrize("case", cases("h4_list_ops"), ids=lambda c: c["id"])
def test_golden(entrypoint_argv, case):
    check(entrypoint_argv, case)
