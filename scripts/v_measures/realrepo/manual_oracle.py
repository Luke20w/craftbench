"""Hand-ported `before` oracles, for pairs where git can't apply F onto F^-with-R-reverted.

    python scripts/v_measures/realrepo/manual_oracle.py start  REPO R F     # worktree at the before base, F cherry-picked (conflicts left)
    (resolve the conflicts by hand: port F's behaviour onto the pre-refactor code; don't touch tests)
    python scripts/v_measures/realrepo/manual_oracle.py commit REPO R F     # commit, keep under refs/realrepo/manual/, record it

Recorded in .context/realrepo/manual_oracles.json; build_refactor_pairs.py then verifies the hidden tests
pass on it like any other oracle."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from build_refactor_pairs import MANUAL  # noqa: E402
from mine import DATA, REPOS, commit, git  # noqa: E402


def worktree(repo: str, r: str, f: str) -> Path:
    return DATA / "manual" / f"{repo}-{r[:8]}-{f[:8]}"


def before_base(repo: Path, r: str, f: str) -> str:
    parent = git(repo, "rev-parse", f"{f}^").strip()
    return git(repo, "rev-parse", f"refs/realrepo/{git(repo, 'rev-parse', r).strip()[:12]}-on-{parent[:12]}").strip()


def main(cmd: str, name: str, r: str, f: str) -> None:
    repo = REPOS / name
    wt = worktree(name, r, f)
    if cmd == "start":
        git(repo, "worktree", "add", "-q", "--detach", str(wt), before_base(repo, r, f))
        subprocess.run(["git", "-C", str(wt), "cherry-pick", "--no-commit", git(repo, "rev-parse", f).strip()])
        print(wt)
    elif cmd == "commit":
        subprocess.run(["git", "-C", str(wt), "add", "-A"], check=True)
        msg = f"realrepo: {f[:12]} hand-ported onto {before_base(repo, r, f)[:12]} (before base)"
        subprocess.run(["git", "-C", str(wt), "-c", "user.name=realrepo", "-c", "user.email=realrepo@local",
                        "commit", "-q", "--no-verify", "-m", msg], check=True)
        sha = git(wt, "rev-parse", "HEAD").strip()
        r12, f12 = git(repo, "rev-parse", r).strip()[:12], commit(repo, f).sha[:12]
        git(repo, "update-ref", f"refs/realrepo/manual/{r12}-{f12}", sha)
        table = json.loads(MANUAL.read_text()) if MANUAL.exists() else {}
        table[f"{name}:{r12}:{f12}"] = sha
        MANUAL.write_text(json.dumps(table, indent=1))
        git(repo, "worktree", "remove", "--force", str(wt), check=False)
        git(repo, "worktree", "prune")
        shutil.rmtree(wt, ignore_errors=True)
        print(sha)


if __name__ == "__main__":
    main(*sys.argv[1:5])
