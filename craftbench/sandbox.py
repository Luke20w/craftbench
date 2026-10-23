"""Where agents work. Anything with `create(dest, source)` returning a workspace path can replace
LocalSandbox (e.g. a container per workspace for untrusted policies)."""

from __future__ import annotations

import hashlib
import shutil
import subprocess
from pathlib import Path

IGNORE = {"__pycache__", ".git", ".pytest_cache", ".claude", ".venv", "node_modules"}  # tool directories, not code


class LocalSandbox:
    def create(self, dest: Path, source: Path | None = None) -> Path:
        """A fresh workspace at `dest`: empty, or a copy of `source`, with its own git repo so any
        git commands an agent runs stay inside it."""
        if dest.exists():
            shutil.rmtree(dest)
        if source:
            copy_code(source, dest)
        else:
            dest.mkdir(parents=True)
        subprocess.run("git init -q && git add -A && git -c user.name=env -c user.email=env@local "
                       "commit -q --allow-empty -m base", shell=True, cwd=dest, check=True)
        return dest


def copy_code(src: Path, dest: Path) -> None:
    shutil.copytree(src, dest, ignore=shutil.ignore_patterns(*IGNORE))


def tree_digest(root: Path) -> str:
    """Fingerprint of a workspace's files (tool directories excluded)."""
    h = hashlib.md5()
    for p in sorted(root.rglob("*")):
        if p.is_file() and not set(p.relative_to(root).parts) & IGNORE:
            h.update(str(p.relative_to(root)).encode())
            h.update(p.read_bytes())
    return h.hexdigest()
