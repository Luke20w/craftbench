"""Variance components of log effort: codebase, codebase×change, codebase×reader, run-to-run.
Balanced design: 12 codebases × 4 probe changes × 2 readers × 2 runs. Then: what a measurement with C changes,
M readers and K runs each costs in noise, against the codebase spread it is trying to see."""
import math, statistics as st, sys
from itertools import product
sys.path.insert(0, __file__.rsplit("/", 1)[0])
from load import load

CBS = ["reference", "if_elif", "dead_code", "duplicated", "junk_names", "golfed",
       "opus-5-5_s0", "opus-5-5_s1", "sonnet-5-5_s0", "sonnet-5-5_s1", "bon_s0", "bon_s1"]
CH = ["subpipelines", "case", "limits", "trace"]
MS = ["claude-opus-5-5", "claude-sonnet-5-5"]
y = {}
for r in load():
    if r["kind"] == "probe" and r["cb"] in CBS and r["model"] in MS and r["run"] in (0, 1):
        y[(r["cb"], r["change"], r["model"], r["run"])] = math.log(max(r["effort"], 1))
assert len(y) == len(CBS) * 4 * 2 * 2, len(y)

def m(**fix):
    keys = [k for k in y if all(k[i] == v for i, v in fix.items())]
    return st.mean(y[k] for k in keys)

nc, nh, nm, nk = len(CBS), 4, 2, 2
g = m()
A = {c: m(**{"0": c}) if False else st.mean(y[(c, h, mm, k)] for h in CH for mm in MS for k in (0, 1)) for c in CBS}
B = {h: st.mean(y[(c, h, mm, k)] for c in CBS for mm in MS for k in (0, 1)) for h in CH}
Cm = {mm: st.mean(y[(c, h, mm, k)] for c in CBS for h in CH for k in (0, 1)) for mm in MS}
AB = {(c, h): st.mean(y[(c, h, mm, k)] for mm in MS for k in (0, 1)) for c in CBS for h in CH}
AC = {(c, mm): st.mean(y[(c, h, mm, k)] for h in CH for k in (0, 1)) for c in CBS for mm in MS}
BC = {(h, mm): st.mean(y[(c, h, mm, k)] for c in CBS for k in (0, 1)) for h in CH for mm in MS}
ABC = {(c, h, mm): st.mean(y[(c, h, mm, k)] for k in (0, 1)) for c in CBS for h in CH for mm in MS}

def ms(ss, df): return ss / df
MSA = ms(nh*nm*nk*sum((A[c]-g)**2 for c in CBS), nc-1)
MSAB = ms(nm*nk*sum((AB[c,h]-A[c]-B[h]+g)**2 for c in CBS for h in CH), (nc-1)*(nh-1))
MSAC = ms(nh*nk*sum((AC[c,mm]-A[c]-Cm[mm]+g)**2 for c in CBS for mm in MS), (nc-1)*(nm-1))
MSABC = ms(nk*sum((ABC[c,h,mm]-AB[c,h]-AC[c,mm]-BC[h,mm]+A[c]+B[h]+Cm[mm]-g)**2 for c in CBS for h in CH for mm in MS),
           (nc-1)*(nh-1)*(nm-1))
MSE = ms(sum((y[k]-ABC[k[:3]])**2 for k in y), nc*nh*nm*(nk-1))
e = MSE
abc = max((MSABC - MSE) / nk, 0)
ab = max((MSAB - MSABC) / (nm*nk), 0)
ac = max((MSAC - MSABC) / (nh*nk), 0)
a = max((MSA - MSAB - MSAC + MSABC) / (nh*nm*nk), 0)
print(f"variance of log effort  codebase {a:.3f}  ×change {ab:.3f}  ×reader {ac:.3f}  ×change×reader {abc:.3f}  run {e:.3f}")
print("measurement noise vs codebase signal (reliability for ranking these 12 by their average over all changes/readers):")
for C, M, K in [(4, 2, 1), (4, 2, 2), (4, 2, 4), (8, 2, 1), (8, 2, 2), (4, 1, 2), (8, 1, 1), (12, 2, 1), (16, 2, 1)]:
    noise = ab / C + ac / M + abc / (C * M) + e / (C * M * K)
    print(f"  {C:2} changes × {M} readers × {K} runs = {C*M*K:3} runs: reliability {a / (a + noise):.2f}")
