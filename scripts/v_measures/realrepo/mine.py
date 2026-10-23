"""Git mining helpers for replay probes: classify files, find refactors and the later commits that
touch the code they wrote, and history statistics. Pure git (no network, no models)."""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DATA = ROOT / ".context" / "realrepo"
REPOS = DATA / "repos"

NON_SOURCE_DIRS = ("docs/", "doc/", "examples/", "example/", "scripts/", "bench", "artwork/", ".github/",
                   "requirements/", "changelog.d/", "typing_examples", "conftest")


def git(repo: Path, *args: str, check: bool = True) -> str:
    r = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True)
    if check and r.returncode:
        raise RuntimeError(f"git {' '.join(args)}: {r.stderr.strip()}")
    return r.stdout


def is_test(path: str) -> bool:
    name = Path(path).name
    return (path.startswith(("tests/", "test/", "testing/")) or "/tests/" in path
            or name.startswith("test_") or name.endswith("_test.py") or name == "conftest.py")


def is_source(path: str) -> bool:
    return (path.endswith(".py") and not is_test(path) and not path.startswith(NON_SOURCE_DIRS)
            and Path(path).name not in ("setup.py", "noxfile.py", "conf.py", "tasks.py"))


@dataclass
class Commit:
    sha: str
    date: str          # committer date, YYYY-MM-DD
    author: str
    subject: str
    body: str
    parents: list[str]
    numstat: dict[str, tuple[int, int]] = field(default_factory=dict)  # path -> (added, deleted) vs first parent

    @property
    def is_merge(self) -> bool:
        return len(self.parents) > 1

    @property
    def message(self) -> str:
        return (self.subject + "\n\n" + self.body).strip()

    @property
    def title(self) -> str:
        """The PR title for a GitHub merge commit, else the subject."""
        if self.subject.startswith("Merge pull request") and self.body.strip():
            return self.body.strip().splitlines()[0]
        return self.subject

    def churn(self, pred=is_source) -> int:
        return sum(a + d for p, (a, d) in self.numstat.items() if pred(p))

    def files(self, pred=lambda p: True) -> list[str]:
        return [p for p in self.numstat if pred(p)]

    @property
    def day(self) -> date:
        return date.fromisoformat(self.date)


_SEP = "\x1e"


def log(repo: Path, *rev: str, first_parent: bool = False, merges: bool = True) -> list[Commit]:
    """Commits with numstat against the first parent (merges included, diffed against parent 1)."""
    args =["log", f"--format={_SEP}%H%x1f%cs%x1f%an%x1f%P%x1f%s%x1f%b%x1f", "--numstat",
            "--diff-merges=first-parent", "--no-renames"]
    if first_parent:
        args.append("--first-parent")
    if not merges:
        args.append("--no-merges")
    out = git(repo, *args, *rev)
    commits = []
    for block in out.split(_SEP)[1:]:
        sha, day, author, parents, subject, body, stat = block.split("\x1f")
        c = Commit(sha, day, author, subject, body.strip(), parents.split())
        for row in stat.strip().splitlines():
            parts = row.split("\t")
            if len(parts) == 3:
                a, d, p = parts
                c.numstat[p] = (int(a) if a != "-" else 0, int(d) if d != "-" else 0)
        commits.append(c)
    return commits


def commit(repo: Path, rev: str) -> Commit:
    return log(repo, "-1", rev)[0]


def is_ancestor(repo: Path, a: str, b: str) -> bool:
    return subprocess.run(["git", "-C", str(repo), "merge-base", "--is-ancestor", a, b]).returncode == 0


def pr_commits(repo: Path, c: Commit) -> set[str]:
    """The commits a change introduced: itself, plus a merge's branch commits."""
    if not c.is_merge:
        return {c.sha}
    return {c.sha, *git(repo, "rev-list", f"{c.parents[0]}..{c.sha}").split()}


_HUNK = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+\d+(?:,\d+)? @@", re.M)


def touched_old_lines(repo: Path, parent: str, sha: str, path: str, pad: int = 2) -> list[tuple[int, int]]:
    """Line ranges of `path` in `parent` that the change from parent to sha modifies (padded)."""
    diff = git(repo, "diff", "-U0", parent, sha, "--", path)
    ranges = []
    for m in _HUNK.finditer(diff):
        start, count = int(m.group(1)), int(m.group(2) or 1)
        lo, hi = (start, start + count - 1) if count else (start, start + 1)
        ranges.append((max(1, lo - pad), hi + pad))
    return ranges


def blamed_lines(repo: Path, rev: str, path: str, ranges: list[tuple[int, int]], authors: set[str]) -> int:
    """How many lines in `ranges` of `path` at `rev` were last written by one of the commits `authors`."""
    n_lines = git(repo, "show", f"{rev}:{path}", check=False).count("\n")
    hits = 0
    for lo, hi in ranges:
        hi = min(hi, n_lines)
        if lo > hi:
            continue
        out = git(repo, "blame", "-l", "-s", "-L", f"{lo},{hi}", rev, "--", path, check=False)
        hits += sum(line.lstrip("^")[:40] in authors for line in out.splitlines())
    return hits


def overlap_with(repo: Path, f: Commit, authors: set[str]) -> int:
    """Lines of source that commit f changes which were written by `authors` (e.g. a refactor)."""
    parent = f.parents[0]
    total = 0
    for p in f.files(is_source):
        if git(repo, "cat-file", "-t", f"{parent}:{p}", check=False).strip() != "blob":
            continue
        total += blamed_lines(repo, parent, p, touched_old_lines(repo, parent, f.sha, p), authors)
    return total


def source_kloc(repo: Path, rev: str, path: str) -> float:
    text = git(repo, "show", f"{rev}:{path}", check=False)
    return sum(1 for line in text.splitlines() if line.strip()) / 1000
