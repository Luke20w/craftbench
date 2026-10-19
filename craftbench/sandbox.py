"""Where agents work. Anything with `create(dest, source)` returning a workspace path can replace
LocalSandbox (e.g. a container per workspace for untrusted policies)."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

IGNORE = {"__pycache__", ".git", ".pytest_cache", ".claude", ".venv", "node_modules"}


class LocalSandbox:
    def create(self, dest: Path, source: Path | None = None) -> Path:
        """A fresh workspace at `dest`: empty, or a copy of `source`, with its own git repo so any
        git commands an agent runs stay inside it."""
        if dest.exists():
            shutil.rmtree(dest)
        if source:
            shutil.copytree(source, dest, ignore=lambda d, names: [n for n in names if n in IGNORE])
        else:
            dest.mkdir(parents=True)
        subprocess.run("git init -q && git add -A && git -c user.name=env -c user.email=env@local "
                       "commit -q --allow-empty -m base", shell=True, cwd=dest, check=True)
        return dest
