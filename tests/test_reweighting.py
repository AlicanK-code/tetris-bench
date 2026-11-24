"""Tests for the term-level replay designs.

The arithmetic is small and two pieces of it decide a published claim:

- the **interaction** term. Its sign is the whole conclusion about the 30B's
  revision -- that neither the repair nor the reweighting explains the outcome
  alone -- and the four-cell formula is easy to get backwards.
- the **ablation enumeration**, which must move exactly one weight per variant
  and must keep a weight whose target equals its baseline, because "moving it
  changes nothing" is a result rather than a reason to drop a row.

:class:`TieCountingAgent` is covered too, since it exists precisely because
``StrategyDiagnostics.flat_moves`` measures the wrong thing.
"""

from __future__ import annotations

import pytest

from tetris_bench.engine.game import Game
from tetris_bench.reweighting import (
    Factorial,
    TieCountingAgent,
    TieCounts,
    ablation_weights,
    render,
)
from tetris_bench.sandbox import ScoringSandbox

# ------------------------------------------------------------------- Factorial


def test_main_effects_and_total() -> None:
    # A alone is worth +1, B alone +2, and together +10.
    cells = Factorial(low_low=0.0, high_low=1.0, low_high=2.0, high_high=10.0)
    assert cells.effect_a == 1.0
    assert cells.effect_b == 2.0
    assert cells.total == 10.0


def test_interaction_is_what_the_two_factors_add_beyond_their_sum() -> None:
    cells = Factorial(low_low=0.0, high_low=1.0, low_high=2.0, high_high=10.0)
    assert cells.interaction == pytest.approx(10.0 - 1.0 - 2.0)


def test_a_purely_additive_design_has_no_interaction() -> None:
    cells = Factorial(low_low=5.0, high_low=8.0, low_high=6.0, high_high=9.0)
    assert cells.effect_a == 3.0
    assert cells.effect_b == 1.0
    assert cells.interaction == pytest.approx(0.0)


def test_the_30b_shape_a_factor_that_only_helps_with_the_other() -> None:
    """The measured cells: reweighting alone loses, and together they gain."""
    cells = Factorial(low_low=41.55, high_low=44.81, low_high=37.65, high_high=50.72)
    assert cells.effect_a == pytest.approx(3.26, abs=0.01)  # repair alone
    assert cells.effect_b == pytest.approx(-3.90, abs=0.01)  # reweighting alone
    assert cells.effect_b < 0 < cells.total
    assert cells.interaction == pytest.approx(9.81, abs=0.01)


# -------------------------------------------------------------- ablation_weights


def test_ablation_puts_the_untouched_baseline_first() -> None:
    variants = ablation_weights((1.0, 2.0), (10.0, 20.0))
    assert variants[0] == (None, (1.0, 2.0))


def test_each_variant_moves_exactly_one_weight() -> None:
    baseline, target = (1.0, 2.0, 3.0), (10.0, 20.0, 30.0)
    variants = ablation_weights(baseline, target)
    assert len(variants) == 1 + len(baseline)
    for index, weights in variants[1:]:
        assert index is not None
        moved = [i for i, (b, w) in enumerate(zip(baseline, weights, strict=True)) if b != w]
        assert moved == [int(index)]
        assert weights[int(index)] == target[int(index)]


def test_a_weight_that_does_not_move_still_gets_a_row() -> None:
    """The 8B's `lines` weight is a real row: moving it changed nothing."""
    variants = ablation_weights((5.0, 1.0), (5.0, 9.0))
    assert len(variants) == 3
    assert variants[1] == ("0", (5.0, 1.0))


def test_mismatched_lengths_are_a_programming_error() -> None:
    with pytest.raises(ValueError, match="differ in length"):
        ablation_weights((1.0,), (1.0, 2.0))


# ----------------------------------------------------------------------- render


def test_render_fills_every_slot_and_keeps_weights_readable() -> None:
    assert render("a %g b %g", (0.5, 100.0)) == "a 0.5 b 100"


def test_render_refuses_a_mismatched_template() -> None:
    with pytest.raises(ValueError, match="slots"):
        render("only %g", (1.0, 2.0))


# ------------------------------------------------------------------- TieCounts


def test_tie_counts_start_empty_and_do_not_divide_by_zero() -> None:
    counts = TieCounts()
    assert counts.tied_share == 0.0
    assert counts.mean_size == 0.0


def test_tie_counts_shares() -> None:
    counts = TieCounts(moves=4, tied_moves=1, tied_total=7, largest=4)
    assert counts.tied_share == 0.25
    assert counts.mean_size == 1.75


# --------------------------------------------------------- TieCountingAgent

#: Scores every candidate alike, so every move is one big tie at the maximum.
CONSTANT = "def score(board, placement):\n    return 1.0\n"
#: Depth varies between candidates from the first piece, so ties are rare.
DISCRIMINATING = (
    "def score(board, placement):\n"
    "    return float(sum(r * sum(row) for r, row in enumerate(board)))\n"
)


def play(source: str, pieces: int = 15) -> TieCounts:
    with ScoringSandbox(source) as box:
        agent = TieCountingAgent(box)
        game = Game(seed=1, max_pieces=pieces)
        while not game.over:
            game.step(agent.choose(game))
        return agent.ties


def test_a_constant_function_ties_on_every_move() -> None:
    counts = play(CONSTANT)
    assert counts.moves > 0
    assert counts.tied_share == 1.0
    assert counts.largest > 1


def test_a_discriminating_function_ties_far_less() -> None:
    assert play(DISCRIMINATING).tied_share < play(CONSTANT).tied_share


def test_the_agent_plays_the_first_maximum() -> None:
    """A constant function leaves every candidate tied, so index 0 is played."""
    with ScoringSandbox(CONSTANT) as box:
        agent = TieCountingAgent(box)
        game = Game(seed=1, max_pieces=5)
        assert agent.choose(game) == game.legal_placements()[0]
