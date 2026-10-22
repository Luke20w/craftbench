"""Dataset 2 (pilot): per-module replay probes at a snapshot T, and what the module's later history did.

For each source module at T (>= MIN_LINES non-blank lines):
  probes    up to 2 verified replay probes from real commits in (T, T+6 months] that touch the module.
            Commits whose source churn is mostly in that module are tried first; a commit touching
            several modules can serve each of them (its "module_share" is recorded).
  outcomes  from (T+6 months, T+3 years], non-merge commits reachable from HEAD that touch the module:
            commits, bug fixes (heuristic below), lines churned, co-change (other source files changed
            in the same commit), reverts. Raw counts plus per-commit and per-KLOC (KLOC at T) rates.

Files are tracked across renames and splits: a path that didn't exist at T belongs to the T-module it
was renamed from, or split out of (the T-module its creating commit deleted the most lines from, if
>= 30% of the new file's size), else the T-module `git blame -C -C` attributes >= 50% of its lines to;
otherwise it is new code and not counted for any module.

    python scripts/realrepo/build_module_history.py   # resumable; writes module_history.json
"""

from __future__ import annotations

import json
import re
import sys
import traceback
from collections import Counter, defaultdict
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from build_refactor_pairs import PYTEST_ARGS, SLUGS, env_for, layout, register_env, run_hint  # noqa: E402
from candidates import NOISE_F  # noqa: E402
from harness import Probe  # noqa: E402
from mine import DATA, REPOS, Commit, git, is_source, is_test, log  # noqa: E402
from replay import discover, quick_hidden, spec_for  # noqa: E402

REPO = "werkzeug"
T_DATE = date(2023, 1, 1)
PROBE_DAYS = 183
OUTCOME_END_DAYS = 3 * 365
MIN_LINES = 100
PROBES_PER_MODULE = 2
MAX_TRIES_PER_MODULE = 6
CACHE = DATA / "cache" / "module_history"
OUT = DATA / "module_history.json"

# Bug-fix heuristic on the commit message (subject + body). Matches fix/fixes/fixed/fixing, bug,
# regression, "issue #N", "fixes/closes/resolves #N"; ignores fixes of non-behaviour (typos, docs,
# lint, typing, tests, CI, changelog).
BUGFIX = re.compile(r"\b(fix(e[sd]|ing)?|bugs?|bugfix|regression|crash(es|ed)?|issue\s*#?\d+|"
                    r"(close[sd]?|resolve[sd]?)\s*#\d+)\b", re.I)
NOT_BEHAVIOUR = re.compile(r"\bfix(e[sd]|ing)?\s+(the\s+)?(typos?|docs?|documentation|docstrings?|lint|flake8|mypy|"
                           r"typing|types?|type hints?|annotations?|tests?|ci|changelog|links?|formatting|"
                           r"spelling|grammar|pre-commit|warnings? in tests)\b", re.I)
NOISE = re.compile(r"\b(black|flake8|pyupgrade|ruff|isort|pre-commit|mypy|typing|type hints?|annotations?|"
                   r"format(ting)?|lint|bugbear|release version|start version|update dependencies|bump)\b", re.I)


def is_bugfix_message(c: Commit) -> bool:
    return bool(BUGFIX.search(c.message)) and not NOT_BEHAVIOUR.search(c.subject) and not NOISE.search(c.subject)


CHANGELOG = re.compile(r"^(CHANGES|CHANGELOG|HISTORY|NEWS)(\.\w+)?$", re.I)
VERSION_HEADING = re.compile(r"^(?:Version\s+)?v?(\d+)\.(\d+)\.(\d+)\b")


def is_bugfix_changelog(repo: Path, c: Commit) -> bool:
    """The commit adds a changelog entry under a patch release heading (X.Y.Z with Z > 0). Pallets
    projects only put bug fixes in patch releases, so this catches fixes whose message doesn't say so."""
    if NOISE.search(c.subject):
        return False
    for p in c.numstat:
        if not CHANGELOG.match(Path(p).name):
            continue
        new_text = git(repo, "show", f"{c.sha}:{p}", check=False).splitlines()
        diff = git(repo, "diff", "-U0", c.parents[0], c.sha, "--", p)
        for m in re.finditer(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@", diff, re.M):
            start, count = int(m.group(1)), int(m.group(2) or 1)
            for ln in range(start, start + count):
                if ln - 1 >= len(new_text) or not new_text[ln - 1].strip().startswith(("-", "*")):
                    continue  # only entry lines, not headings
                for prev in range(ln - 1, -1, -1):
                    v = VERSION_HEADING.match(new_text[prev].strip())
                    if v:
                        if int(v.group(3)) > 0:
                            return True
                        break
    return False


def snapshot(repo: Path, day: date) -> str:
    return git(repo, "log", "--first-parent", f"--until={day.isoformat()}", "-1", "--format=%H", "HEAD").strip()


def nonblank(repo: Path, rev: str, path: str) -> int:
    return sum(1 for ln in git(repo, "show", f"{rev}:{path}", check=False).splitlines() if ln.strip())


class Provenance:
    """Maps a source path at some revision to the T-module its code came from."""

    def __init__(self, repo: Path, t_rev: str, modules: set[str]):
        self.repo, self.t_rev, self.modules = repo, t_rev, modules
        self.t_paths = set(git(repo, "ls-tree", "-r", "--name-only", t_rev).split())
        self._cache: dict[str, str | None] = {}

    def module(self, rev: str, path: str) -> str | None:
        """Provenance is computed the first time a path is seen (at that revision) and then reused."""
        if path not in self._cache:
            self._cache[path] = self._module(rev, path)
        return self._cache[path]

    def _module(self, rev: str, path: str) -> str | None:
        if path in self.modules:
            return path
        if path in self.t_paths:  # existed at T but too small to be a module
            return None
        return self._by_creation(rev, path) or self._by_blame(rev, path)

    def _by_creation(self, rev: str, path: str) -> str | None:
        """The file was created after T: by renaming another file (follow it), or in a commit that
        deleted lines from T-modules (a split / move): the T-module losing the most lines, if those
        deletions are >= 30% of the new file's lines."""
        out = git(self.repo, "log", "--follow", "-M", "--format=@%H", "--name-status", rev, "--", path, check=False)
        events = [blk for blk in out.split("@")[1:] if blk.strip()]
        if not events:
            return None
        sha, *rows = events[-1].strip().splitlines()  # the oldest event: how the file came to be
        row = next((r.split("\t") for r in rows if r.strip()), None)
        if not row:
            return None
        if row[0].startswith("R") and len(row) == 3:
            old = row[1]
            return old if old in self.modules else (None if old in self.t_paths else self._by_creation(f"{sha}^", old))
        added = git(self.repo, "show", "--numstat", "--format=", sha, "--", row[-1], check=False).split()
        n_added = int(added[0]) if added and added[0].isdigit() else 0
        dels = Counter()
        for r in git(self.repo, "show", "--numstat", "--format=", "-M", sha, check=False).splitlines():
            parts = r.split("\t")
            if len(parts) == 3 and parts[1].isdigit() and parts[2] in self.modules:
                dels[parts[2]] = int(parts[1])
        if dels:
            best, n = dels.most_common(1)[0]
            if n >= 0.3 * max(1, n_added):
                return best
        return None

    def _by_blame(self, rev: str, path: str) -> str | None:
        out = git(self.repo, "blame", "-C", "-C", "-w", "--line-porcelain", f"{self.t_rev}..{rev}", "--", path,
                  check=False)
        origins, total, cur_boundary = Counter(), 0, False
        for line in out.splitlines():
            if re.match(r"^[0-9a-f]{40} ", line):
                total += 1
                cur_boundary = False
            elif line == "boundary":
                cur_boundary = True
            elif line.startswith("filename ") and cur_boundary:
                origins[line[9:]] += 1
        if not total or not origins:
            return None
        best, n = origins.most_common(1)[0]
        return best if best in self.modules and n >= 0.5 * total else None


def commit_modules(prov: Provenance, c: Commit) -> dict[str, int]:
    """T-module -> source lines this commit churned in it (paths mapped at the commit's parent, or at
    the commit for files it creates)."""
    out: dict[str, int] = defaultdict(int)
    parent = c.parents[0]
    for p in c.files(is_source):
        exists_before = git(prov.repo, "cat-file", "-t", f"{parent}:{p}", check=False).strip() == "blob"
        m = prov.module(parent if exists_before else c.sha, p)
        if m:
            a, d = c.numstat[p]
            out[m] += a + d
    return dict(out)


def verify_probe(repo: Path, c: Commit, envs: dict) -> dict:
    f = CACHE / f"probe-{c.sha[:12]}.json"
    if f.exists():
        return json.loads(f.read_text())
    try:
        rec = _verify_probe(repo, c, envs)
    except Exception as e:  # noqa: BLE001
        traceback.print_exc()
        rec = {"status": "discarded", "reason": f"crashed: {e}"}
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(rec, indent=1))
    return rec


def _verify_probe(repo: Path, c: Commit, envs: dict) -> dict:
    env, py = env_for(repo, c.parents[0], envs)
    lay = layout(repo, c.sha)
    p = Probe(id=f"{repo.name}-{c.sha[:8]}", repo=SLUGS[repo.name], clone=f"repos/{repo.name}", base=c.parents[0],
              commit=c.sha, oracle=c.sha, spec="", env=env, hidden=[], pytest_args=PYTEST_ARGS.get(repo.name, []),
              **lay)
    if not quick_hidden(py, p):
        return {"status": "discarded", "reason": "no test in the commit's changed test files fails on base and passes on commit"}
    rec = discover(py, p)
    rec.pop("_visible_passed")
    if not p.hidden:
        return {"status": "discarded", "reason": "no stable hidden test after full verification", "verification": rec}
    p.spec, meta = spec_for(repo, SLUGS[repo.name], c)
    p.meta = {"spec_sources": meta}
    p.verification = rec
    p.run = run_hint(p)
    return {"status": "ok", "probe": p.to_dict()}


def outcomes(prov: Provenance, commits: list[Commit], kloc: dict[str, float]) -> dict[str, dict]:
    per = {m: {"commits": 0, "commits_excluding_noise": 0, "bugfix_commits": 0, "bugfix_by_message": 0,
               "bugfix_by_changelog": 0, "lines_churned": 0, "lines_churned_excluding_noise": 0,
               "cochange_files": [], "cochange_files_excluding_noise": [], "reverts": 0, "bugfix_subjects": []}
           for m in kloc}
    reverted = {m.group(1) for c in commits for m in [re.search(r"This reverts commit ([0-9a-f]{7,40})", c.body)] if m}
    for c in commits:
        mods = commit_modules(prov, c)
        if not mods:
            continue
        src_files = c.files(is_source)
        noise = bool(NOISE.search(c.subject))
        by_msg, by_log = is_bugfix_message(c), is_bugfix_changelog(prov.repo, c)
        for m, churn in mods.items():
            o = per[m]
            o["commits"] += 1
            o["lines_churned"] += churn
            own = [p for p in src_files if prov.module(c.parents[0], p) == m or prov.module(c.sha, p) == m]
            o["cochange_files"].append(len(src_files) - len(own))
            if not noise:
                o["commits_excluding_noise"] += 1
                o["lines_churned_excluding_noise"] += churn
                o["cochange_files_excluding_noise"].append(len(src_files) - len(own))
            o["bugfix_by_message"] += by_msg
            o["bugfix_by_changelog"] += by_log
            if by_msg or by_log:
                o["bugfix_commits"] += 1
                o["bugfix_subjects"].append(c.subject[:100])
            if c.subject.lower().startswith("revert") or any(c.sha.startswith(r) for r in reverted):
                o["reverts"] += 1
    for m, o in per.items():
        n, k = o["commits"], kloc[m]
        co, co_n = o.pop("cochange_files"), o.pop("cochange_files_excluding_noise")
        nn = o["commits_excluding_noise"]
        o["mean_cochange_other_source_files"] = round(sum(co) / len(co), 3) if co else None
        o["mean_cochange_other_source_files_excluding_noise"] = round(sum(co_n) / len(co_n), 3) if co_n else None
        o["bugfix_share"] = round(o["bugfix_commits"] / nn, 3) if nn else None  # of non-noise commits
        o["churn_per_commit"] = round(o["lines_churned_excluding_noise"] / nn, 1) if nn else None
        o["per_kloc"] = {"commits": round(n / k, 2), "commits_excluding_noise": round(nn / k, 2),
                         "bugfix_commits": round(o["bugfix_commits"] / k, 2),
                         "lines_churned_excluding_noise": round(o["lines_churned_excluding_noise"] / k, 1)}
    return per


def main() -> None:
    repo = REPOS / REPO
    t_rev = snapshot(repo, T_DATE)
    t_day = date.fromisoformat(git(repo, "log", "-1", "--format=%cs", t_rev).strip())
    lay = layout(repo, t_rev)
    paths = [p for p in git(repo, "ls-tree", "-r", "--name-only", t_rev).split() if is_source(p) and p.endswith(".py")]
    sizes = {p: nonblank(repo, t_rev, p) for p in paths}
    modules = sorted(p for p, n in sizes.items() if n >= MIN_LINES)
    kloc = {m: sizes[m] / 1000 for m in modules}
    prov = Provenance(repo, t_rev, set(modules))
    envs: dict = json.loads(OUT.read_text()).get("envs", {}) if OUT.exists() else {}

    probe_end = T_DATE + timedelta(days=PROBE_DAYS)
    window = log(repo, f"--since={(T_DATE - timedelta(days=60)).isoformat()}",
                 f"--until={(probe_end + timedelta(days=2)).isoformat()}", "HEAD", merges=False)
    window = [c for c in window if T_DATE < c.day <= probe_end]
    probe_commits = [c for c in window if c.files(is_source) and c.files(is_test) and not NOISE_F.search(c.subject)
                     and not NOISE.search(c.subject)]
    touches = {c.sha: commit_modules(prov, c) for c in probe_commits}

    per_module: dict[str, dict] = {}
    probes: dict[str, dict] = {}
    discarded: list[dict] = []
    for m in modules:
        cands = [c for c in probe_commits if m in touches[c.sha]]
        share = {c.sha: touches[c.sha][m] / max(1, sum(touches[c.sha].values())) for c in cands}
        cands.sort(key=lambda c: (-share[c.sha], c.date))
        chosen, tried = [], 0
        for c in cands:
            if len(chosen) >= PROBES_PER_MODULE or tried >= MAX_TRIES_PER_MODULE:
                break
            tried += 1
            rec = verify_probe(repo, c, envs)
            print(f"{m:45} {c.sha[:9]} share={share[c.sha]:.2f} {rec['status']:9} {c.subject[:50]}", flush=True)
            if rec["status"] == "ok":
                pid = rec["probe"]["id"]
                probes[pid] = rec["probe"]
                chosen.append({"probe": pid, "commit": c.sha, "date": c.date, "subject": c.subject,
                               "module_share": round(share[c.sha], 3), "hidden": len(rec["probe"]["hidden"])})
            else:
                discarded.append({"module": m, "commit": c.sha, "subject": c.subject, "reason": rec["reason"]})
        per_module[m] = {"nonblank_lines_at_T": sizes[m], "candidate_commits": len(cands), "tried": tried,
                         "probes": chosen}

    out_start, out_end = probe_end, T_DATE + timedelta(days=OUTCOME_END_DAYS)
    later = log(repo, f"--since={(out_start - timedelta(days=60)).isoformat()}",
                f"--until={(out_end + timedelta(days=2)).isoformat()}", "HEAD", merges=False)
    later = [c for c in later if out_start < c.day <= out_end and c.files(is_source)]
    outs = outcomes(prov, later, kloc)
    unmapped = Counter(p for c in later for p in c.files(is_source)
                       if not (prov.module(c.parents[0], p) or prov.module(c.sha, p)))
    for m in modules:
        per_module[m]["outcomes"] = outs[m]

    for p in probes.values():
        register_env(p["env"], envs)
    OUT.write_text(json.dumps({
        "description": __doc__, "repo": SLUGS[REPO], "snapshot": {"sha": t_rev, "date": t_day.isoformat()},
        "probe_window": [T_DATE.isoformat(), probe_end.isoformat()],
        "outcome_window": [out_start.isoformat(), out_end.isoformat()],
        "bugfix_heuristic": {
            "rule": "a commit is a bug fix if its message matches `match` (unless its subject matches one of "
                    "`unless_subject_matches`), OR it adds a changelog entry under a patch-release heading "
                    "(X.Y.Z, Z > 0)",
            "match": BUGFIX.pattern, "unless_subject_matches": [NOT_BEHAVIOUR.pattern, NOISE.pattern]},
        "noise_heuristic": NOISE.pattern, "layout": lay,
        "outcome_commits_total": len(later),
        "outcome_source_paths_not_mapped_to_a_T_module": dict(unmapped.most_common()),
        "modules": per_module, "envs": envs, "probes": list(probes.values()), "discarded": discarded,
    }, indent=1))
    n_ok = sum(1 for v in per_module.values() if len(v["probes"]) >= PROBES_PER_MODULE)
    print(f"{len(modules)} modules, {n_ok} with {PROBES_PER_MODULE} probes, {len(probes)} probes -> {OUT}")


if __name__ == "__main__":
    main()
