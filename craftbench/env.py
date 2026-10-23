"""The environment: build (policy) → maintain (frozen extender on hidden changes) → reward.

    env = Environment(load_task("etl_pipeline"))
    ep = env.reset()
    for i, prompt in enumerate(ep.prompts, 1):
        policy.run(ep.workspace, prompt, ep.dir / "build" / f"milestone_{i}")  # edits files in ep.workspace
    grade = env.grade(ep.workspace, ep.dir)  # grade.reward is the per-rollout reward
"""

from __future__ import annotations

import hashlib
import json
import shutil
import statistics as st
import sys
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .agents import Agent, AgentRun, ClaudeCodeAgent, load_calls, save_calls
from .analysis import ANALYZERS, code_metrics
from .effort import change_effort
from .grading import grade_snapshots, run_suite, run_suites
from .reward import geomean, reward
from .sandbox import LocalSandbox, copy_code, tree_digest
from .task import Suite, Task

POLICY_PROMPT = """You are building {program} in the current directory. It is run as `{run}`.

This is milestone {i} of {n}. Implement the specification below. Behaviour from earlier milestones \
must keep working. Hidden tests will check the program's behaviour through its command-line \
interface. After you finish, another engineer will maintain this code and will receive new \
requirements that you cannot see.

{spec}
"""

EXTENDER_PROMPT = """You are maintaining the existing codebase in the current directory: {program}. \
It is run as `{run}`.

A new requirement has arrived. Implement it in this codebase. Everything that already works must \
keep working exactly as before. When the requirement is fully implemented, stop.

{spec}
"""


def run_key(code: Path, extender: str, change: Suite) -> str:
    """Identifies an extender run by everything that decides its outcome, minus machine-specific
    details (the prompt's interpreter path), so results carry over to other checkouts."""
    return hashlib.md5(f"{tree_digest(code)}|{extender}|{change.spec}|{EXTENDER_PROMPT}".encode()).hexdigest()


@dataclass
class Episode:
    dir: Path              # where this episode's logs and grade go
    workspace: Path        # where the policy builds the code
    prompts: list[str]     # one per milestone, in order


@dataclass
class Grade:
    reward: float
    milestone_pass_fraction: float           # F
    milestones: dict[str, list[int]]         # milestone id -> [passed, total]
    efforts: dict[str, float]                # change id -> effort (tokens read), across the panel
    efforts_by_extender: dict[str, dict[str, float]]  # change id -> extender -> its mean effort
    extender_runs: dict[str, list[dict]]     # change id -> per-run details
    metrics: dict                            # logged only, never rewarded


@dataclass
class Environment:
    task: Task
    # The panel. Readers disagree about which code is easy to change (docs/experiments/v_measures.md), so
    # use several, ideally from different model families.
    extenders: list[Agent] = field(default_factory=lambda: [ClaudeCodeAgent("claude-sonnet-5-5"),
                                                            ClaudeCodeAgent("claude-opus-5-5")])
    # Per change; the runs' efforts are averaged. A second run is worth ~+0.1 correlation with what code really costs
    # to own (docs/experiments/v_measures.md).
    runs_per_extender: int = 2
    max_parallel: int = 4           # extender runs at once
    lam: float = 0.5
    runs_dir: Path = Path("runs")
    sandbox: LocalSandbox = field(default_factory=LocalSandbox)

    @property
    def run_hint(self) -> str:
        return self.task.run_hint.format(python=sys.executable)

    def reset(self, name: str | None = None) -> Episode:
        """A new episode: an empty workspace and the milestone prompts, in order."""
        d = self.runs_dir / self.task.id / (name or uuid.uuid4().hex[:8])
        shutil.rmtree(d, ignore_errors=True)  # a rerun starts clean
        n = len(self.task.milestones)
        prompts = [POLICY_PROMPT.format(program=self.task.program, run=self.run_hint, i=i, n=n, spec=m.spec)
                   for i, m in enumerate(self.task.milestones, 1)]
        return Episode(d, self.sandbox.create(d / "build" / "code"), prompts)

    def run_episode(self, policy: Agent, name: str | None = None) -> Grade:
        """Let an Agent do the build phase, then grade."""
        ep = self.reset(name)
        for i, prompt in enumerate(ep.prompts, 1):
            policy.run(ep.workspace, prompt, ep.dir / "build" / f"milestone_{i}")
        (ep.dir / "build" / "done").touch()  # the build is final; grading it again reuses finished work
        return self.grade(ep.workspace, ep.dir)

    def grade(self, code: Path, out: Path) -> Grade:
        """Milestone tests → F; each extender makes each hidden change → efforts; then the reward.

        A change's effort is each extender's mean over its runs, then the geometric mean across the
        panel, so an extender that reads less across the board (a stronger model) scales every
        rollout's reward equally instead of outweighing the others."""
        milestones = run_suites(self.task, code, list(self.task.milestones))
        passed = sum(len(r.passed) for r in milestones.values())
        F = passed / sum(len(r.tests) for r in milestones.values())

        changes = self.task.episode_changes()
        jobs = [(c, e, k) for c in changes for e in self.extenders for k in range(self.runs_per_extender)]

        def one_run(job):
            change, extender, k = job
            d = out / "maintain" / change.id / extender.name / f"run_{k}"
            return self.maintain(extender, code, change, d, passed)

        with ThreadPoolExecutor(max(1, min(self.max_parallel, len(jobs)))) as ex:
            runs = list(ex.map(one_run, jobs))
        by_change = {c.id: [r for (cc, _, _), r in zip(jobs, runs) if cc.id == c.id] for c in changes}
        by_extender = {c: {e.name: st.mean(r["effort"] for r in rs if r["extender"] == e.name) for e in self.extenders}
                       for c, rs in by_change.items()}
        efforts = {c: geomean(by_ext.values()) for c, by_ext in by_extender.items()}

        grade = Grade(reward(F, list(efforts.values()), self.lam), F,
                      {k: [len(r.passed), len(r.tests)] for k, r in milestones.items()},
                      efforts, by_extender, by_change, code_metrics(code, ANALYZERS[self.task.language]))
        out.mkdir(parents=True, exist_ok=True)
        (out / "grade.json").write_text(json.dumps(asdict(grade), indent=2))
        return grade

    def maintain(self, extender: Agent, code: Path, change: Suite, d: Path, regression_base: int) -> dict:
        """One extender run on a private copy of the code, then its effort. A finished run of the same
        extender on the same code and change is reused (its tool calls and graded snapshots are kept), so
        grading again only does new work, and its effort is recomputed with the current rules."""
        prompt = EXTENDER_PROMPT.format(program=self.task.program, run=self.run_hint, spec=change.spec)
        key = run_key(code, extender.name, change)
        done = d / "result.json"
        if (done.exists() and json.loads(done.read_text()).get("key") == key
                and (d / "calls.json").exists() and (d / f"curve_{change.id}.json").exists()):
            meta = json.loads((d / "run.json").read_text()) if (d / "run.json").exists() else {}
            run = AgentRun(load_calls(d / "calls.json"), meta.get("cost_usd", 0.0), meta.get("stop", ""),
                           meta.get("usage", {}))
            return {"extender": extender.name, "key": key, **self.score(run, d, code, change, regression_base)}
        shutil.rmtree(d, ignore_errors=True)  # a partial or outdated run: start clean
        workspace = self.sandbox.create(d / "code", code)
        run = extender.run(workspace, prompt, d, snapshot_dir=d / "snaps")
        save_calls(run.calls, d / "calls.json")  # what scoring (and later re-scoring) needs
        # Hooks don't fire for failed tool calls, so always snapshot the final state too.
        final = sum(not c.is_error for c in run.calls) + 1
        copy_code(workspace, d / "snaps" / f"{final:04d}")
        result = {"extender": extender.name, "key": key, **self.score(run, d, code, change, regression_base)}
        done.write_text(json.dumps(result))
        return result

    def score(self, run: AgentRun, d: Path, base: Path, change: Suite, regression_base: int) -> dict:
        """Effort for a finished extender run whose snapshots are in d/snaps (also used to re-grade)."""
        curve = grade_snapshots(self.task, change, d / "snaps")
        already = run_suite(self.task, base, change).passed  # passing before the extender did anything
        effort = change_effort(run.calls, curve, base, ANALYZERS[self.task.language], regression_base, already)
        return {"effort": effort, "already_passing": len(already), "cost_usd": run.cost_usd, "usage": run.usage,
                "stop": run.stop, "tool_calls": len(run.calls),
                "new_tests_passed": len(curve.points[-1].new_passed) if curve.points else 0,
                "new_tests_total": len(curve.tests)}
