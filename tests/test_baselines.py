"""Tests for the reference-player constants.

These exist because the project published two different heuristic rates -- 43.2
and 43.5 -- with neither labelled, so a reader comparing a model's 50.19 against
43.5 could reasonably ask why the table said 43.2. Both were right under
different conditions. The fix is that a rate now travels with its conditions,
and these pin the parts of that which are cheap to check.

The full replay is **not** here: measuring the heuristic on ten sequences at the
2,000-piece budget takes about twenty seconds, which would be a third of the
suite's runtime for one number. `analysis/baselines.py` regenerates it instead,
and the module docstring says so.
"""

from __future__ import annotations

import pytest

from tetris_bench.baselines import (
    EVAL_SEEDS,
    HEURISTIC_RATE,
    MAX_PIECES,
    RANDOM_RATE,
    Baseline,
    measure_heuristic,
    measure_random,
)


def test_the_canonical_conditions_are_the_ones_the_curves_use() -> None:
    """If these drift from the loop's defaults, every comparison silently moves."""
    from tetris_bench.loop import LoopConfig

    config = LoopConfig(model="m")
    assert config.eval_seeds == EVAL_SEEDS
    assert config.max_pieces == MAX_PIECES


def test_a_baseline_carries_its_conditions() -> None:
    label = Baseline("x", 1.0, (1000, 1001, 1002), 2000).conditions
    assert label == "seeds 1000-1002, 2,000-piece budget"


def test_the_heuristic_beats_random_by_two_orders_of_magnitude() -> None:
    assert HEURISTIC_RATE > 100 * RANDOM_RATE


def test_the_published_rate_is_between_the_two_figures_it_replaces() -> None:
    """43.16 on twenty seeds, 43.46 run to exhaustion, and the canonical one between."""
    assert 43.1 < HEURISTIC_RATE < 43.5


def test_measuring_is_totals_over_totals_not_a_mean_of_rates() -> None:
    """A short game must not weigh as much as a long one."""
    rate, score, pieces, _ = measure_heuristic(seeds=(1000, 1001), max_pieces=40)
    assert rate == pytest.approx(score / pieces)


def test_a_tiny_budget_censors_every_game() -> None:
    _, _, _, censored = measure_heuristic(seeds=(1000, 1001), max_pieces=10)
    assert censored == 2


def test_random_pools_across_agent_seeds() -> None:
    rate, score, pieces = measure_random(seeds=(1000,), max_pieces=30, agent_seeds=3)
    assert rate == pytest.approx(score / pieces)
    assert pieces > 0
