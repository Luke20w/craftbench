"""Hidden tests for milestone 5_text: golden cases in m5_text.json."""

import pytest

from golden import cases, check


@pytest.mark.parametrize("case", cases("m5_text"), ids=lambda c: c["id"])
def test_golden(entrypoint_argv, case):
    check(entrypoint_argv, case)
