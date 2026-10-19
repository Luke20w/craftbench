"""python -m extenders check | plan [--group G] | selftest [EXP7_DIR]"""

from __future__ import annotations

import argparse
import shlex
from pathlib import Path

from . import config
from .harnesses import REGISTRY
from .panel import selected


def check(panel: config.Panel) -> None:
    print(f"{'extender':24}{'harness':13}{'enabled':9}{'installed/auth':40}{'parser':10}")
    for e in panel.extenders:
        h = REGISTRY[e.harness]
        ok, why = h.available()
        try:
            h.validate(e)
            valid = ""
        except ValueError as err:
            valid = f"  INVALID: {err}"
        print(f"{e.id:24}{e.harness:13}{'yes' if e.enabled else 'no':9}{('ok' if ok else 'MISSING') + ' ' + why[:32]:40}"
              f"{'verified' if h.verified else 'unverified':10}{valid}")


def plan(panel: config.Panel, group: str) -> None:
    chosen = selected(panel, group)
    print(f"group {group!r}: {len(chosen)} of {len(panel.active)} active extenders selected")
    for e in chosen:
        argv, env, via_stdin = REGISTRY[e.harness].command(e, Path("<workdir>"), Path("/tmp/extenders-plan") / e.id)
        print(f"\n[{e.id}] seeds={e.seeds} budget=${e.budget_usd} env={sorted(env)} prompt via {'stdin' if via_stdin else 'argv'}")
        print("  " + shlex.join(argv))


def main() -> None:
    ap = argparse.ArgumentParser(prog="python -m extenders")
    ap.add_argument("cmd", choices=["check", "plan", "selftest"])
    ap.add_argument("arg", nargs="?")
    ap.add_argument("--panel", default=str(config.DEFAULT_PANEL))
    ap.add_argument("--group", default="example-group")
    a = ap.parse_args()
    panel = config.load(a.panel)
    if a.cmd == "check":
        check(panel)
    elif a.cmd == "plan":
        plan(panel, a.group)
    else:
        from .selftest import main as selftest
        selftest(Path(a.arg) if a.arg else None)


if __name__ == "__main__":
    main()
