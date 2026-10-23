"""The reward as a per-rollout signal: what it ranks, and what it ignores."""

import pytest

from craftbench.reward import reward


def test_broken_code_scores_zero():
    assert reward(0.0, [100, 200]) == 0


def test_less_reading_scores_higher():
    assert reward(1.0, [4_000]) > reward(1.0, [6_000])


def relative(rewards):  # each as a multiple of the group's first
    return [r / rewards[0] for r in rewards]


def test_ranking_does_not_depend_on_scale():
    """Scaling every effort, or one change being naturally bigger, scales every reward in the group
    by the same factor, so the ranking within a group is unchanged."""
    group = [(1.0, [4_000, 20_000]), (1.0, [6_000, 30_000]), (0.7, [4_000, 20_000])]
    base = [reward(f, e) for f, e in group]
    scaled = [reward(f, [x * 7 for x in e]) for f, e in group]
    bigger_change = [reward(f, [e[0], e[1] * 10]) for f, e in group]
    assert relative(scaled) == pytest.approx(relative(base))
    assert relative(bigger_change) == pytest.approx(relative(base))


def test_changes_count_by_ratio_not_size():
    """Halving the reading on a small change beats +10% on a big one (a plain average would not)."""
    assert reward(1.0, [2_000, 33_000]) > reward(1.0, [4_000, 30_000])


def test_lambda_tradeoff():
    """At λ = 0.5, twice the reading costs as much as losing ~29% of milestone tests."""
    assert reward(1.0, [2_000]) == pytest.approx(reward(1 / 2 ** 0.5, [1_000]))
