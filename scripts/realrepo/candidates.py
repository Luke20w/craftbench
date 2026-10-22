"""Mine candidate (refactor, follow-up) pairs from a repo's history; no tests are run here.

Refactor R: message looks like a refactoring (keywords), not formatting/typing/docs noise, changes
>= 30 source lines and no test files.
Follow-up F: a non-merge descendant of R within 183 days that changes both source and tests and
touches R's code: >= 2 changed lines that `git blame` attributes to R (padded by 2 lines), or a
function/method R changed (same file, same qualified name).

    python scripts/realrepo/candidates.py REPO [REPO ...]   # writes .context/realrepo/candidates/REPO.json
"""

from __future__ import annotations

import ast
import json
import re
import sys
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from mine import DATA, REPOS, Commit, git, is_source, is_test, log, overlap_with, pr_commits, touched_old_lines  # noqa: E402

KW = re.compile(r"refactor|clean ?up|simplif|extract|restructur|reorganiz|consolidat|dedup|split|move|rewrite|"
                r"rework|tidy|untangle|internal|inline|helper|reuse|unify|generali[sz]e|decouple|separate|"
                r"factor|share|common|replace .* with", re.I)
NOISE = re.compile(r"black|flake8|pyupgrade|ruff|lint|typing|type hint|annotat|mypy|drop (support|python)|format|"
                   r"pre-commit|isort|python ?2|py2|\bdocs?\b|docstring|typo|bump|release|version|src director|"
                   r"changelog|deprecat", re.I)
NOISE_F = re.compile(r"black|flake8|pyupgrade|ruff|lint|typing|type hint|annotat|mypy|drop (support|python)|"
                     r"format|pre-commit|isort|python ?2|typo|bump|release|^revert", re.I)
MAX_REFACTOR_LINES = 1500  # bigger ones are mechanical moves (e.g. "move to src directory")


def qualnames(source: str, ranges: list[tuple[int, int]]) -> set[str]:
    """Qualified names of the innermost functions/classes overlapping the line ranges."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return set()
    spans: list[tuple[int, int, str]] = []

    def walk(node: ast.AST, prefix: str) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                name = f"{prefix}{child.name}"
                start = min([child.lineno, *(d.lineno for d in child.decorator_list)])
                spans.append((start, child.end_lineno or child.lineno, name))
                walk(child, name + ".")
    walk(tree, "")
    hits = set()
    for lo, hi in ranges:
        inner = [s for s in spans if s[0] <= hi and lo <= s[1]]
        # keep the innermost: spans not containing another hit span
        for s in inner:
            if not any(t is not s and s[0] <= t[0] and t[1] <= s[1] for t in inner):
                hits.add(s[2])
    return hits


def changed_functions(repo: Path, old: str, new: str, path: str, side: str) -> set[str]:
    """Functions touched by old->new in `path`, named in the `side` ('old' or 'new') version."""
    rev = old if side == "old" else new
    src = git(repo, "show", f"{rev}:{path}", check=False)
    if side == "old":
        ranges = touched_old_lines(repo, old, new, path, pad=0)
    else:
        diff = git(repo, "diff", "-U0", old, new, "--", path)
        ranges = []
        for m in re.finditer(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@", diff, re.M):
            start, count = int(m.group(1)), int(m.group(2) or 1)
            ranges.append((start, start + max(count, 1) - 1))
    return {f"{path}::{q}" for q in qualnames(src, ranges)}


def refactor_functions(repo: Path, r: Commit) -> set[str]:
    return set().union(*[changed_functions(repo, r.parents[0], r.sha, p, "new") for p in r.files(is_source)]) \
        if r.files(is_source) else set()


def mine_repo(name: str, since: str = "2018-06-01") -> list[dict]:
    repo = REPOS / name
    allc = log(repo, f"--since={since}", "HEAD")
    by_sha = {c.sha: c for c in allc}
    out = []
    for r in allc:
        title = r.title
        if (not KW.search(title) or NOISE.search(title) or title.startswith("Merge branch")
                or "revert" in title.lower()):
            continue
        src, tst = r.churn(is_source), r.churn(is_test)
        if not (30 <= src <= MAX_REFACTOR_LINES) or tst:
            continue
        authors = pr_commits(repo, r)
        lo, hi = r.day, r.day + timedelta(days=183)
        # descendants of R only (--ancestry-path); explicit times, since git reads a bare date as
        # "that day at the current time of day"
        desc = git(repo, "rev-list", "--no-merges", "--ancestry-path", f"--since={lo.isoformat()} 00:00:00",
                   f"--until={hi.isoformat()} 23:59:59", f"{r.sha}..HEAD").split()
        r_funcs = refactor_functions(repo, r)
        followups = []
        for sha in desc:
            f = by_sha.get(sha)
            if (not f or f.sha in authors or NOISE_F.search(f.subject) or not f.files(is_source)
                    or not f.files(is_test) or not (lo <= f.day <= hi)):
                continue
            blame = overlap_with(repo, f, authors)
            f_funcs = set().union(*[changed_functions(repo, f.parents[0], f.sha, p, "old")
                                    for p in f.files(is_source)])
            shared = sorted(r_funcs & f_funcs)
            if blame >= 2 or shared:
                followups.append({"sha": f.sha, "date": f.date, "author": f.author, "subject": f.subject,
                                  "blame_overlap": blame, "shared_functions": shared})
        out.append({"repo": name, "sha": r.sha, "date": r.date, "author": r.author, "title": title,
                    "merge": r.is_merge, "source_lines": src, "functions": sorted(r_funcs),
                    "followups": sorted(followups, key=lambda x: x["date"])})
        print(f"{name:14} {r.sha[:9]} {r.date} src={src:4} F={len(followups):2} | {title[:70]}", flush=True)
    return out


if __name__ == "__main__":
    (DATA / "candidates").mkdir(parents=True, exist_ok=True)
    for name in sys.argv[1:]:
        res = mine_repo(name)
        (DATA / "candidates" / f"{name}.json").write_text(json.dumps(res, indent=1))
