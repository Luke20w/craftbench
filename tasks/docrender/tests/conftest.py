import shlex

import pytest


def pytest_addoption(parser):
    parser.addoption("--entrypoint", action="store", required=True, help="Full command to run the submission")


@pytest.fixture(scope="session")
def entrypoint_argv(request):
    return shlex.split(request.config.getoption("--entrypoint"))
