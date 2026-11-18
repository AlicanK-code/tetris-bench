"""The Tetris engine: pure game logic with no dependency on any LLM code.

Everything in here is deterministic given a seed, so a run can be reproduced
exactly from its config. The public surface is deliberately small:

- :class:`Board` -- an immutable grid of locked cells
- :class:`Piece` / :data:`PIECES` -- tetromino shapes and their rotations
- :class:`Placement` / :func:`legal_placements` -- the move vocabulary
- :class:`SevenBag` -- seeded piece generation
- :class:`Game` -- one game, advanced a placement at a time
"""

from tetris_bench.engine.board import DEFAULT_HEIGHT, DEFAULT_WIDTH, EMPTY, Board
from tetris_bench.engine.game import LINE_SCORES, Game, GameOverCause
from tetris_bench.engine.pieces import PIECE_KINDS, PIECES, Cell, Piece, Shape
from tetris_bench.engine.placements import Placement, legal_placements
from tetris_bench.engine.rng import SevenBag

__all__ = [
    "DEFAULT_HEIGHT",
    "DEFAULT_WIDTH",
    "EMPTY",
    "LINE_SCORES",
    "PIECES",
    "PIECE_KINDS",
    "Board",
    "Cell",
    "Game",
    "GameOverCause",
    "Piece",
    "Placement",
    "SevenBag",
    "Shape",
    "legal_placements",
]
