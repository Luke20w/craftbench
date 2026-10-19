"""The environment: build (policy) → maintain (frozen extender on hidden changes) → reward.

    env = Environment(load_task("etl_pipeline"))
    ep = env.reset()
    for prompt in ep.prompts:
        policy.act(ep.workspace, prompt)       # the policy edits files in ep.workspace
    grade = env.grade(ep.workspace, ep.dir)    # grade.reward is the per-rollout reward
"""

from __future__ import annotations

import json
import shutil
import statistics as st
import sys
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .agents import Agent, AgentRun, ClaudeCodeAgent
from .analysis import ANALYZERS, code_metrics
from .effort import change_effort
from .grading import grade_snapshots, run_suites
from .reward import reward
from .sandbox import LocalSandbox
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
    efforts: dict[str, float]                # change id -> effort (tokens read)
    extender_runs: dict[str, list[dict]]     # change id -> per-run details
    metrics: dict                            # logged only, never rewarded


@dataclass
class Environment:
    task: Task
    extender: Agent = field(default_factory=ClaudeCodeAgent)
    extender_runs: int = 1          # runs per change; their efforts are averaged
    lam: float = 0.5
    runs_dir: Path = Path("runs")
    sandbox: LocalSandbox = field(default_factory=LocalSandbox)

    @property
    def run_hint(self) -> str:
        return self.task.run_hint.format(python=sys.executable)

    def reset(self) -> Episode:
        """A new episode: an empty workspace and the milestone prompts, in order."""
        d = self.runs_dir / self.task.id / uuid.uuid4().hex[:8]
        n = len(self.task.milestones)
        prompts = [POLICY_PROMPT.format(program=self.task.program, run=self.run_hint, i=i, n=n, spec=m.spec)
                   for i, m in enumerate(self.task.milestones, 1)]
        return Episode(d, self.sandbox.create(d / "build" / "code"), prompts)

    def run_episode(self, policy: Agent) -> Grade:
        """Let an Agent do the build phase, then grade."""
        ep = self.reset()
        for i, prompt in enumerate(ep.prompts, 1):
            policy.run(ep.workspace, prompt, ep.dir / "build" / f"milestone_{i}")
        return self.grade(ep.workspace, ep.dir)

    def grade(self, code: Path, out: Path) -> Grade:
        """Milestone tests → F; the extender makes each hidden change → efforts; then the reward."""
        milestones = run_suites(self.task, code, list(self.task.milestones))
        passed = sum(len(r.passed) for r in milestones.values())
        F = passed / sum(len(r.tests) for r in milestones.values())

        jobs = [(c, k) for c in self.task.episode_changes() for k in range(self.extender_runs)]
        with ThreadPoolExecutor(max(1, len(jobs))) as ex:
            runs = list(ex.map(lambda j: self.maintain(code, j[0], out / "maintain" / j[0].id / f"run_{j[1]}", passed), jobs))
        by_change = {c.id: [r for (cc, _), r in zip(jobs, runs) if cc.id == c.id] for c in self.task.episode_changes()}
        efforts = {c: st.mean(r["effort"] for r in rs) for c, rs in by_change.items()}

        grade = Grade(reward(F, list(efforts.values()), self.lam), F,
                      {k: [len(r.passed), len(r.tests)] for k, r in milestones.items()},
                      efforts, by_change, code_metrics(code, ANALYZERS[self.task.language]))
        out.mkdir(parents=True, exist_ok=True)
        (out / "grade.json").write_text(json.dumps(asdict(grade), indent=2))
        return grade

    def maintain(self, code: Path, change: Suite, d: Path, regression_base: int) -> dict:
        """One extender run on a private copy of the code, then its effort."""
        workspace = self.sandbox.create(d / "code", code)
        prompt = EXTENDER_PROMPT.format(program=self.task.program, run=self.run_hint, spec=change.spec)
        run = self.extender.run(workspace, prompt, d, snapshot_dir=d / "snaps")
        # Hooks don't fire for failed tool calls, so always snapshot the final state too.
        final = sum(not c.is_error for c in run.calls) + 1
        shutil.copytree(workspace, d / "snaps" / f"{final:04d}", ignore=shutil.ignore_patterns(".git", "__pycache__"))
        return self.score(run, d, code, change, regression_base)

    def score(self, run: AgentRun, d: Path, base: Path, change: Suite, regression_base: int) -> dict:
        """Effort for a finished extender run whose snapshots are in d/snaps (also used to re-grade)."""
        curve = grade_snapshots(self.task, change, d / "snaps")
        effort = change_effort(run.calls, curve, base, ANALYZERS[self.task.language], regression_base)
        return {"effort": effort, "cost_usd": run.cost_usd, "stop": run.stop, "tool_calls": len(run.calls),
                "new_tests_passed": len(curve.points[-1].new_passed) if curve.points else 0,
                "new_tests_total": len(curve.tests)}
