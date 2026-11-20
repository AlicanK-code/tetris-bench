"""The hand-written heuristic agent: a weighted sum of four board features.

This is the reference strong player. It exists to sanity-check the engine (a
sensible heuristic should comfortably beat random) and to give the LLMs something
meaningful to be measured against.

The weights come from Yiyuan Lee, "Tetris AI - The (Near) Perfect Bot" (2013),
where they were found with a genetic algorithm:
https://codemyroad.wordpress.com/2013/04/14/tetris-ai-the-near-perfect-player/

They are used unmodified on purpose: tuning them ourselves would make the
baseline a moving target, and the point of a baseline is that it does not move.

One caveat on calling this *the* reference. Lee tuned these weights for a 10x22
board with one lookahead piece under SRS rotation, and his post notes the results
"may or may not be the same for a different set of rules". This engine is 10x20,
has no lookahead, and deduplicates rotation states, so these are weights
optimised for a near neighbour of our game rather than for our game. Empirically
it hardly matters -- the agent still reaches the piece cap -- but it is a
reference ceiling, not a published optimum for these rules.

(Not to be confused with El-Tetris, Islam El-Ashi's 2011 algorithm, which is a
modification of Dellacherie's and uses six different features -- landing height,
rows eliminated, row transitions, column transitions, holes and well sums -- with
entirely different weight values.)

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
    """Weights for the four features, defaulting to Lee's 2013 values.

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
