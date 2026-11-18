"""The hand-written heuristic agent: a weighted sum of four board features.

This is the reference strong player. It exists to sanity-check the engine (a
sensible heuristic should comfortably beat random) and to give the LLMs something
meaningful to be measured against.

The weights are the well-known El-Tetris values. They are published and
unmodified on purpose: tuning them ourselves would make the baseline a moving
target, and the point of a baseline is that it does not move.

One subtlety drives the whole design. The features are measured on the board the
move *would produce* -- after the piece is locked in and after any completed rows
are cleared -- not on the board as it stands now. Scoring the current board would
rate every candidate move identically, since the board is the same for all of
them; the move only shows up in its consequences.
"""

from __future__ import annotations

from dataclasses import dataclass

from tetris_bench.agents.base import ScoringAgent, ScoringFunction
from tetris_bench.engine.board import Board
from tetris_bench.engine.placements import Placement, apply_placement
from tetris_bench.metrics import aggregate_height, bumpiness, holes


@dataclass(frozen=True)
class HeuristicWeights:
    """Weights for the four features, defaulting to the El-Tetris values.

    Negative weights are penalties. Frozen and constructible so weight sets can
    be compared within a single run -- useful for showing a deliberately weaker
    baseline -- without editing source.
    """

    aggregate_height: float = -0.510066
    complete_lines: float = 0.760666
    holes: float = -0.356630
    bumpiness: float = -0.184483


DEFAULT_WEIGHTS = HeuristicWeights()


def heuristic_scorer(weights: HeuristicWeights = DEFAULT_WEIGHTS) -> ScoringFunction:
    """Build a scoring function that rates a placement by its consequences.

    Returns a closure over ``weights`` with the signature
    ``(board, placement) -> float`` -- deliberately the same signature a model is
    asked to produce in ``strategy`` mode.
    """

    def score(board: Board, placement: Placement) -> float:
        after, lines = apply_placement(board, placement)
        return (
            weights.aggregate_height * aggregate_height(after)
            + weights.complete_lines * lines
            + weights.holes * holes(after)
            + weights.bumpiness * bumpiness(after)
        )

    return score


def heuristic_agent(weights: HeuristicWeights = DEFAULT_WEIGHTS) -> ScoringAgent:
    """The heuristic agent: :class:`ScoringAgent` driven by :func:`heuristic_scorer`."""
    return ScoringAgent(heuristic_scorer(weights), name="heuristic")
