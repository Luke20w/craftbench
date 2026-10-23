"""Hidden tests for the change s2_quote_cite: golden cases in quote_cite.json (see gen/make.py)."""

import pytest

from golden import cases, check


@pytest.mark.parametrize("case", cases("quote_cite"), ids=lambda c: c["id"])
def test_golden(entrypoint_argv, case):
    check(entrypoint_argv, case)
