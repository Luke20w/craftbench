"""Build and verify replay probes: synthetic bases (a refactor reverted), hidden-test discovery with
repeated runs, and specs from the commit message plus the GitHub PR / linked issues."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

from envs import export_tree
from harness import Probe, overlay_tests, run_pytest
from mine import DATA, Commit, commit, git, is_test

GH_CACHE = DATA / "gh_cache"


# --- synthetic bases ----------------------------------------------------------------------------

def revert_onto(repo: Path, onto: str, r: Commit, ref: str) -> tuple[str | None, str]:
    """A commit = `onto` with refactor `r` reverted. Only trivial conflicts are resolved: conflicts in
    non-Python files (changelogs, docs) keep `onto`'s version. Returns (sha or None, note)."""
    return _synthesize(repo, onto, ["revert", "--no-commit", *(["-m", "1"] if r.is_merge else []), r.sha], ref,
                       f"{onto[:12]} with {r.sha[:12]} reverted")


def pick_onto(repo: Path, onto: str, f: Commit, ref: str) -> tuple[str | None, str]:
    """A commit = `onto` plus the changes of non-merge commit f (cherry-pick, same trivial-conflict rule)."""
    return _synthesize(repo, onto, ["cherry-pick", "--no-commit", f.sha], ref, f"{f.sha[:12]} applied onto {onto[:12]}")


def _synthesize(repo: Path, onto: str, args: list[str], ref: str, message: str) -> tuple[str | None, str]:
    existing = git(repo, "rev-parse", "-q", "--verify", f"refs/realrepo/{ref}", check=False).strip()
    if existing:
        return existing, "cached"
    wt = Path(tempfile.mkdtemp(prefix="rr-wt-")) / "wt"
    git(repo, "worktree", "add", "-q", "--detach", str(wt), onto)
    try:
        res = subprocess.run(["git", "-C", str(wt), *args], capture_output=True, text=True)
        note = "clean"
        if res.returncode:
            conflicted = git(wt, "diff", "--name-only", "--diff-filter=U").split()
            if not conflicted or any(p.endswith(".py") for p in conflicted):
                return None, f"conflict: {' '.join(conflicted) or res.stderr.strip()[:200]}"
            for p in conflicted:
                git(wt, "checkout", "--ours", "--", p)
                git(wt, "add", "--", p)
            note = f"trivial conflicts kept from base: {' '.join(conflicted)}"
        env_args = ["-c", "user.name=realrepo", "-c", "user.email=realrepo@local"]
        subprocess.run(["git", "-C", str(wt), *env_args, "commit", "-q", "--allow-empty", "--no-verify", "-m",
                        f"realrepo: {message}"], check=True, capture_output=True,
                       env={"GIT_AUTHOR_DATE": "2000-01-01T00:00:00", "GIT_COMMITTER_DATE": "2000-01-01T00:00:00",
                            "PATH": "/usr/bin:/bin:/opt/homebrew/bin"})
        sha = git(wt, "rev-parse", "HEAD").strip()
        git(repo, "update-ref", f"refs/realrepo/{ref}", sha)
        return sha, note
    finally:
        git(repo, "worktree", "remove", "--force", str(wt), check=False)
        shutil.rmtree(wt.parent, ignore_errors=True)


# --- running a tree with some revision's tests ----------------------------------------------------

def run_tree(python: Path, repo: Path, rev: str, probe: Probe, with_commit_tests: bool = True,
             targets: list[str] | None = None) -> tuple[dict[str, str], float]:
    """Outcomes of `rev`'s code with the probe commit's test dirs (or its own), and seconds taken."""
    with tempfile.TemporaryDirectory(prefix="rr-run-") as tmp:
        ws = export_tree(repo, rev, Path(tmp) / "code")
        if with_commit_tests:
            overlay_tests(probe, ws)
        t0 = time.time()
        default = [d for d in probe.test_dirs if (ws / d).exists() and Path(d).name != "conftest.py"]
        out = run_pytest(python, ws, targets or default,
                         probe.pythonpath, extra=tuple(probe.pytest_args))
        return out, time.time() - t0


def passed(o: dict[str, str]) -> set[str]:
    return {k for k, v in o.items() if v == "passed"}


def discover(python: Path, probe: Probe, runs: int = 2, candidates: list[str] | None = None) -> dict:
    """Fill probe.hidden / probe.regression by running base and oracle with the commit's tests.

    hidden     = in a test file the commit changed; passes on the oracle in every run (whole-suite and
                 ids-only), fails on the base in every run.
    regression = passes on base and oracle in every run, and isn't hidden.
    Without an oracle, hidden = `candidates` (e.g. the same commit's hidden tests on another base) that
    fail on this base. Returns the verification record; its "_visible_passed" is a set (not JSON)."""
    repo = DATA / probe.clone
    parent = git(repo, "rev-parse", f"{probe.commit}^").strip()
    changed = [p for p in git(repo, "diff", "--name-only", parent, probe.commit, "--", *probe.test_dirs).split()]
    visible, t_vis = run_tree(python, repo, probe.base, probe, with_commit_tests=False)
    base_runs = [run_tree(python, repo, probe.base, probe) for _ in range(runs)]
    ora_runs = [run_tree(python, repo, probe.oracle, probe) for _ in range(runs)] if probe.oracle else []
    b_any = set().union(*(passed(o) for o, _ in base_runs))
    b_all = set.intersection(*(passed(o) for o, _ in base_runs))
    o_all = set.intersection(*(passed(o) for o, _ in ora_runs)) if ora_runs else set()
    in_changed = lambda t: t.split("::")[0] in changed  # noqa: E731
    if ora_runs:
        hidden = sorted(t for t in o_all - b_any if in_changed(t))
    else:
        hidden = sorted(set(candidates or []) - b_any)
    rec: dict = {"changed_test_files": changed,
                 "visible_suite": {"collected": len(visible), "passed": len(passed(visible)),
                                   "seconds": round(t_vis, 1)},
                 "base_with_commit_tests": [{"collected": len(o), "passed": len(passed(o))} for o, _ in base_runs],
                 "oracle_with_commit_tests": [{"collected": len(o), "passed": len(passed(o))} for o, _ in ora_runs]}
    flaky = set()
    for runs_ in (base_runs, ora_runs):
        if runs_:
            flaky |= set().union(*(passed(o) for o, _ in runs_)) - set.intersection(*(passed(o) for o, _ in runs_))
    rec["flaky"] = sorted(flaky)
    rec["commit_tests_failing_on_oracle"] = sorted(t for t in (set(ora_runs[0][0]) if ora_runs else set())
                                                    if in_changed(t) and t not in o_all)
    if hidden:  # the grader runs hidden tests alone when it skips regression: check that mode too
        b_ids, _ = run_tree(python, repo, probe.base, probe, targets=hidden)
        bad = set(hidden) & passed(b_ids)
        if probe.oracle:
            o_ids, _ = run_tree(python, repo, probe.oracle, probe, targets=hidden)
            bad |= set(hidden) - passed(o_ids)
        bad = sorted(bad)
        rec["ids_only_disagree"] = bad
        hidden = [t for t in hidden if t not in bad]
    rec["hidden_new"] = sorted(t for t in hidden if t not in visible)
    rec["hidden_modified"] = sorted(t for t in hidden if t in visible)
    probe.hidden = hidden
    probe.regression = sorted((b_all & o_all) - set(hidden)) if ora_runs else sorted(b_all)
    rec["hidden"] = len(hidden)
    rec["regression"] = len(probe.regression)
    rec["seconds_full_suite"] = round(max(t for _, t in base_runs), 1)
    rec["_visible_passed"] = passed(visible)
    return rec


# --- specs --------------------------------------------------------------------------------------

def _gh(path: str) -> object:
    GH_CACHE.mkdir(parents=True, exist_ok=True)
    f = GH_CACHE / (hashlib.md5(path.encode()).hexdigest() + ".json")
    if f.exists():
        return json.loads(f.read_text())
    r = subprocess.run(["gh", "api", "-H", "Accept: application/vnd.github+json", path], capture_output=True,
                       text=True)
    data = json.loads(r.stdout) if r.returncode == 0 and r.stdout.strip() else None
    f.write_text(json.dumps(data))
    return data


TEMPLATE_LINES = re.compile(r"^\s*(- \[[ x]\]|<!--|-->|Checklist:?$|Describe what this patch does|"
                            r"Link to any relevant issues|fixes #$|Thank you for)", re.I)


# Paragraphs of PR text that describe how the change was implemented rather than what is wanted.
SOLUTION_TALK = re.compile(
    r"\b(my (solution|fix|approach|implementation)|the (solution|fix|approach|implementation) (is|was|here)|"
    r"this (pr|pull request|patch|change|commit) (adds|changes|fixes|implements|introduces|refactors|moves|"
    r"makes|uses|replaces|removes)|i (used|added|changed|moved|refactored|implemented|introduced|made|replaced|"
    r"removed|updated|wrapped|extracted)|i've|i have (added|changed|moved|implemented)|implemented by|"
    r"solves? (the|this) issue|fixed by)\b", re.I)


def _clean(text: str, solution_lines: set[str]) -> tuple[str, list[str]]:
    """Drop PR-template boilerplate, HTML comments and code blocks that quote the solution's code."""
    notes = []
    text = re.sub(r"<!--.*?-->", "", text or "", flags=re.S)

    def block(m: re.Match) -> str:
        lines = {ln.strip() for ln in m.group(0).splitlines()[1:-1] if len(ln.strip()) > 12}
        if len(lines & solution_lines) >= 2:
            notes.append("removed a code block quoting the solution")
            return "[code quoting the solution removed]"
        return m.group(0)

    text = re.sub(r"```.*?```", block, text, flags=re.S)
    kept = [ln for ln in text.splitlines() if not TEMPLATE_LINES.match(ln)]
    paras = re.split(r"\n\s*\n", "\n".join(kept))
    solution_paras = [p for p in paras if SOLUTION_TALK.search(p)]
    if solution_paras:
        notes.append(f"removed {len(solution_paras)} paragraph(s) describing the implementation")
    text = "\n\n".join(p for p in paras if p not in solution_paras)
    return re.sub(r"\n{3,}", "\n\n", text).strip(), notes


def spec_for(repo: Path, slug: str, c: Commit) -> tuple[str, dict]:
    """Commit message, plus the PR description and linked issues (via the GitHub API, cached)."""
    diff = git(repo, "show", "--format=", c.sha, "--", ".", ":(exclude)tests", ":(exclude)*.rst", ":(exclude)*.md")
    solution = {ln[1:].strip() for ln in diff.splitlines()
                if ln.startswith("+") and not ln.startswith("+++") and len(ln.strip()) > 12}
    trailer = re.compile(r"^(co-authored-by|signed-off-by|reviewed-by):", re.I)
    parts = ["\n".join(ln for ln in c.message.splitlines() if not trailer.match(ln.strip())).strip()]
    meta: dict = {"pr": None, "issues": [], "notes": []}
    prs = _gh(f"repos/{slug}/commits/{c.sha}/pulls") or []
    pr = next((p for p in prs if p.get("merged_at")), prs[0] if prs else None)
    issue_nums = set(map(int, re.findall(r"#(\d+)", c.message)))
    if pr:
        meta["pr"] = pr["number"]
        body, notes = _clean(pr.get("body") or "", solution)
        meta["notes"] += notes
        if pr["title"].strip() not in c.message or body:
            parts.append(f"Pull request #{pr['number']}: {pr['title']}\n\n{body}".strip())
        issue_nums |= set(map(int, re.findall(
            r"(?:fix(?:es|ed)?|close[sd]?|resolve[sd]?|see|for|issue)\s*:?\s*#(\d+)", body, re.I)))
        issue_nums |= set(map(int, re.findall(rf"github\.com/{re.escape(slug)}/issues/(\d+)", body)))
        issue_nums.discard(pr["number"])
    for n in sorted(issue_nums)[:3]:
        iss = _gh(f"repos/{slug}/issues/{n}")
        if not iss or "pull_request" in iss:
            continue
        body, notes = _clean(iss.get("body") or "", solution)
        meta["notes"] += notes
        meta["issues"].append(n)
        parts.append(f"Issue #{n}: {iss['title']}\n\n{body}".strip())
    return "\n\n---\n\n".join(p for p in parts if p.strip()), meta


def is_test_path(p: str) -> bool:
    return is_test(p)





def quick_hidden(python: Path, probe: Probe) -> list[str]:
    """Cheap pre-filter: tests in the commit's changed test files failing on base, passing on oracle
    (one run each, changed files only)."""
    repo = DATA / probe.clone
    parent = git(repo, "rev-parse", f"{probe.commit}^").strip()
    changed = [p for p in git(repo, "diff", "--name-only", "--diff-filter=AM", parent, probe.commit, "--",
                              *probe.test_dirs).split() if p.endswith(".py") and Path(p).name != "conftest.py"]
    if not changed:
        return []
    b, _ = run_tree(python, repo, probe.base, probe, targets=changed)
    o, _ = run_tree(python, repo, probe.oracle, probe, targets=changed)
    return sorted(passed(o) - passed(b))
