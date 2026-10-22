"""Hidden tests for the probe change explain: golden cases in big_explain.json (see make_big_tests.py)."""

import pytest

from chain_golden import cases, check


@pytest.mark.parametrize("case", cases("big_explain"), ids=lambda c: c["id"])
def test_golden(entrypoint_argv, case):
    check(entrypoint_argv, case)
