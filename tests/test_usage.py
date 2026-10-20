"""Subscription guard and usage summary, without model calls."""

import json
import time

import pytest

from craftbench.agents import ClaudeCodeAgent
from craftbench.usage import Quota, QuotaExceeded, summary


def report(five, week, overage=False):
    return {"isUsingOverage": overage, "unifiedWindows": {"five_hour": {"utilization": five, "resetsAt": time.time()},
                                                          "seven_day": {"utilization": week}}}


def test_quota_stops_before_extra_usage_or_a_full_week(monkeypatch):
    q = Quota(max_five_hour=0.8, max_seven_day=0.5)
    q.check()  # nothing reported yet
    q.update(report(0.2, 0.1))
    q.check()
    q.update(report(0.2, 0.6))
    with pytest.raises(QuotaExceeded):
        q.check()
    q.update(report(0.2, 0.1, overage=True))
    with pytest.raises(QuotaExceeded):
        q.check()
    slept = []
    monkeypatch.setattr(time, "sleep", slept.append)
    q.update(report(0.9, 0.1))
    q.check()  # 5-hour window full: wait for it to reset, then carry on
    assert slept and q.latest == {}


def test_claude_runs_report_subscription_usage():
    lines = [json.dumps({"type": "rate_limit_event", "rate_limit_info": report(0.14, 0.01)}),
             json.dumps({"type": "result", "subtype": "success", "total_cost_usd": 0.03, "usage": {"output_tokens": 5}})]
    run, _ = ClaudeCodeAgent().parse(lines, [], None)
    assert run.quota["unifiedWindows"]["five_hour"]["utilization"] == 0.14 and run.cost_usd == 0.03


def test_summary_adds_up_runs_by_agent_and_role(tmp_path):
    for path, cost in [("bench/opus/s0/build/milestone_1", 1.0), ("bench/opus/s0/build/milestone_2", 2.0),
                       ("bench/opus/s0/maintain/limits/haiku/run_0", 0.5)]:
        (tmp_path / path).mkdir(parents=True)
        (tmp_path / path / "run.json").write_text(json.dumps({
            "agent": "haiku" if "maintain" in path else "opus", "cost_usd": cost, "usage": {"output_tokens": 10},
            "quota": report(0.3, 0.05), "finished": time.time()}))
    out = summary(tmp_path)
    assert "| opus | build | 2 | 3.00 |" in out and "| haiku | extend | 1 | 0.50 |" in out
    assert "Total: $3.50" in out and "5-hour 30%, weekly 5%" in out
