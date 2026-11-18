"""What an agent is, and the adapter that turns a scoring function into one.

Two layers, on purpose:

:data:`ScoringFunction` is the primitive -- ``(board, placement) -> float``,
rating a single candidate move. :class:`ScoringAgent` is a four-line adapter that
applies a scoring function to every legal placement and keeps the best.

That split is what makes the benchmark's main mode cheap to build. In
``strategy`` mode a model is asked to write exactly a
``score(board, placement) -> float`` function, so a sandboxed model-written
scorer drops into the same slot as the hand-written heuristic, driven by the same
adapter. The heuristic agent is therefore the reference implementation of the
artefact being benchmarked, not a separate code path.

Not every agent is a scorer, though -- "choose uniformly at random" is not a
per-placement rating -- so :class:`Agent` stays the general interface and
:class:`ScoringAgent` is just one implementation of it.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

from tetris_bench.engine.board import Board
from tetris_bench.engine.game import Game
from tetris_bench.engine.placements import Placement

ScoringFunction = Callable[[Board, Placement], float]
"""Rates one candidate placement against the board it would be played on.

Higher is better. This is the signature a model is asked to produce in
``strategy`` mode.
"""


class Agent(Protocol):
    """Anything that can pick a placement for the current piece.

    A :class:`~typing.Protocol` rather than an abstract base class: agents are
    matched structurally, so a class satisfies this by having the right members
    and needs to inherit nothing. There is no shared behaviour to inherit, and a
    test can pass a small stub without ceremony.
    """

    name: str

    def choose(self, game: Game) -> Placement:
        """Pick one of ``game.legal_placements()``."""
        ...


class ScoringAgent:
    """Plays the highest-scoring legal placement.

    Ties go to whichever placement comes first in the legal-placement list,
    because :func:`max` returns the first maximum. That is arbitrary but
    deterministic, which is what reproducibility needs.
    """

    def __init__(self, scorer: ScoringFunction, name: str = "scoring") -> None:
        self._scorer = scorer
        self.name = name

    def choose(self, game: Game) -> Placement:
        placements = game.legal_placements()
        if not placements:
            raise ValueError("no legal placements: the game is over and should not be stepped")
        return max(placements, key=lambda placement: self._scorer(game.board, placement))
