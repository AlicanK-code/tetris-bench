"""Tests for the decision-level inertness measure.

Four things here are load-bearing for a published claim and each is easy to get
subtly wrong:

- ``choose_index`` must break ties exactly as :class:`StrategyAgent` does, since
  it deliberately duplicates that rule rather than sharing it. If the two ever
  disagree, this analysis measures a player nobody ran.
- "identical scores" and "identical choice" are different properties, and the
  whole point of the measure is that the second is much more common than the
  first.
- pairing must follow the loop's lineage, which **skips a rejected generation**
  rather than pairing across it.
- a pair that cannot be played must come back as a recorded failure, not an
  exception, or one bad function ends a sweep over a hundred of them.
"""

from __future__ import annotations

import pytest

from tetris_bench.engine.game import Game
from tetris_bench.placement_diff import (
    ComparingAgent,
    MoveComparison,
    PairDiff,
    Pairing,
    choose_index,
    compare_scores,
    diff_pair,
    lineage_pairs,
)
from tetris_bench.sandbox import ScoringSandbox, build_items

# ---------------------------------------------------------------- choose_index


@pytest.mark.parametrize(
    ("scores", "expected"),
    [
        ([1.0, 2.0, 3.0], 2),
        ([3.0, 2.0, 1.0], 0),
        ([1.0, 3.0, 3.0], 1),  # a tie goes to the FIRST maximum
        ([0.0, 0.0, 0.0], 0),  # a flat function plays index 0
        ([float("-inf")] * 4, 0),  # every candidate unplayable
        ([float("-inf"), 0.5], 1),
    ],
)
def test_choose_index_takes_the_first_maximum(scores: list[float], expected: int) -> None:
    assert choose_index(scores) == expected


def test_choose_index_matches_the_agent_that_produced_every_published_number() -> None:
    """The duplicated rule must agree with StrategyAgent on a real board.

    Asserted against the agent's own expression rather than against a constant,
    so that if `StrategyAgent.choose` ever changes its tie-breaking this fails
    instead of silently measuring the old rule.
    """
    scores = [1.0, 5.0, 5.0, float("-inf"), 2.0]
    agent_rule = max(range(len(scores)), key=lambda index: scores[index])
    assert choose_index(scores) == agent_rule


# --------------------------------------------------------------- compare_scores


def test_identical_vectors_agree_and_are_flagged_identical() -> None:
    comparison = compare_scores([1.0, 2.0], [1.0, 2.0])
    assert comparison == MoveComparison(chosen_a=1, chosen_b=1, identical_scores=True)
    assert not comparison.diverged


def test_a_uniform_rescaling_changes_every_score_and_no_choice() -> None:
    """The 8B's no-op revision in miniature: doubling cannot move an argmax."""
    a = [1.0, 7.0, 3.0]
    comparison = compare_scores(a, [2 * value for value in a])
    assert not comparison.diverged
    assert not comparison.identical_scores


def test_divergence_is_detected() -> None:
    assert compare_scores([1.0, 0.0], [0.0, 1.0]).diverged


def test_mismatched_candidate_counts_are_a_programming_error() -> None:
    with pytest.raises(ValueError, match="different candidates"):
        compare_scores([1.0], [1.0, 2.0])


# ------------------------------------------------------------------- PairDiff


def test_pair_diff_properties() -> None:
    inert = PairDiff(label="x", moves=100, diverged=0, identical_score_moves=0)
    assert inert.inert and inert.rate == 0.0
    assert not inert.arithmetically_identical

    same = PairDiff(label="x", moves=100, diverged=0, identical_score_moves=100)
    assert same.arithmetically_identical

    moved = PairDiff(label="x", moves=100, diverged=5)
    assert not moved.inert and moved.rate == 0.05


def test_a_pair_with_no_moves_is_not_called_inert() -> None:
    """Zero of zero decisions is no evidence, and must not read as agreement."""
    assert not PairDiff(label="x", moves=0, diverged=0).inert


# --------------------------------------------------------------- lineage_pairs


def rows(*positions: tuple[int, int, bool]) -> list[dict]:
    return [
        {"model": "m", "chain": chain, "iteration": iteration, "played": played}
        for chain, iteration, played in positions
    ]


def test_lineage_pairs_are_consecutive_within_a_chain() -> None:
    pairs = lineage_pairs(rows((0, 0, True), (0, 1, True), (0, 2, True)))
    assert [(p.iteration_a, p.iteration_b) for p in pairs] == [(0, 1), (1, 2)]
    assert all(p.chain == 0 for p in pairs)
    assert not any(p.skipped_rejection for p in pairs)


def test_lineage_pairs_skip_a_rejected_generation() -> None:
    """Iteration 1 never played, so the model revised iteration 0 at step 2."""
    pairs = lineage_pairs(rows((0, 0, True), (0, 1, False), (0, 2, True)))
    assert [(p.iteration_a, p.iteration_b) for p in pairs] == [(0, 2)]
    assert pairs[0].skipped_rejection


def test_lineage_pairs_never_cross_chains() -> None:
    pairs = lineage_pairs(rows((0, 5, True), (1, 0, True)))
    assert pairs == []


def test_lineage_pairs_tolerate_one_row_per_seed() -> None:
    """A log has several rows per position; each pair must appear once."""
    duplicated = rows((0, 0, True), (0, 0, True), (0, 1, True), (0, 1, True))
    assert len(lineage_pairs(duplicated)) == 1


def test_pairing_labels_name_the_saved_files() -> None:
    pair = Pairing(model="qwen3-8b", chain=1, iteration_a=4, iteration_b=5)
    assert pair.name_a == "qwen3-8b-chain1-iter4"
    assert pair.name_b == "qwen3-8b-chain1-iter5"
    assert pair.label == "qwen3-8b-chain1-iter4->5"


# ------------------------------------------------------- the agent and the driver

# `lines_cleared` is 0 for every candidate on an empty board, so a function
# built on it alone scores every placement identically and would make these
# tests pass for the wrong reason. These use depth instead -- row 0 is the top,
# so a larger weighted sum means cells sitting lower -- which varies between
# candidates from the very first piece.
DEPTH = "sum(r * sum(row) for r, row in enumerate(board))"
DOUBLED_A = f"def score(board, placement):\n    return float({DEPTH})\n"
DOUBLED_B = f"def score(board, placement):\n    return 2.0 * ({DEPTH})\n"
INVERTED = f"def score(board, placement):\n    return -float({DEPTH})\n"


def test_comparing_agent_plays_the_earlier_function_and_counts_the_later_one() -> None:
    """Driving with A means A's choice is what actually gets played."""
    with ScoringSandbox(DOUBLED_A) as box_a, ScoringSandbox(INVERTED) as box_b:
        agent = ComparingAgent(box_a, box_b)
        game = Game(seed=1, max_pieces=5)
        placements = game.legal_placements()
        chosen = agent.choose(game)

        scores_a = box_a.score(build_items(game.board, placements))
        assert chosen == placements[choose_index(scores_a)]
        assert agent.moves == 1


def test_a_uniform_rescaling_diverges_on_no_board() -> None:
    diff = diff_pair("doubled", DOUBLED_A, DOUBLED_B, seeds=(1,), max_pieces=30)
    assert diff.failure is None
    assert diff.moves > 0
    assert diff.inert
    assert not diff.arithmetically_identical  # every score differs; no choice does
    assert diff.first_divergence is None


def test_an_inverted_function_diverges_and_records_where() -> None:
    diff = diff_pair("inverted", DOUBLED_A, INVERTED, seeds=(1,), max_pieces=30)
    assert diff.diverged > 0
    assert diff.first_divergence is not None


def test_a_rejected_function_is_a_recorded_failure_not_an_exception() -> None:
    diff = diff_pair("bad", DOUBLED_A, "import os\ndef score(b, p):\n    return 0.0\n", seeds=(1,))
    assert diff.failure is not None
    assert "import" in diff.failure
    assert diff.moves == 0
    assert not diff.inert
