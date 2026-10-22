"""Hidden tests for the probe change missing_as_null: golden cases in big_missing_as_null.json (see make_big_tests.py)."""

import pytest

from chain_golden import cases, check


@pytest.mark.parametrize("case", cases("big_missing_as_null"), ids=lambda c: c["id"])
def test_golden(entrypoint_argv, case):
    check(entrypoint_argv, case)
