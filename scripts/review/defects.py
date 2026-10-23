"""Defects introduced by maintenance: an answer key for what code costs to own that isn't reading.

After each step k of every chained maintenance run (scripts/v_measures, `chain`), run the fuzz requests through
the maintained code and through the reference after step k (chain_reference/h<k>). A defect is a request the
starting code answered like the starting reference but the maintained code now answers differently from the
reference after step k (exit code, error code, path or data; message text is ignored). Requests the starting
code already answered differently are behaviour the specs left open.

    python scripts/review/defects.py <cases.jsonl> [parallel]     # writes defects.json next to the runs
"""
from __future__ import annotations

import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/v_measures"))
import run as vm  # noqa: E402
from craftbench.sandbox import tree_digest  # noqa: E402

DRIVER = Path(__file__).resolve().parent / "fuzz" / "driver.py"
CACHE = vm.OUT.parent / "defects_cache"


def strip_messages(v):
    if isinstance(v, dict):
        return {k: strip_messages(x) for k, x in v.items() if k != "message"}
    if isinstance(v, list):
        return [strip_messages(x) for x in v]
    return v


def answers(code: Path, cases: Path) -> list:
    """The code's answer to every request (cached by the code's contents)."""
    out = CACHE / f"{tree_digest(code)}_{cases.stem}.jsonl"
    if not out.exists():
        CACHE.mkdir(parents=True, exist_ok=True)
        tmp = out.with_suffix(".tmp")
        subprocess.run([sys.executable, str(DRIVER), str(code), str(cases), str(tmp)], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        tmp.rename(out)
    rows = []
    for line in out.read_text().splitlines():
        exit_code, stdout = json.loads(line)
        try:
            rows.append(json.dumps([exit_code, strip_messages(json.loads(stdout))], sort_keys=True))
        except json.JSONDecodeError:
            rows.append(json.dumps([exit_code, stdout]))
    return rows


def main():
    cases, par = Path(sys.argv[1]).resolve(), int(sys.argv[2]) if len(sys.argv) > 2 else 4
    refs = [vm.TASK.reference] + [vm.TASK.root / "chain_reference" / h.id.split("_")[0] for h in vm.TASK.held_out]
    starts = {n: p for n, p in vm.codebases().items() if not n.startswith(("x_", "bon", "redteam"))}
    chains = {(n, m.name, r.name): [r / f"{k + 1}_{h.id}" / "code" for k, h in enumerate(vm.TASK.held_out)]
              for n in starts for m in sorted((vm.OUT / vm.slug(n) / "chain").glob("*"))
              for r in sorted(m.glob("run_*")) if (r / f"4_{vm.TASK.held_out[-1].id}" / "result.json").exists()}
    codes = refs + list(starts.values()) + [c for steps in chains.values() for c in steps]
    digest = {str(c): tree_digest(c) for c in codes}
    unique = {digest[str(c)]: c for c in codes}  # identical code (e.g. a step that changed nothing) runs once
    with ThreadPoolExecutor(par) as ex:
        by_digest = dict(zip(unique, ex.map(lambda c: answers(c, cases), unique.values())))
    got = {c: by_digest[d] for c, d in digest.items()}
    ref = [got[str(p)] for p in refs]
    result = {}
    for (n, model, run), steps in chains.items():
        start = got[str(starts[n])]
        agreed = [i for i in range(len(start)) if start[i] == ref[0][i]]
        rates = [sum(got[str(c)][i] != ref[k + 1][i] for i in agreed) / len(agreed) for k, c in enumerate(steps)]
        result.setdefault(n, []).append({"maintainer": model, "run": run, "agreed": len(agreed), "defects": rates})
        print(n, model, run, len(agreed), [f"{x:.3%}" for x in rates], flush=True)
    (vm.OUT / "defects.json").write_text(json.dumps(result, indent=1))


if __name__ == "__main__":
    main()
