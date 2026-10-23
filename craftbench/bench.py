"""Benchmark models as builders (the policy, in env.py's terms): each builds the task `runs` times, the
environment's extender panel grades every build, and the report compares builders.

Builds live at <runs dir>/<task>/bench/<builder>/s<k>. A finished build is never rebuilt, and grading
reuses finished extender runs, so rerunning resumes an interrupted benchmark, and adding extenders or
builds later only runs what's new.
"""

from __future__ import annotations

import json
import shutil
import statistics as st
import sys
import traceback
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict

from .agents import Agent
from .analysis import ANALYZERS, source_files
from .env import Environment
from .reward import geomean
from .usage import QuotaExceeded


def run(env: Environment, builders: list[Agent], runs: int, parallel: int = 1) -> dict[str, list[dict]]:
    """builder -> the grade of each of its builds (failed builds are reported and left out)."""
    def build(job):
        b, k = job
        name = f"bench/{b.name}/s{k}"
        d = env.runs_dir / env.task.id / name
        try:
            if (d / "build" / "done").exists():
                return asdict(env.grade(d / "build" / "code", d))
            return asdict(env.run_episode(b, name))
        except QuotaExceeded as e:
            print(f"{name} stopped: {e}", file=sys.stderr)
        except Exception:
            print(f"{name} failed:\n{traceback.format_exc()}", file=sys.stderr)

    jobs = [(b, k) for b in builders for k in range(runs)]
    with ThreadPoolExecutor(parallel) as ex:
        grades = list(ex.map(build, jobs))
    return {b.name: [g for (bb, _), g in zip(jobs, grades) if bb is b and g] for b in builders}


def _spread(values: list[float], fmt: str) -> str:
    if len(values) == 1:
        return format(values[0], fmt)
    return f"{format(st.median(values), fmt)} ({format(min(values), fmt)}–{format(max(values), fmt)})"


def report(results: dict[str, list[dict]]) -> str:
    """Builders (medians over builds, range in brackets), then how each extender rated them."""
    graded = {b: gs for b, gs in results.items() if gs}
    if not graded:
        return "no finished builds"
    changes = sorted(next(iter(graded.values()))[0]["efforts"])
    efforts = " | ".join(f"effort: {c}" for c in changes)
    rows = [f"| builder | builds | F | reward ×100 | {efforts} | code nodes |",
            "|---|---|---|---|" + "---|" * len(changes) + "---|"]
    for b, gs in graded.items():
        cells = " | ".join(f"{st.median(g['efforts'][c] for g in gs):,.0f}" for c in changes)
        rows.append(f"| {b} | {len(gs)} | {_spread([g['milestone_pass_fraction'] for g in gs], '.2f')} | "
                    f"{_spread([g['reward'] * 100 for g in gs], '.3f')} | {cells} | "
                    f"{st.median(g['metrics']['nodes'] for g in gs):,.0f} |")

    # Each extender's effort for each builder (geometric mean over changes, median over builds),
    # relative to that extender's median across builders: 1.00 = typical, lower = easier to change.
    # Rows that disagree across columns show where one reader's habits decide the ranking.
    extenders = sorted(next(iter(graded.values()))[0]["efforts_by_extender"][changes[0]])
    raw = {b: {e: st.median(geomean(g["efforts_by_extender"][c][e] for c in changes) for g in gs) for e in extenders}
           for b, gs in graded.items()}
    typical = {e: st.median(raw[b][e] for b in raw) for e in extenders}
    rows += ["", "Effort by extender, relative to its typical builder (lower = easier to change):", "",
             "| builder | " + " | ".join(extenders) + " |", "|---|" + "---|" * len(extenders)]
    rows += [f"| {b} | " + " | ".join(f"{raw[b][e] / typical[e]:.2f}" for e in extenders) + " |" for b in raw]
    # How much the readers agree on which builds are easy to change. Low agreement means the ranking is
    # partly about who reads, so trust the panel average, not any one column.
    builds = [(g["efforts_by_extender"], b) for b, gs in graded.items() for g in gs]
    if len(extenders) > 1 and len(builds) > 2:
        rows += ["", "Extender agreement across builds (Spearman):", ""]
        for i, e1 in enumerate(extenders):
            for e2 in extenders[i + 1:]:
                x = [geomean(ebe[c][e1] for c in changes) for ebe, _ in builds]
                y = [geomean(ebe[c][e2] for c in changes) for ebe, _ in builds]
                rows.append(f"- {e1} vs {e2}: {_spearman(x, y):+.2f}")
    return "\n".join(rows)


def _spearman(x: list[float], y: list[float]) -> float:
    def rank(v):  # ties share the mean of their ranks
        return [sorted(v).index(a) + (v.count(a) - 1) / 2 for a in v]

    rx, ry = rank(x), rank(y)
    mx, my = sum(rx) / len(rx), sum(ry) / len(ry)
    sx = sum((a - mx) ** 2 for a in rx) ** 0.5
    sy = sum((b - my) ** 2 for b in ry) ** 0.5
    return sum((a - mx) * (b - my) for a, b in zip(rx, ry)) / (sx * sy) if sx and sy else float("nan")


SMOKE_PROMPT = "Read {file}, then add the comment `# smoke test` as its first line. Then stop."


def smoke(env: Environment, agent: Agent) -> str:
    """One tiny extender job on the task's reference (costs cents): checks that the agent's CLI runs,
    its tool calls parse with real result sizes, and snapshots are taken."""
    d = env.runs_dir / "smoke" / agent.name
    shutil.rmtree(d, ignore_errors=True)
    workspace = env.sandbox.create(d / "code", env.task.reference)
    file = source_files(workspace, ANALYZERS[env.task.language])[0].relative_to(workspace)
    run = agent.run(workspace, SMOKE_PROMPT.format(file=file), d, snapshot_dir=d / "snaps")
    snaps = sorted(p.name for p in (d / "snaps").glob("[0-9]*"))
    problems = [msg for ok, msg in [
        (any(c.result_chars > 1000 for c in run.calls), "no tool call returned the file's contents"),
        (snaps, "no snapshot was taken"),
        ((workspace / file).read_text().startswith("# smoke test"), "the edit wasn't made")] if not ok]
    lines = [f"{agent.name}: {'OK' if not problems else 'PROBLEMS: ' + '; '.join(problems)}",
             f"  stop={run.stop} cost_usd={run.cost_usd:.3f} snapshots={snaps}",
             f"  usage={ {k: v for k, v in run.usage.items() if isinstance(v, int)} }"]
    lines += [f"  {c.name:6} {c.result_chars:>7,} chars {'(error) ' if c.is_error else ''}{json.dumps(c.input)[:80]}"
              for c in run.calls]
    return "\n".join(lines)
