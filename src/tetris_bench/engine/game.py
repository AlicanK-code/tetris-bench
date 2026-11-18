"""A single game of placement-based Tetris.

:class:`Board` is immutable data; :class:`Game` is the mutable session that
walks it forward one placement at a time. That split keeps the pure geometry
testable on its own while the game loop stays easy to read.

A game ends one of two ways. Either the stack grows until the next piece has
nowhere to land (``"block_out"``), or it reaches its piece budget
(``"piece_limit"``). The budget matters more than it looks: a competent
heuristic can stack cleanly more or less forever, so without a cap a benchmark
run would never finish. Capping pieces instead of wall-clock time also keeps
every model's game the same length, which is what makes scores comparable.
"""

from __future__ import annotations

from typing import Literal

from tetris_bench.engine.board import DEFAULT_HEIGHT, DEFAULT_WIDTH, Board
from tetris_bench.engine.placements import Placement, apply_placement, legal_placements
from tetris_bench.engine.rng import SevenBag

GameOverCause = Literal["block_out", "piece_limit"]

LINE_SCORES: dict[int, int] = {0: 0, 1: 100, 2: 300, 3: 500, 4: 800}
"""Points for clearing n rows at once: single, double, triple, tetris.

These are the classic Nintendo values minus the level multiplier. There are no
levels here because there is no gravity to speed up, so a line is worth the same
on the first piece as on the last. The steep curve still rewards a model that
learns to build for multi-line clears instead of chipping away one row at a time.
"""

DEFAULT_PREVIEW = 5
DEFAULT_MAX_PIECES = 500


class Game:
    """One seeded game, advanced by choosing a placement per piece."""

    def __init__(
        self,
        seed: int,
        width: int = DEFAULT_WIDTH,
        height: int = DEFAULT_HEIGHT,
        preview: int = DEFAULT_PREVIEW,
        max_pieces: int | None = DEFAULT_MAX_PIECES,
    ) -> None:
        # Refuse a meaningless budget rather than defining a behaviour for it.
        # A zero or negative cap has no sensible reading, and quietly playing one
        # piece (or none) would turn a config typo into a silently short run.
        if max_pieces is not None and max_pieces < 1:
            raise ValueError(
                f"max_pieces must be at least 1, or None for no limit, got {max_pieces}"
            )

        self.seed = seed
        self.preview = preview
        self.max_pieces = max_pieces
        self.board = Board.empty(width, height)
        self.bag = SevenBag(seed)
        self.current: str = self.bag.draw()
        self.score = 0
        self.lines_cleared = 0
        self.pieces_placed = 0
        self.over = False
        self.cause: GameOverCause | None = None

    @property
    def next_pieces(self) -> tuple[str, ...]:
        """The upcoming pieces a model is allowed to see."""
        return self.bag.peek(self.preview)

    def legal_placements(self) -> list[Placement]:
        """Every placement available to the current piece."""
        return legal_placements(self.board, self.current)

    def step(self, placement: Placement) -> int:
        """Apply a placement, returning how many lines it cleared.

        Rejects anything that is not a legal placement of the current piece, so a
        buggy agent fails loudly here rather than quietly corrupting the board.
        """
        if self.over:
            raise RuntimeError("game is already over")
        if placement.kind != self.current:
            raise ValueError(
                f"placement is for piece {placement.kind!r}, current piece is {self.current!r}"
            )
        if placement not in self.legal_placements():
            raise ValueError(f"illegal placement: {placement!r}")

        self.board, cleared = apply_placement(self.board, placement)

        self.score += LINE_SCORES[cleared]
        self.lines_cleared += cleared
        self.pieces_placed += 1

        self.current = self.bag.draw()
        self._check_over()
        return cleared

    def _check_over(self) -> None:
        """Decide whether the game has just ended, and why."""
        if self.max_pieces is not None and self.pieces_placed >= self.max_pieces:
            self.over = True
            self.cause = "piece_limit"
        elif not self.legal_placements():
            self.over = True
            self.cause = "block_out"

    def __str__(self) -> str:
        """A compact human-readable summary, handy when debugging a run."""
        status = f"over ({self.cause})" if self.over else "in play"
        return (
            f"seed={self.seed} {status} score={self.score} "
            f"lines={self.lines_cleared} pieces={self.pieces_placed} "
            f"current={self.current} next={''.join(self.next_pieces)}\n{self.board}"
        )
