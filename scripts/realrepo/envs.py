"""Per-repo virtualenvs for running a repo's own pytest at a historical commit.

The env holds the repo's test and runtime dependencies as of that commit (uv --exclude-newer), but
NOT the package itself: tests import the package from the directory being graded (PYTHONPATH), so
an extender's edits take effect. The package's dist-info is kept so importlib.metadata still works."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tarfile
import tempfile
import tomllib
from datetime import date, timedelta
from pathlib import Path

from mine import DATA, git

UV = DATA / "tools" / "bin" / "uv"
ENVS = DATA / "envs"
PYTHONS = DATA / "pythons"


def python_for(day: date) -> str:
    """A CPython the code of that day was tested on."""
    return "3.9" if day < date(2021, 10, 1) else "3.10" if day < date(2022, 10, 1) else \
        "3.11" if day < date(2023, 10, 1) else "3.12"


def _uv(*args: str, version: str = "0.0.0", **kw) -> subprocess.CompletedProcess:
    # builds from a git archive have no .git: tell setuptools-scm / hatch-vcs the version instead
    env = {**os.environ, "UV_PYTHON_INSTALL_DIR": str(PYTHONS), "UV_CACHE_DIR": str(DATA / "uv-cache"),
           "SETUPTOOLS_SCM_PRETEND_VERSION": version}
    return subprocess.run([str(UV), *args], capture_output=True, text=True, env=env, **kw)


def export_tree(repo: Path, rev: str, dest: Path) -> Path:
    """The files of `rev` (no .git) into dest."""
    dest.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryFile() as f:
        subprocess.run(["git", "-C", str(repo), "archive", "--format=tar", rev], stdout=f, check=True)
        f.seek(0)
        with tarfile.open(fileobj=f) as t:
            t.extractall(dest, filter="tar")
    return dest


def _requirements(tree: Path) -> tuple[list[str], list[str]]:
    """(requirement strings, requirement files) for the tests, as declared at this commit."""
    names = ["requirements/tests.txt", "requirements/testing.txt", "requirements/test.txt", "requirements-test.txt",
             "requirements-tests.txt", "test-requirements.txt", "tests/requirements.txt"]
    files = [str(tree / n) for n in names if (tree / n).exists()]
    if not files:  # fall back to the dev requirements (may include docs tools; harmless)
        files = [str(tree / n) for n in ("requirements-dev.txt", "requirements/dev.txt", "dev-requirements.txt")
                 if (tree / n).exists()][:1]
    # pytest-cov is always installed so the grader can pass --no-cov whatever the repo's addopts say
    reqs: list[str] = ["pytest", "pytest-cov"]
    py = tree / "pyproject.toml"
    if py.exists():
        cfg = tomllib.loads(py.read_text())
        groups = cfg.get("dependency-groups", {})
        extras = cfg.get("project", {}).get("optional-dependencies", {})
        for table in (groups, extras):
            for name in ("tests", "test", "testing"):
                for r in table.get(name, []):
                    if isinstance(r, str):
                        reqs.append(r)
                    elif isinstance(r, dict) and "include-group" in r:
                        reqs += [x for x in groups.get(r["include-group"], []) if isinstance(x, str)]
    reqs += _tox_deps(tree)
    tox = tree / "tox.ini"
    if tox.exists():
        for m in re.finditer(r"^\s*-r\s*(?:\{toxinidir\}/)?(\S+)", tox.read_text(), re.M):
            if (tree / m.group(1)).is_file() and str(tree / m.group(1)) not in files:
                files.append(str(tree / m.group(1)))
    return reqs, files


def _tox_deps(tree: Path) -> list[str]:
    """`deps` of tox.ini's [testenv] (older projects declare test requirements only there)."""
    import configparser
    tox = tree / "tox.ini"
    if not tox.exists():
        return []
    cp = configparser.ConfigParser(interpolation=None)
    try:
        cp.read_string(tox.read_text())
    except configparser.Error:
        return []
    raw = cp.get("testenv", "deps", fallback="")
    out = []
    for ln in raw.splitlines():
        ln = ln.split("#")[0].strip()
        if ln.startswith("-r"):  # requirement files are installed best-effort by make_env (old pins may not build)
            continue
        elif ln and "{" not in ln and not ln.startswith("-") and not re.match(r"^[\w,!-]+:\s", ln):
            out.append(ln)  # factor-conditional deps ("coverage: coverage") belong to other tox envs
    return out


def env_name(repo: Path, rev: str) -> str:
    """Envs are shared between commits that declare the same test requirements: the name is the
    python version plus a digest of the requirement inputs at `rev` (pinned requirement files; else
    the packaging metadata, plus the month, since unpinned requirements resolve by date)."""
    import hashlib
    day = date.fromisoformat(git(repo, "log", "-1", "--format=%cs", rev).strip())
    names = set(git(repo, "ls-tree", "-r", "--name-only", rev).split())
    pinned = sorted(n for n in names if re.fullmatch(r"(requirements/(tests?|testing|dev)\.txt|requirements-(tests?|dev)\.txt|"
                                                  r"(test|dev)-requirements\.txt|tests/requirements\.txt)", n))
    h = hashlib.md5()
    for n in pinned:
        h.update(git(repo, "show", f"{rev}:{n}").encode())
    if not pinned:
        for n in ("pyproject.toml", "setup.py", "setup.cfg", "tox.ini"):
            if n in names:
                text = git(repo, "show", f"{rev}:{n}")
                if n == "pyproject.toml":  # only the dependency tables, not versions or tool config
                    cfg = tomllib.loads(text)
                    text = json.dumps([cfg.get("project", {}).get("dependencies"),
                                       cfg.get("project", {}).get("optional-dependencies"),
                                       cfg.get("dependency-groups"), cfg.get("build-system")], sort_keys=True)
                h.update(text.encode())
        h.update(day.isoformat()[:7].encode())
    return f"{repo.name}-py{python_for(day)}-{h.hexdigest()[:8]}"


def make_env(name: str, repo: Path, rev: str, extra: list[str] = (), python: str | None = None,
             exclude_newer: str | None = None) -> Path:
    """Create (once) the env `name` for testing `repo` at `rev`; returns its python."""
    env_dir = ENVS / name
    py = env_dir / "bin" / "python"
    if (env_dir / ".ready").exists():
        return py
    day = date.fromisoformat(git(repo, "log", "-1", "--format=%cs", rev).strip())
    python = python or python_for(day)
    exclude_newer = exclude_newer or (day + timedelta(days=14)).isoformat()
    shutil.rmtree(env_dir, ignore_errors=True)
    r = _uv("venv", "-q", "--python", python, str(env_dir))
    if r.returncode:
        raise RuntimeError(r.stderr)
    with tempfile.TemporaryDirectory() as tmp:
        tree = export_tree(repo, rev, Path(tmp) / "tree")
        reqs, files = _requirements(tree)
        extras = _setup_extra(tree)
        base = ["pip", "install", "-q", "--python", str(py), "--exclude-newer", exclude_newer]
        version = (git(repo, "describe", "--tags", "--abbrev=0", rev, check=False).strip().lstrip("v")
                   or "0.0.0")
        for f in files:  # pinned requirement files are best effort: old pins may not build any more
            _uv(*base, "-r", f)
        # Build the project's wheel with current build tools (old backends often don't run on this
        # python), then resolve everything else as of the commit's date.
        wheels = Path(tmp) / "wheels"
        b = _uv("build", "-q", "--wheel", "--python", python, "--out-dir", str(wheels), str(tree), version=version)
        built = sorted(wheels.glob("*.whl")) if b.returncode == 0 else []
        target = f"{built[0]}{extras}" if built else f"{tree}{extras}"
        r = _uv(*base, target, *reqs, *extra, version=version)
        note = ""
        if r.returncode:  # the project itself didn't build with era-appropriate build tools:
            # install only its declared runtime and test requirements (no project metadata then)
            r2 = _uv(*base, *reqs, *_runtime_deps(tree), *extra)
            if r2.returncode:
                raise RuntimeError(f"installing {name}: {r.stderr[-1500:]}\n--- fallback: {r2.stderr[-1500:]}")
            note = " project_not_built=1"
        else:
            _strip_package(py, tree)
    (env_dir / ".ready").write_text(f"{repo.name} {rev} python={python} exclude_newer={exclude_newer}{note}\n")
    return py


def _runtime_deps(tree: Path) -> list[str]:
    """install_requires / project.dependencies, read without building the project."""
    py = tree / "pyproject.toml"
    if py.exists():
        deps = tomllib.loads(py.read_text()).get("project", {}).get("dependencies")
        if deps:
            return list(deps)
    text = "".join((tree / f).read_text() for f in ("setup.py", "setup.cfg") if (tree / f).exists())
    m = re.search(r"install_requires\s*=\s*\[([^\]]*)\]", text)
    if m:
        return re.findall(r"""["']([^"']+)["']""", m.group(1))
    m = re.search(r"install_requires\s*=\s*\n((?:[ \t]+\S.*\n)+)", text)  # setup.cfg
    return [x.strip() for x in m.group(1).splitlines() if x.strip()] if m else []


def _setup_extra(tree: Path) -> str:
    """'[tests]' (or test/testing) when setup.py/setup.cfg declares that extra."""
    text = "".join((tree / f).read_text() for f in ("setup.py", "setup.cfg") if (tree / f).exists())
    if "extras_require" not in text:
        return ""
    for name in ("tests", "test", "testing"):
        if f'"{name}"' in text or f"'{name}'" in text or f"\n{name} =" in text or f"\n{name}=" in text:
            return f"[{name}]"
    return ""


def _strip_package(py: Path, tree: Path) -> None:
    """Uninstall the project itself but keep its metadata (version lookups, entry points)."""
    site = Path(subprocess.run([str(py), "-c", "import sysconfig;print(sysconfig.get_paths()['purelib'])"],
                               capture_output=True, text=True, check=True).stdout.strip())
    name = _project_name(tree)
    norm = name.lower().replace("-", "_").replace(".", "_")
    infos = [p for p in site.glob("*.dist-info") if p.name.lower().split("-")[0] == norm]
    keep = []
    for info in infos:
        dst = Path(tempfile.mkdtemp()) / info.name
        shutil.copytree(info, dst)
        keep.append(dst)
    _uv("pip", "uninstall", "-q", "--python", str(py), name)
    for src in keep:
        dst = site / src.name
        shutil.copytree(src, dst, dirs_exist_ok=True)
        for junk in ("RECORD", "direct_url.json", "INSTALLER"):
            (dst / junk).unlink(missing_ok=True)


def _project_name(tree: Path) -> str:
    py = tree / "pyproject.toml"
    if py.exists():
        name = tomllib.loads(py.read_text()).get("project", {}).get("name")
        if name:
            return name
    for f in ("setup.cfg", "setup.py"):
        p = tree / f
        if p.exists():
            import re
            m = re.search(r"""name\s*[=:]\s*['"]?([A-Za-z0-9_.-]+)""", p.read_text())
            if m:
                return m.group(1)
    raise RuntimeError(f"no project name in {tree}")
