"""Run a panel of extenders on a group of rollouts and turn their reading into one cost per rollout.

Flow for one change request and one group of rollouts (same task, different policy samples):
  1. selected(panel, group_id): which extenders score this group. Sampling is per group, so every
     rollout in a group faces exactly the same extenders.
  2. run_group(...): each selected extender x seed implements the change on each rollout's codebase.
  3. score_group(...): nodes_read_per_test per run (never-passing tests charged a per-extender ceiling of
     2x the group's median total reading), median over seeds, divided by that extender's group median
     (so each extender is a relative judge and no single model's scale dominates), then the weighted
     mean over extenders. ~1.0 = typical for the group; lower = cheaper to change.
"""

from __future__ import annotations

import hashlib
import shutil
import statistics as st
import subprocess
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from .config import ExtenderSpec, Panel
from .events import RunRecord
from .harnesses import REGISTRY
from .nodes import SKIP_DIRS
from .scoring import CachedGrader, GradeFn, cumulative_reading, nodes_read_per_test


def selected(panel: Panel, group_id: str) -> list[ExtenderSpec]:
    out = []
    for spec in panel.active:
        u = int(hashlib.sha256(f"{group_id}/{spec.id}".encode()).hexdigest()[:8], 16) / 0xFFFFFFFF
        if u < spec.sample_rate:
            out.append(spec)
    return out


class Budget:
    def __init__(self, total: float):
        self.total, self.spent, self.reserved, self.lock = total, 0.0, 0.0, threading.Lock()

    def acquire(self, amount: float) -> bool:
        with self.lock:
            if self.spent + self.reserved + amount > self.total:
                return False
            self.reserved += amount
            return True

    def release(self, amount: float, cost: float | None) -> None:
        with self.lock:
            self.reserved -= amount
            self.spent += cost if cost is not None else amount   # unknown cost: assume the cap was used


def prepare(base_dir: Path, workdir: Path) -> None:
    if workdir.exists():
        shutil.rmtree(workdir)
    shutil.copytree(base_dir, workdir, ignore=lambda _, names: [n for n in names if n in SKIP_DIRS])
    subprocess.run("git init -q && git add -A && git -c user.name=x -c user.email=x@x commit -qm base",
                   shell=True, cwd=workdir, check=True, capture_output=True)


def run_group(panel: Panel, group_id: str, codebases: dict[str, Path], change_spec: str, out_dir: Path,
              budget: Budget | None = None, prompt_vars: dict | None = None) -> dict[str, list[RunRecord]]:
    """codebases: rollout_id -> the policy's codebase. Returns rollout_id -> runs (all extenders x seeds)."""
    budget = budget or Budget(panel.total_budget_usd)
    prompt = panel.prompt_template.format(spec=change_spec, **{"run_hint": "", **(prompt_vars or {})})
    jobs = [(rid, spec, seed) for rid in codebases for spec in selected(panel, group_id) for seed in range(spec.seeds)]
    results: dict[str, list[RunRecord]] = {rid: [] for rid in codebases}

    def job(j):
        rid, spec, seed = j
        if not budget.acquire(spec.budget_usd):
            return None
        out = out_dir / rid / spec.id / f"s{seed}"
        rec = None
        try:
            prepare(codebases[rid], out / "code")
            rec = REGISTRY[spec.harness].run(spec, prompt, out / "code", out, seed)
            return rid, rec
        finally:
            budget.release(spec.budget_usd, rec.cost_usd if rec else 0.0)

    with ThreadPoolExecutor(panel.max_parallel) as ex:
        for res in ex.map(job, jobs):
            if res:
                results[res[0]].append(res[1])
    return results


def score_group(panel: Panel, runs: dict[str, list[RunRecord]], codebases: dict[str, Path], grade: GradeFn,
                tests: list[str], regression_base: int, ref_density: float) -> dict[str, dict]:
    """rollout_id -> {"cost": panel cost (~1 = group typical, lower is better), "by_extender": {...}}."""
    grader = CachedGrader(grade)
    weights = {s.id: s.weight for s in panel.extenders}
    by_ext: dict[str, list] = {}
    for rid, recs in runs.items():
        for r in recs:
            by_ext.setdefault(r.extender_id, []).append((rid, r))

    raw: dict[str, dict[str, float]] = {rid: {} for rid in runs}
    detail: dict[str, dict[str, list]] = {rid: {} for rid in runs}
    for ext, items in by_ext.items():
        ceiling = None
        if panel.fail_charge == "ceiling":
            totals = [cumulative_reading(r, codebases[rid], ref_density)[-1] for rid, r in items]
            ceiling = 2 * st.median(totals)
        per_rollout: dict[str, list[float]] = {}
        for rid, r in items:
            s = nodes_read_per_test(r, grader, tests, regression_base, codebases[rid], ref_density,
                                    fail_charge=ceiling, stable_regression=panel.stable_regression)
            per_rollout.setdefault(rid, []).append(s["nodes_read_per_test"])
            detail[rid].setdefault(ext, []).append(s)
        for rid, vals in per_rollout.items():
            raw[rid][ext] = st.median(vals)

    out = {}
    group_median = {ext: st.median(raw[rid][ext] for rid in raw if ext in raw[rid]) for ext in by_ext}
    for rid in runs:
        rel = {ext: v / group_median[ext] for ext, v in raw[rid].items() if group_median[ext] > 0}
        wsum = sum(weights[e] for e in rel)
        out[rid] = {"cost": sum(weights[e] * v for e, v in rel.items()) / wsum if wsum else None,
                    "by_extender": raw[rid], "detail": detail[rid]}
    return out
