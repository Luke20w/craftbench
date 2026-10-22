"""Dataset 1: expert refactorings R, each with later real feature/fix commits F replayed on two bases.

  after  = F's parent (the refactored code, as history had it)
  before = F's parent with R reverted (clean revert; conflicts only in non-Python files are resolved by
           keeping F's parent's version)

Checks, all recorded:
  * R is behaviour-preserving: R's own test suite passes identically on R's parent and on R
    (R changes no test files).
  * on `before`, every visible test passing on `after` still passes.
  * hidden tests of F fail on both bases and pass on both oracles: F itself for `after`, and F with
    R reverted for `before` (when that reverts cleanly; otherwise "before_oracle": null and the before
    side is only checked to fail).
  * the hidden set used for BOTH probes is the intersection, so the two probes are graded identically.

    python scripts/realrepo/build_refactor_pairs.py [--only REPO]   # resumable; writes refactor_pairs.json
"""

from __future__ import annotations

import json
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from envs import env_name, make_env  # noqa: E402
from harness import LAST_OUTPUT, Probe  # noqa: E402
from mine import DATA, REPOS, commit, git, is_source  # noqa: E402
from replay import discover, passed, pick_onto, quick_hidden, revert_onto, run_tree, spec_for  # noqa: E402

CACHE = DATA / "cache" / "pairs"
OUT = DATA / "refactor_pairs.json"

SLUGS = {"click": "pallets/click", "jinja": "pallets/jinja", "werkzeug": "pallets/werkzeug",
         "flask": "pallets/flask", "itsdangerous": "pallets/itsdangerous", "marshmallow": "marshmallow-code/marshmallow",
         "attrs": "python-attrs/attrs", "more-itertools": "more-itertools/more-itertools", "arrow": "arrow-py/arrow",
         "packaging": "pypa/packaging", "pluggy": "pytest-dev/pluggy", "boltons": "mahmoud/boltons",
         "pyparsing": "pyparsing/pyparsing", "tomlkit": "python-poetry/tomlkit", "loguru": "Delgan/loguru",
         "humanize": "python-humanize/humanize", "sqlparse": "andialbrecht/sqlparse", "toolz": "pytoolz/toolz",
         "tenacity": "jd/tenacity", "filelock": "tox-dev/filelock", "wtforms": "pallets-eco/wtforms",
         "markupsafe": "pallets/markupsafe"}

# Per-repo pytest arguments: skip tests that start servers or need the network.
PYTEST_ARGS = {"werkzeug": ["-m", "not dev_server"], "flask": [], "arrow": []}

# Curated candidates: (repo, refactor commit, follow-up commits). Follow-ups were mined by
# candidates.py: later commits within 183 days that change lines the refactor wrote (git blame) and
# change both source and tests. See refactor_pairs.json "discarded" for what didn't verify.
CANDIDATES: list[tuple[str, str, list[str]]] = json.loads((DATA / "refactor_candidates.json").read_text()) \
    if (DATA / "refactor_candidates.json").exists() else []


def layout(repo: Path, rev: str) -> dict:
    names = set(git(repo, "ls-tree", "--name-only", rev).split())
    test_dirs = [d for d in ("tests", "test", "testing") if d in names]
    if "conftest.py" in names:
        test_dirs.append("conftest.py")
    return {"pythonpath": ["src"] if "src" in names else ["."], "test_dirs": test_dirs}


MANUAL = DATA / "manual_oracles.json"


def manual_oracle(repo: Path, r_sha: str, f_sha: str) -> str | None:
    """A hand-made `before` oracle: F's change ported onto F^-with-R-reverted where git couldn't apply
    it (conflicts resolved by hand, behaviour only, no test changes). Keyed "repo:R12:F12"."""
    table = json.loads(MANUAL.read_text()) if MANUAL.exists() else {}
    full = lambda x: git(repo, "rev-parse", x).strip()[:12]  # noqa: E731
    sha = table.get(f"{repo.name}:{full(r_sha)}:{full(f_sha)}")
    if not sha:
        return None
    return git(repo, "rev-parse", sha).strip()


def env_for(repo: Path, rev: str, envs: dict) -> tuple[str, Path]:
    name = env_name(repo, rev)
    py = make_env(name, repo, rev)
    register_env(name, envs)
    return name, py


def register_env(name: str, envs: dict) -> None:
    """Manifest entry for an existing env (also for probes that came from the cache)."""
    ready = (DATA / "envs" / name / ".ready").read_text().strip()
    envs[name] = {"python": f"envs/{name}/bin/python", "repo": ready.split()[0], "rev": ready.split()[1],
                  "info": ready}


def run_hint(p: Probe) -> str:
    pp = ":".join(p.pythonpath)
    dirs = " ".join(d for d in p.test_dirs if d != "conftest.py")
    return f"PYTHONPATH={pp} {{python}} -m pytest {dirs} {' '.join(p.pytest_args)}".strip()


def check_refactor(repo: Path, r_sha: str, envs: dict) -> dict:
    """R's suite passes the same on R's parent and on R."""
    f = CACHE / f"R-{repo.name}-{r_sha[:12]}.json"
    if f.exists():
        return json.loads(f.read_text())
    r = commit(repo, r_sha)
    parent = r.parents[0]
    env, py = env_for(repo, parent, envs)
    lay = layout(repo, r.sha)
    p = Probe(id="R", repo=SLUGS[repo.name], clone=f"repos/{repo.name}", base=parent, commit=r.sha,
              oracle=r.sha, spec="", env=env, hidden=[], pytest_args=PYTEST_ARGS.get(repo.name, []), **lay)
    on_parent, _ = run_tree(py, repo, parent, p)  # parent's code, R's tests (= parent's tests)
    on_r, _ = run_tree(py, repo, r.sha, p)
    test_files_changed = [x for x in r.numstat if not is_source(x) and x.split("/")[0] in lay["test_dirs"]]
    rec = {"sha": r.sha, "date": r.date, "author": r.author, "title": r.title, "message": r.message,
           "merge": r.is_merge, "source_lines_changed": r.churn(is_source),
           "source_files": r.files(is_source), "test_files_changed": test_files_changed,
           "suite_on_parent": {"collected": len(on_parent), "passed": len(passed(on_parent))},
           "suite_on_refactor": {"collected": len(on_r), "passed": len(passed(on_r))},
           # ids collected in only one run (e.g. parametrized with the current time) can't be compared
           "ids_not_in_both_runs": len(set(on_parent) ^ set(on_r)),
           "pass_only_on_parent": sorted((passed(on_parent) - passed(on_r)) & set(on_r)),
           "pass_only_on_refactor": sorted((passed(on_r) - passed(on_parent)) & set(on_parent)), "env": env}
    if not on_r:
        rec["pytest_output_tail"] = LAST_OUTPUT.get("tail", "")
    rec["behaviour_preserving"] = (not test_files_changed and not rec["pass_only_on_parent"]
                                   and not rec["pass_only_on_refactor"] and len(passed(on_r)) > 0)
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(rec, indent=1))
    return rec


def build_pair(repo: Path, r_sha: str, f_sha: str, envs: dict) -> dict:
    """Both probes for one follow-up F, or a discard record with the reason."""
    cache = CACHE / f"F-{repo.name}-{r_sha[:12]}-{f_sha[:12]}.json"
    manual = manual_oracle(repo, r_sha, f_sha)
    if cache.exists():
        rec = json.loads(cache.read_text())
        if not manual or manual in rec.get("before_oracle_revert", ""):
            return rec
    rec = _build_pair(repo, r_sha, f_sha, envs)
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(rec, indent=1))
    return rec


def _build_pair(repo: Path, r_sha: str, f_sha: str, envs: dict) -> dict:
    r, f = commit(repo, r_sha), commit(repo, f_sha)
    parent = f.parents[0]
    out = {"commit": f.sha, "date": f.date, "author": f.author, "subject": f.subject}
    env, py = env_for(repo, parent, envs)
    lay = layout(repo, f.sha)
    common = dict(repo=SLUGS[repo.name], clone=f"repos/{repo.name}", commit=f.sha, spec="", env=env, hidden=[],
                  pytest_args=PYTEST_ARGS.get(repo.name, []), **lay)
    after = Probe(id=f"{repo.name}-{r.sha[:8]}-{f.sha[:8]}-after", base=parent, oracle=f.sha, **common)
    quick = quick_hidden(py, after)
    if not quick:
        return out | {"status": "discarded", "reason": "no test in F's changed test files fails on F^ and passes on F"}
    before_base, note = revert_onto(repo, parent, r, f"{r.sha[:12]}-on-{parent[:12]}")
    if not before_base:
        return out | {"status": "discarded", "reason": f"refactor does not revert cleanly on F^ ({note})"}
    before_oracle, note_o = revert_onto(repo, f.sha, r, f"{r.sha[:12]}-on-{f.sha[:12]}")
    if not before_oracle:  # second route to an oracle: F's own diff applied to the before base
        before_oracle, note_p = pick_onto(repo, before_base, f, f"{f.sha[:12]}-onto-{before_base[:12]}")
        note_o = f"revert of R on F: {note_o}; F cherry-picked onto before: {note_p}"
    if not before_oracle and manual_oracle(repo, r.sha, f.sha):  # third: F ported to the before base by hand
        before_oracle = manual_oracle(repo, r.sha, f.sha)
        note_o = f"hand-ported F onto the before base: {before_oracle} (refs/realrepo/manual/...); {note_o}"
    rec_a = discover(py, after)
    vis_a = rec_a.pop("_visible_passed")
    if not after.hidden:
        return out | {"status": "discarded", "reason": "no stable hidden test after full verification",
                      "after": rec_a}
    before = Probe(id=f"{repo.name}-{r.sha[:8]}-{f.sha[:8]}-before", base=before_base, oracle=before_oracle,
                   **common)
    rec_b = discover(py, before, candidates=after.hidden)
    vis_b = rec_b.pop("_visible_passed")
    lost = sorted(vis_a - vis_b)
    rec_b["visible_tests_passing_on_after_but_not_before"] = lost
    hidden = sorted(set(after.hidden) & set(before.hidden))
    out |= {"revert": note, "before_oracle_revert": note_o if before_oracle else f"none ({note_o})",
            "verification_after": rec_a, "verification_before": rec_b,
            "hidden_after_only": sorted(set(after.hidden) - set(hidden)),
            "hidden_before_only": sorted(set(before.hidden) - set(hidden))}
    if lost:
        return out | {"status": "discarded", "reason": f"{len(lost)} visible tests pass on after but not before"}
    if not hidden:
        return out | {"status": "discarded", "reason": "no hidden test common to both bases"}
    spec, meta = spec_for(repo, SLUGS[repo.name], f)
    for p in (after, before):
        p.hidden = hidden
        p.regression = sorted(set(p.regression) - set(hidden))
        p.spec = spec
        p.meta = {"spec_sources": meta, "refactor": r.sha, "variant": p.id.rsplit("-", 1)[1]}
        p.run = run_hint(p)
    diff = git(repo, "diff", "--shortstat", before_base, parent)
    return out | {"status": "ok", "hidden": hidden, "base_diff_after_vs_before": diff.strip(),
                  "probes": [after.to_dict(), before.to_dict()]}


def main(argv: list[str]) -> None:
    only = argv[argv.index("--only") + 1] if "--only" in argv else None
    envs: dict = {}
    pairs, probes, discarded = [], [], []
    for repo_name, r_sha, f_shas in CANDIDATES:
        if only and repo_name != only:
            continue
        repo = REPOS / repo_name
        try:
            rr = check_refactor(repo, r_sha, envs)
        except Exception as e:  # noqa: BLE001 - record and move on
            discarded.append({"repo": repo_name, "refactor": r_sha, "reason": f"refactor check crashed: {e}"})
            traceback.print_exc()
            continue
        print(f"R {repo_name} {r_sha[:9]} preserving={rr['behaviour_preserving']} {rr['title'][:60]}", flush=True)
        if not rr["behaviour_preserving"]:
            discarded.append({"repo": repo_name, "refactor": r_sha, "reason": "refactor changes test outcomes or tests",
                              "check": {k: rr[k] for k in ("suite_on_parent", "suite_on_refactor",
                                                           "pass_only_on_parent", "pass_only_on_refactor",
                                                           "test_files_changed")}})
            continue
        followups = []
        for f_sha in f_shas:
            try:
                fr = build_pair(repo, r_sha, f_sha, envs)
            except Exception as e:  # noqa: BLE001
                traceback.print_exc()
                fr = {"commit": f_sha, "status": "discarded", "reason": f"crashed: {e}"}
            print(f"   F {f_sha[:9]} {fr['status']} {fr.get('reason', '')} hidden={len(fr.get('hidden', []))}",
                  flush=True)
            if fr["status"] == "ok":
                followups.append({k: v for k, v in fr.items() if k != "probes"} |
                                 {"probe_after": fr["probes"][0]["id"], "probe_before": fr["probes"][1]["id"]})
                probes += fr["probes"]
            else:
                discarded.append({"repo": repo_name, "refactor": r_sha, "followup": f_sha, **fr})
        entry = {"repo": SLUGS[repo_name], "refactor": rr, "followups": followups}
        (pairs if followups else discarded).append(entry if followups else
                                                   {"repo": repo_name, "refactor": r_sha,
                                                    "reason": "no follow-up verified"})
    for p in probes:
        register_env(p["env"], envs)
    out = OUT.with_name(f"refactor_pairs.{only}.json") if only else OUT  # --only never clobbers the full set
    out.write_text(json.dumps({"description": __doc__, "envs": envs, "pairs": pairs, "probes": probes,
                               "discarded": discarded}, indent=1))
    print(f"{len(pairs)} refactors, {len(probes)} probes, {len(discarded)} discards -> {out}")


if __name__ == "__main__":
    main(sys.argv[1:])
