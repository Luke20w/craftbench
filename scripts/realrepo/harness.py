"""Replay probes: a real commit from an open-source repo, replayed as a change request.

A probe is (repo, base, spec, hidden tests):
  * base    the tree the extender starts from: the commit's parent (or a synthetic variant of it,
            e.g. the parent with a refactor reverted). Its own tests are visible; the commit's are not.
  * spec    the commit message (+ PR / issue text where available).
  * hidden  pytest node ids the commit added or changed that FAIL on base and PASS on the commit.
  * grading copy the code, replace its test directories with the commit's (the commit's versions of
            the files it changed, the base's elsewhere), run the listed node ids with the repo's pytest.

Manifest (JSON):
  {"envs":   {name: {"python": path-relative-to-data-root, ...}},
   "probes": [{"id", "repo", "clone", "base", "commit", "oracle", "spec", "test_dirs", "pythonpath",
               "env", "hidden": [node ids], "regression": [node ids], "run": hint, "verification": {...}}]}
  `oracle` is a tree on which all hidden tests pass (the commit itself for an unmodified base).
  `regression` are visible-suite tests passing on base and on oracle (CraftBench's "old tests").
  Paths are relative to .context/realrepo (DATA).

    python scripts/realrepo/harness.py list    MANIFEST
    python scripts/realrepo/harness.py prepare MANIFEST PROBE_ID [DEST]
    python scripts/realrepo/harness.py grade   MANIFEST PROBE_ID CODE_DIR [--hidden-only]
    python scripts/realrepo/harness.py check   MANIFEST [PROBE_ID ...]   # base fails, oracle passes
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from envs import export_tree  # noqa: E402
from mine import DATA  # noqa: E402

COPY_IGNORE = shutil.ignore_patterns(".git", "__pycache__", ".pytest_cache", ".venv", ".tox", "node_modules",
                                     "*.egg-info", ".claude", ".mypy_cache")


@dataclass
class Probe:
    id: str
    repo: str                    # GitHub slug, e.g. "pallets/click"
    clone: str                   # local clone, relative to DATA
    base: str                    # sha of the tree the extender starts from (may be a synthetic commit)
    commit: str                  # the real commit replayed; its test dirs are the graded tests
    oracle: str | None           # sha of a tree implementing the change on this base (None: unknown)
    spec: str
    env: str                     # key into manifest["envs"]
    hidden: list[str]
    regression: list[str] = field(default_factory=list)
    test_dirs: list[str] = field(default_factory=lambda: ["tests"])
    pythonpath: list[str] = field(default_factory=lambda: ["src"])
    pytest_args: list[str] = field(default_factory=list)  # e.g. ["-m", "not dev_server"]
    run: str = ""                # how to run the visible tests, for the extender's prompt
    meta: dict = field(default_factory=dict)
    verification: dict = field(default_factory=dict)

    @classmethod
    def from_dict(cls, d: dict) -> "Probe":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Manifest:
    envs: dict[str, dict]
    probes: list[Probe]

    @classmethod
    def load(cls, path: str | Path) -> "Manifest":
        raw = json.loads(Path(path).read_text())
        return cls(raw.get("envs", {}), [Probe.from_dict(p) for p in raw["probes"]])

    def probe(self, probe_id: str) -> Probe:
        return next(p for p in self.probes if p.id == probe_id)

    def python(self, probe: Probe) -> Path:
        return DATA / self.envs[probe.env]["python"]

    def save(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps({"envs": self.envs, "probes": [p.to_dict() for p in self.probes]},
                                         indent=1))


# --- workspaces ---------------------------------------------------------------------------------

def prepare(probe: Probe, dest: str | Path | None = None) -> Path:
    """A fresh workspace with the base tree (no .git, no hidden tests). Returns its path."""
    dest = Path(dest) if dest else DATA / "workspaces" / probe.id / "code"
    if dest.exists():
        shutil.rmtree(dest)
    return export_tree(DATA / probe.clone, probe.base, dest)


def test_tree(probe: Probe) -> Path:
    """The graded test directories (the commit's), materialized once per commit."""
    out = DATA / "test_trees" / f"{Path(probe.clone).name}-{probe.commit[:12]}"
    if not (out / ".done").exists():
        shutil.rmtree(out, ignore_errors=True)
        with tempfile.TemporaryDirectory() as tmp:
            tree = export_tree(DATA / probe.clone, probe.commit, Path(tmp))
            for d in probe.test_dirs:
                if (tree / d).is_dir():
                    shutil.copytree(tree / d, out / d)
                elif (tree / d).is_file():
                    (out / d).parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(tree / d, out / d)
        (out / ".done").touch()
    return out


def overlay_tests(probe: Probe, ws: Path) -> None:
    """Replace the workspace's test dirs (which an extender may have edited) with the graded ones."""
    src = test_tree(probe)
    for d in probe.test_dirs:
        target = ws / d
        if target.is_dir():
            shutil.rmtree(target)
        elif target.exists():
            target.unlink()
        if (src / d).is_dir():
            shutil.copytree(src / d, target)
        elif (src / d).is_file():
            shutil.copy2(src / d, target)


# --- running tests ------------------------------------------------------------------------------

LAST_OUTPUT: dict[str, str] = {}  # tail of the last pytest run's output, for diagnosing crashes


def run_pytest(python: Path, ws: Path, targets: list[str], pythonpath: list[str], timeout: int = 900,
               extra: tuple[str, ...] = ()) -> dict[str, str]:
    """Run pytest in ws on targets (files or node ids); {node id: outcome}. Empty if it crashed."""
    out = Path(tempfile.mkstemp(suffix=".json")[1])
    ws = ws.resolve()  # /tmp and /var are symlinks on macOS; pytest node ids need one spelling
    env = {k: v for k, v in os.environ.items() if not k.startswith(("PYTHON", "PYTEST", "VIRTUAL_ENV", "COV_"))}
    env |= {"PYTHONPATH": os.pathsep.join([*(str(ws / p) for p in pythonpath), str(HERE)]),
            "PYTHONDONTWRITEBYTECODE": "1", "PYTHONHASHSEED": "0", "NO_COLOR": "1", "TERM": "dumb"}
    if len(" ".join(targets)) > 100_000:  # too long for a command line: run their files instead
        targets = sorted({t.split("::")[0] for t in targets})
    cmd = [str(python), "-m", "pytest", "-q", "-p", "no:cacheprovider", "-p", "realrepo_report",
           f"--realrepo-out={out}", "--rootdir=.", "-o", "console_output_style=classic",
           "--no-cov", "--continue-on-collection-errors", *extra, *targets]
    try:
        r = subprocess.run(cmd, cwd=ws, env=env, capture_output=True, text=True, timeout=timeout)
        LAST_OUTPUT["tail"] = (r.stdout + r.stderr)[-2000:]
        return json.loads(out.read_text() or "{}")
    except (subprocess.TimeoutExpired, json.JSONDecodeError) as e:
        LAST_OUTPUT["tail"] = repr(e)
        return {}
    finally:
        out.unlink(missing_ok=True)


def grade(probe: Probe, code_dir: str | Path, python: Path | None = None, regression: bool = True,
          timeout: int = 900) -> set[str]:
    """Node ids (hidden, plus regression unless regression=False) that pass on code_dir, which can be
    any snapshot of a workspace. code_dir is not modified."""
    python = python or _default_manifest_python(probe)
    with tempfile.TemporaryDirectory(prefix="rr-grade-") as tmp:
        ws = Path(tmp) / "code"
        shutil.copytree(code_dir, ws, ignore=COPY_IGNORE, symlinks=True)
        overlay_tests(probe, ws)
        wanted = set(probe.hidden) | (set(probe.regression) if regression else set())
        targets = sorted({t.split("::")[0] for t in wanted}) if regression else sorted(probe.hidden)
        outcomes = run_pytest(python, ws, targets, probe.pythonpath, timeout, tuple(probe.pytest_args))
    return {t for t, o in outcomes.items() if o == "passed" and t in wanted}


_MANIFEST_CACHE: dict[str, dict] = {}


def _default_manifest_python(probe: Probe) -> Path:
    """Find the env's python when grade() is called without one: look in every manifest in DATA."""
    if not _MANIFEST_CACHE:
        for m in DATA.glob("*.json"):
            try:
                _MANIFEST_CACHE.update(json.loads(m.read_text()).get("envs", {}))
            except (json.JSONDecodeError, AttributeError):
                pass
    return DATA / _MANIFEST_CACHE[probe.env]["python"]


def check(manifest: Manifest, probe: Probe) -> dict:
    """Re-verify a probe from scratch: no hidden test passes on base, all pass on the oracle."""
    py = manifest.python(probe)
    with tempfile.TemporaryDirectory() as tmp:
        t0 = time.time()
        base = grade(probe, prepare(probe, Path(tmp) / "base"), py)
        secs = time.time() - t0
        res = {"id": probe.id, "hidden": len(probe.hidden), "hidden_on_base": len(base & set(probe.hidden)),
               "regression": len(probe.regression), "regression_on_base": len(base & set(probe.regression)),
               "grade_seconds": round(secs, 1)}
        if probe.oracle:
            oracle_dir = export_tree(DATA / probe.clone, probe.oracle, Path(tmp) / "oracle")
            ora = grade(probe, oracle_dir, py)
            res |= {"hidden_on_oracle": len(ora & set(probe.hidden)),
                    "regression_on_oracle": len(ora & set(probe.regression))}
    res["ok"] = res["hidden_on_base"] == 0 and res.get("hidden_on_oracle", res["hidden"]) == res["hidden"]
    return res


def main(argv: list[str]) -> None:
    cmd, mpath, *rest = argv
    m = Manifest.load(mpath)
    if cmd == "list":
        for p in m.probes:
            print(f"{p.id:48} hidden={len(p.hidden):3} regression={len(p.regression):5}  {p.spec.splitlines()[0][:70]}")
    elif cmd == "prepare":
        print(prepare(m.probe(rest[0]), rest[1] if len(rest) > 1 else None))
    elif cmd == "grade":
        p = m.probe(rest[0])
        passed = grade(p, rest[1], m.python(p), regression="--hidden-only" not in rest)
        print(json.dumps({"hidden_passed": sorted(passed & set(p.hidden)), "hidden_total": len(p.hidden),
                          "regression_passed": len(passed & set(p.regression)),
                          "regression_total": len(p.regression)}, indent=1))
    elif cmd == "check":
        ids = rest or [p.id for p in m.probes]
        for i in ids:
            print(json.dumps(check(m, m.probe(i))), flush=True)
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
