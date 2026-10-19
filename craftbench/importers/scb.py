"""Turn a SlopCodeBench problem into a craftbench task folder.

SlopCodeBench problems are a sequence of checkpoints, each a spec plus hidden tests that drive the
program through its CLI. The first `milestones` checkpoints become milestones; the remaining ones
become change requests, chained (each requires the previous), because SlopCodeBench checkpoints
build on each other.

Limits (why this is scaffolding):
  * only the first change after the milestones is independent, so episodes get one change; add
    hand-written independent changes (see docs/TASK_AUTHORING.md) to get a useful change pool;
  * CLI problems only; problems that start an HTTP server need a different entrypoint;
  * no reference solution is copied (SlopCodeBench ships per-checkpoint solutions under
    solutions/checkpoint_N if you want one).

    python -m craftbench.importers.scb <scb_problem_dir> tasks/<id> --milestones 3
"""

from __future__ import annotations

import argparse
import re
import shutil
from pathlib import Path


def import_problem(src: Path, dest: Path, milestones: int) -> Path:
    cfg = (src / "config.yaml").read_text()
    entry = re.search(r"^entry_file:\s*(\S+)", cfg, re.M)
    entry_file = (entry.group(1) if entry else src.name) + ".py"
    checkpoints = sorted((int(m.group(1)), p) for p in src.glob("checkpoint_*.md")
                         if (m := re.match(r"checkpoint_(\d+)\.md", p.name)))
    if len(checkpoints) <= milestones:
        raise ValueError(f"{src.name} has {len(checkpoints)} checkpoints; need more than {milestones}")

    dest.mkdir(parents=True, exist_ok=True)
    (dest / "specs").mkdir(exist_ok=True)
    shutil.copytree(src / "tests", dest / "tests", dirs_exist_ok=True)
    conftest = dest / "tests" / "conftest.py"  # the runner only passes --entrypoint
    conftest.write_text(re.sub(r'("--checkpoint",\s*action="store",\s*)required=True', r"\1required=False",
                               conftest.read_text()))
    for n, p in checkpoints:
        text = p.read_text().replace("%%%ENTRYPOINT:entry_file%%%", entry_file)
        (dest / "specs" / f"checkpoint_{n}.md").write_text(text)
    if (src.parent / "LICENSE").exists():
        shutil.copy(src.parent / "LICENSE", dest / "LICENSE-slopcodebench")

    def block(kind, n, requires=None):
        lines = [f"[[{kind}]]", f'id = "checkpoint_{n}"', f'spec = "specs/checkpoint_{n}.md"',
                 f'tests = ["test_checkpoint_{n}.py"]']
        if requires:
            lines.append(f'requires = ["{requires}"]')
        return "\n".join(lines)

    parts = [
        f'id = "{dest.name}"',
        f'program = "{src.name}, a command-line program"',
        'language = "python"',
        f'entrypoint = "{{python}} {{workspace}}/{entry_file}"', "",
    ]
    parts += [block("milestones", n) for n, _ in checkpoints[:milestones]]
    prev = None
    for n, _ in checkpoints[milestones:]:
        parts.append(block("changes", n, prev))
        prev = f"checkpoint_{n}"
    (dest / "task.toml").write_text("\n".join(parts) + "\n")
    return dest


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("src", type=Path)
    ap.add_argument("dest", type=Path)
    ap.add_argument("--milestones", type=int, default=3)
    a = ap.parse_args()
    print(import_problem(a.src, a.dest, a.milestones))
