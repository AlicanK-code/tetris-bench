"""Tests for the curve power arithmetic.

This module exists because the same few lines were written inline in four
documents and three scripts, and the repo consequently published a ratio
computed against two different denominators. So the tests do two jobs:

- pin the **published figures** for all four rungs, read from the artifacts on
  disk, so a change to the aggregation that silently moves a number in the
  README fails here instead;
- pin the pieces that are easy to get wrong in isolation -- a chain whose first
  or last position was rejected, and rounding a sample size *up*.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from tetris_bench.curves import build_curves
from tetris_bench.power import (
    MDE_CONSTANT,
    RungPower,
    chains_for,
    held_out_rates,
    minimum_detectable,
    summarise,
)

PUBLISHED = Path("runs/published")

#: model -> (chains, median gain, paired sd, chain spread), as published in
#: docs/findings/ and the README on 2026-11-24.
EXPECTED = {
    "4b-loop": ("qwen3-4b", 5, -4.63, 8.69, 3.63),
    "8b-loop": ("qwen3-8b", 10, 2.51, 12.44, 14.89),
    "five-chain": ("qwen3-14b", 5, 8.04, 8.74, 12.55),
    "30b-pilot": ("qwen3-30b", 6, 7.37, 16.76, 15.70),
}


def load(run: str) -> RungPower:
    rows = [json.loads(line) for line in (PUBLISHED / run / "loop.jsonl").open()]
    spread = next(curve.chain_spread() for curve in build_curves(rows))
    return summarise(rows, spread)


@pytest.mark.parametrize("run", sorted(EXPECTED))
def test_the_published_figures_still_come_out_of_the_artifacts(run: str) -> None:
    model, chains, gain, sd, spread = EXPECTED[run]
    power = load(run)
    assert power.model == model
    assert power.chains == chains
    assert power.median_gain == pytest.approx(gain, abs=0.005)
    assert power.paired_sd == pytest.approx(sd, abs=0.005)
    assert power.chain_spread == pytest.approx(spread, abs=0.005)


@pytest.mark.parametrize("run", sorted(EXPECTED))
def test_no_rung_detected_its_own_gain(run: str) -> None:
    """The project's headline, as an assertion."""
    assert not load(run).detected


def test_the_ratio_has_no_constant_across_rungs() -> None:
    """The finding that retired scaling one rung's sigma from another's."""
    ratios = sorted(load(run).ratio for run in EXPECTED)
    assert ratios[0] == pytest.approx(0.70, abs=0.01)
    assert ratios[-1] == pytest.approx(2.39, abs=0.01)
    assert ratios[-1] / ratios[0] > 3


# ------------------------------------------------------------------ arithmetic


def test_minimum_detectable_shrinks_with_the_root_of_n() -> None:
    assert minimum_detectable(10.0, 1) == pytest.approx(MDE_CONSTANT * 10.0)
    assert minimum_detectable(10.0, 4) == pytest.approx(MDE_CONSTANT * 5.0)


def test_minimum_detectable_needs_a_chain() -> None:
    with pytest.raises(ValueError, match="at least one chain"):
        minimum_detectable(10.0, 0)


def test_chains_for_rounds_up() -> None:
    """9.26 chains means 10. Rounding to nearest understates the requirement."""
    assert chains_for(8.74, 8.04) == 10
    assert math.ceil((MDE_CONSTANT * 8.74 / 8.04) ** 2) == 10


def test_chains_for_treats_the_target_as_a_magnitude() -> None:
    assert chains_for(8.69, 4.63) == chains_for(8.69, -4.63)


def test_no_sample_size_resolves_a_gain_of_zero() -> None:
    with pytest.raises(ValueError, match="gain of zero"):
        chains_for(10.0, 0.0)


def test_a_flat_run_has_no_chain_count_for_its_own_gain() -> None:
    flat = RungPower("m", chains=5, median_gain=0.0, paired_sd=8.0, chain_spread=8.0)
    assert flat.chains_for_observed() is None


# ----------------------------------------------------------------- aggregation


def rows(*cells: tuple[int, int, str, int, int]) -> list[dict]:
    return [
        {
            "model": "m",
            "chain": chain,
            "iteration": iteration,
            "split": split,
            "score": score,
            "pieces_placed": pieces,
        }
        for chain, iteration, split, score, pieces in cells
    ]


def test_rates_are_totals_over_totals_not_a_mean_of_rates() -> None:
    """A 40-piece game must not weigh as much as a 2,000-piece one."""
    rates = held_out_rates(rows((0, 0, "eval", 100, 10), (0, 0, "eval", 100, 90)))
    assert rates[(0, 0)] == pytest.approx(2.0)  # 200/100, not (10 + 1.11)/2


def test_training_rows_are_excluded() -> None:
    rates = held_out_rates(rows((0, 0, "train", 999, 1), (0, 0, "eval", 10, 10)))
    assert rates[(0, 0)] == pytest.approx(1.0)


def test_a_position_with_no_pieces_is_absent_rather_than_zero() -> None:
    assert held_out_rates(rows((0, 0, "eval", 0, 0))) == {}


def test_a_chain_that_starts_late_is_measured_from_where_it_starts() -> None:
    """A rejection at iteration 0 is a missing position, not a score of zero."""
    power = summarise(
        rows(
            (0, 1, "eval", 100, 10),  # chain 0 begins at iteration 1
            (0, 5, "eval", 300, 10),
            (1, 0, "eval", 100, 10),
            (1, 5, "eval", 100, 10),
        ),
        chain_spread=1.0,
    )
    # chain 0 gains 30 - 10 = 20, chain 1 gains 0; the median of the two is 10.
    assert power.median_gain == pytest.approx(10.0)
    assert power.chains == 2


def test_a_log_with_one_chain_has_no_paired_spread() -> None:
    with pytest.raises(ValueError, match="at least two chains"):
        summarise(rows((0, 0, "eval", 10, 10), (0, 5, "eval", 20, 10)), chain_spread=1.0)


def test_a_log_with_no_held_out_games_is_refused() -> None:
    with pytest.raises(ValueError, match="no held-out games"):
        summarise(rows((0, 0, "train", 10, 10)), chain_spread=1.0)
