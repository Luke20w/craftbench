"""How much of the spread in V between codebases is real, and how much is one measurement's noise?

A measurement = geomean over the probe changes (and readers) of one run each. Replicate k uses run k of every
cell. Noise variance comes from replicate differences; between-codebase variance from the replicate means.
"""
import math, statistics as st, sys
from collections import defaultdict
sys.path.insert(0, __file__.rsplit("/", 1)[0])
from load import load

ROWS = load()
OPUS, SONNET = "claude-opus-5-5", "claude-sonnet-5-5"
cell = defaultdict(dict)  # (cb, kind, change, model) -> run -> effort
for r in ROWS:
    cell[(r["cb"], r["kind"], r["change"], r["model"])][r["run"]] = r["effort"]

def replicates(cb, kind, models, changes=None):
    """log V per replicate k, only where every (change, model) cell has run k."""
    cells = [v for (c, k, ch, m), v in cell.items() if c == cb and k == kind and m in models
             and (changes is None or ch in changes)]
    if not cells:
        return []
    ks = sorted(set.intersection(*(set(v) for v in cells)))
    return [st.mean(math.log(max(v[k], 1)) for v in cells) for k in ks]

def decompose(label, cbs, kind, models, changes=None):
    reps = {cb: replicates(cb, kind, models, changes) for cb in cbs}
    reps = {cb: r for cb, r in reps.items() if len(r) >= 1}
    paired = [r[:2] for r in reps.values() if len(r) >= 2]
    if len(paired) < 2:
        print(f"{label:46} too few replicated codebases ({len(paired)})"); return
    noise = st.mean((a - b) ** 2 / 2 for a, b in paired)          # var of one measurement
    means = [st.mean(r[:2]) if len(r) >= 2 else r[0] for r in reps.values()]
    total = st.variance(means)
    between = max(total - noise / 2, 0)                              # means are of 2 runs
    icc = between / (between + noise) if between + noise else 0
    need = 4 * noise / between if between else math.inf              # runs for reliability 0.8
    print(f"{label:46} n={len(reps):2}  spread(sd, ×)={math.exp(math.sqrt(between)):.3f}  "
          f"noise(sd, ×)={math.exp(math.sqrt(noise)):.3f}  1-run reliability={icc:.2f}  "
          f"runs for 0.8={need:.1f}")

PLANTED = ["reference", "if_elif", "dead_code", "duplicated", "junk_names", "golfed"]
BUILDS = ["opus-5-5_s0", "opus-5-5_s1", "sonnet-5-5_s0", "sonnet-5-5_s1", "bon_s0", "bon_s1"]
SIBS0 = [f"bonm7_s0_c{i}" for i in range(6)]
SIBS1 = [f"bonm7_s1_c{i}" for i in range(6)]
print("\n== probes (4 small changes) ==")
for models, name in (([OPUS, SONNET], "panel"), ([OPUS], "opus"), ([SONNET], "sonnet")):
    decompose(f"planted flaws, {name}", PLANTED, "probe", models)
    decompose(f"builds from scratch, {name}", BUILDS, "probe", models)
    decompose(f"all 12 above, {name}", PLANTED + BUILDS, "probe", models)
print("\n== big probes (Sonnet) ==")
decompose("siblings seed 0", SIBS0, "bigprobe", [SONNET])
decompose("siblings seed 1", SIBS1, "bigprobe", [SONNET])
decompose("siblings both seeds", SIBS0 + SIBS1, "bigprobe", [SONNET])
print("\n== answer key (chains) ==")
for models, name in (([OPUS, SONNET], "both"), ([OPUS], "opus"), ([SONNET], "sonnet")):
    decompose(f"planted flaws, {name}", PLANTED, "chain", models)
    decompose(f"builds from scratch, {name}", BUILDS, "chain", models)
decompose("siblings seed 0, sonnet", SIBS0, "chain", [SONNET])
decompose("siblings seed 1, sonnet", SIBS1, "chain", [SONNET])
decompose("siblings both seeds, sonnet", SIBS0 + SIBS1, "chain", [SONNET])

print("\n== one policy: Sonnet builds from scratch ==")
GROUP = [cb for cb in sorted({r["cb"] for r in ROWS}) if cb.startswith("sonnet-5-5_s")]
decompose(f"probes, sonnet ({len(GROUP)} builds)", GROUP, "probe", [SONNET])
decompose(f"answer key, sonnet chain", GROUP, "chain", [SONNET])

def rank(v):
    return [sorted(v).index(a) for a in v]
def spearman(x, y):
    rx, ry = rank(x), rank(y); n = len(x)
    return 1 - 6 * sum((a - b) ** 2 for a, b in zip(rx, ry)) / (n * (n * n - 1))
pv = {cb: st.mean(replicates(cb, "probe", [SONNET])) for cb in GROUP if replicates(cb, "probe", [SONNET])}
cv = {cb: st.mean(replicates(cb, "chain", [SONNET])) for cb in GROUP if replicates(cb, "chain", [SONNET])}
both = sorted(set(pv) & set(cv))
for cb in both:
    print(f"  {cb:16} probe {math.exp(pv[cb]):7.0f}  answer key {math.exp(cv[cb]):7.0f}")
if len(both) >= 3:
    print(f"  probe vs answer key, Spearman over {len(both)} builds: {spearman([pv[c] for c in both], [cv[c] for c in both]):+.2f}")
