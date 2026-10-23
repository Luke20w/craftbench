"""Hidden tests for the change k3_definition_list: golden cases in definition_list.json (see gen/make.py)."""

import pytest

from golden import cases, check


@pytest.mark.parametrize("case", cases("definition_list"), ids=lambda c: c["id"])
def test_golden(entrypoint_argv, case):
    check(entrypoint_argv, case)
