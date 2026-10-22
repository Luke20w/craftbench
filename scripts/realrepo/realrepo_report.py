"""pytest plugin (loaded with `-p realrepo_report`): write each test's outcome to --realrepo-out as JSON.

A test passes when its setup and call both passed and it isn't an xfail/xpass."""

import json

_outcomes: dict[str, str] = {}


def pytest_addoption(parser):
    parser.addoption("--realrepo-out", default=None)


def pytest_runtest_logreport(report):
    nid = report.nodeid
    if report.when == "setup" and report.outcome != "passed":
        _outcomes[nid] = "skipped" if report.skipped else "error"
    elif report.when == "call":
        _outcomes[nid] = "xfail" if hasattr(report, "wasxfail") else report.outcome
    elif report.when == "teardown" and report.outcome == "failed" and _outcomes.get(nid) == "passed":
        _outcomes[nid] = "error"


def pytest_sessionfinish(session):
    out = session.config.getoption("--realrepo-out")
    if out:
        with open(out, "w") as f:
            json.dump(_outcomes, f)
