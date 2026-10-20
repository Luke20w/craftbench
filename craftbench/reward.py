"""Per-rollout reward:  R = F × (geometric mean of E over the episode's changes) ^ (−λ)

F  fraction of hidden milestone tests passing (does the code work?)
E  effort for each change (tokens read; see effort.py)
λ  maintainability vs correctness: at 0.5, twice the reading costs as much as losing ~29% of
   milestone tests.

No batch or reference needed: the trainer compares rollouts within a group. Scaling every effort by
a constant, or one change being naturally bigger, scales every reward in the group by the same
factor, so the ranking is unchanged. The geometric mean counts each change by ratio, so a big change
can't swamp a small one.
"""

import math


def geomean(efforts) -> float:
    efforts = list(efforts)
    return math.exp(sum(math.log(max(e, 1.0)) for e in efforts) / len(efforts))


def reward(milestone_pass_fraction: float, efforts: list[float], lam: float = 0.5) -> float:
    if not efforts:
        return milestone_pass_fraction
    return milestone_pass_fraction * geomean(efforts) ** -lam
