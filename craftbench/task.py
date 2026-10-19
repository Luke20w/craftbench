"""Tasks are data: a folder with task.toml, specs and hidden tests. Nothing here is domain specific."""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass
from pathlib import Path

TASKS_DIR = Path(__file__).resolve().parent.parent / "tasks"


@dataclass(frozen=True)
class Suite:
    """One unit of work: a milestone the policy builds, or a change the extender makes."""

    id: str
    spec_path: Path
    tests: tuple[str, ...]      # test files in the task's tests/ folder
    requires: tuple[str, ...] = ()

    @property
    def spec(self) -> str:
        # Drop HTML comments (benchmark canary headers) so agents only see the requirement.
        return re.sub(r"<!--.*?-->", "", self.spec_path.read_text(), flags=re.S).strip()


@dataclass(frozen=True)
class Task:
    id: str
    root: Path
    program: str                 # one-line description used in prompts
    language: str
    entrypoint: str              # command the hidden tests run: {python} and {workspace} are filled in
    milestones: tuple[Suite, ...]
    changes: tuple[Suite, ...]
    reference: Path | None       # optional known-good solution
    mutants: Path | None         # optional known-worse copies of the reference

    @property
    def tests_dir(self) -> Path:
        return self.root / "tests"

    @property
    def run_hint(self) -> str:
        """How agents are told to run the program: the entrypoint, from inside the workspace."""
        return self.entrypoint.replace("{workspace}/", "")

    def change(self, change_id: str) -> Suite:
        return next(c for c in self.changes if c.id == change_id)

    def episode_changes(self) -> list[Suite]:
        """The changes graded in every episode: all independent ones, so every rollout in a training
        group is compared on the same changes. Chained changes (with `requires`) are not used yet."""
        return [c for c in self.changes if not c.requires]

    def mutant_dirs(self) -> dict[str, Path]:
        return {p.name: p for p in sorted(self.mutants.iterdir()) if p.is_dir()} if self.mutants else {}


def load_task(task: str | Path) -> Task:
    """Load a task by id (from ./tasks) or by path to its folder."""
    root = Path(task) if (Path(task) / "task.toml").exists() else TASKS_DIR / str(task)
    raw = tomllib.loads((root / "task.toml").read_text())
    suite = lambda s: Suite(s["id"], root / s["spec"], tuple(s["tests"]), tuple(s.get("requires", ())))  # noqa: E731
    return Task(
        id=raw["id"], root=root, program=raw["program"], language=raw.get("language", "python"),
        entrypoint=raw["entrypoint"],
        milestones=tuple(suite(m) for m in raw["milestones"]),
        changes=tuple(suite(c) for c in raw.get("changes", [])),
        reference=root / raw["reference"] if "reference" in raw else None,
        mutants=root / raw["mutants"] if "mutants" in raw else None,
    )


def list_tasks() -> list[str]:
    return sorted(p.parent.name for p in TASKS_DIR.glob("*/task.toml"))
