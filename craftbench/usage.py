"""Usage: what agent runs cost, and a guard for subscription limits.

Every agent run leaves a run.json next to its logs (cost, tokens, and the subscription limits the CLI
reported). `summary` adds them up. Claude Code reports a Claude subscription's 5-hour and weekly usage
at the start of each run; `QUOTA` checks the latest report before every run starts: it pauses until the
5-hour window resets when that window is too full, and stops when the weekly window is too full or
extra usage (billed beyond the subscription) is being used.
"""

from __future__ import annotations

import json
import sys
import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path


class QuotaExceeded(RuntimeError):
    pass


@dataclass
class Quota:
    max_five_hour: float = 0.8    # pause when the 5-hour window is this full
    max_seven_day: float = 0.5    # stop when the weekly window is this full
    latest: dict = field(default_factory=dict)  # the last rate-limit report seen
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def update(self, info: dict) -> None:
        if info:
            with self._lock:
                self.latest = info

    def check(self) -> None:
        """Call before starting a run."""
        info = self.latest
        if not info:
            return
        if info.get("isUsingOverage"):
            raise QuotaExceeded("the subscription is past its limit and billing extra usage")
        windows = info.get("unifiedWindows", {})
        week, five = windows.get("seven_day", {}), windows.get("five_hour", {})
        if week.get("utilization", 0) >= self.max_seven_day:
            raise QuotaExceeded(f"weekly usage is at {week['utilization']:.0%} (limit {self.max_seven_day:.0%})")
        if five.get("utilization", 0) >= self.max_five_hour:
            wait = max(0, five.get("resetsAt", 0) - time.time()) + 60
            print(f"5-hour usage is at {five['utilization']:.0%}: pausing {wait / 60:.0f} min until it resets",
                  file=sys.stderr)
            time.sleep(wait)
            with self._lock:
                self.latest = {}


QUOTA = Quota()


def summary(runs_dir: Path) -> str:
    """Runs, cost and tokens per agent and role, and the latest subscription usage seen."""
    rows, latest = defaultdict(lambda: defaultdict(float)), None
    for f in sorted(runs_dir.rglob("run.json")):
        r = json.loads(f.read_text())
        parts = f.relative_to(runs_dir).parts
        role = "smoke" if "smoke" in parts else "build" if "build" in parts else "extend"
        row = rows[(r["agent"], role)]
        row["runs"] += 1
        row["cost_usd"] += r["cost_usd"]
        for k in ("input_tokens", "output_tokens", "cache_read_input_tokens", "cache_creation_input_tokens"):
            row[k] += r["usage"].get(k, 0)
        if r.get("quota") and (latest is None or r["finished"] > latest["finished"]):
            latest = r
    if not rows:
        return "no runs yet"
    out = ["| agent | role | runs | cost $ (API-equivalent) | input | output | cache read | cache write |",
           "|---|---|---|---|---|---|---|---|"]
    for (agent, role), r in sorted(rows.items()):
        out.append(f"| {agent} | {role} | {r['runs']:.0f} | {r['cost_usd']:.2f} | {r['input_tokens']:,.0f} | "
                   f"{r['output_tokens']:,.0f} | {r['cache_read_input_tokens']:,.0f} | "
                   f"{r['cache_creation_input_tokens']:,.0f} |")
    out.append(f"\nTotal: ${sum(r['cost_usd'] for r in rows.values()):.2f} at API prices")
    if latest:
        w = latest["quota"].get("unifiedWindows", {})
        out.append(f"Subscription at {time.strftime('%Y-%m-%d %H:%M', time.localtime(latest['finished']))}: "
                   f"5-hour {w.get('five_hour', {}).get('utilization', 0):.0%}, "
                   f"weekly {w.get('seven_day', {}).get('utilization', 0):.0%}, "
                   f"extra usage {'IN USE' if latest['quota'].get('isUsingOverage') else 'not used'}")
    return "\n".join(out)
