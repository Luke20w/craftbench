"""Hidden tests for milestone 6_numbers: golden cases in m6_numbers.json."""

import pytest

from golden import cases, check


@pytest.mark.parametrize("case", cases("m6_numbers"), ids=lambda c: c["id"])
def test_golden(entrypoint_argv, case):
    check(entrypoint_argv, case)
