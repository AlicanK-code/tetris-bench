"""Enumerating every placement a piece can legally reach.

A *placement* is a finished move: rotate the piece in free space above the
board, line it up over a column, and drop it straight down until it lands. That
is the whole move vocabulary of this benchmark -- there are no tucks or slides,
where a piece is shifted sideways underneath an overhang after falling.

Leaving tucks out is a deliberate narrowing. It keeps this module a small pure
function of the board, makes a placement list short enough to show a model in a
prompt, and keeps the thing being measured squarely on *how well a model scores
a position*, rather than on whether it can spot a clever slide. Adding tucks
later means adding a reachability search here and nothing else.
"""

from __future__ import annotations

from dataclasses import dataclass

from tetris_bench.engine.board import Board
from tetris_bench.engine.pieces import PIECES, Cell


@dataclass(frozen=True)
class Placement:
    """One finished move: a rotation, a column, and where the piece landed.

    ``row`` and ``column`` are the top-left corner of the piece's bounding box
    once it has come to rest, and ``cells`` are the absolute board coordinates it
    occupies. Carrying the resolved cells means a scoring function never has to
    recompute the geometry.
    """

    kind: str
    rotation: int
    column: int
    row: int
    cells: tuple[Cell, ...]

    @property
    def landing_row(self) -> int:
        """The lowest board row this piece touches (its deepest cell)."""
        return max(row for row, _ in self.cells)


def _drop(board: Board, shape: tuple[Cell, ...], column: int) -> int | None:
    """Drop a shape down ``column`` and return the row it rests at.

    Returns ``None`` if the shape cannot rest fully inside the board, which
    happens when the stack has grown high enough that the piece would come to
    rest poking out through the ceiling.
    """
    shape_height = max(r for r, _ in shape) + 1

    # Start fully above the ceiling, then fall one row at a time. Negative rows
    # are legal mid-flight, which is why `Board.collides` tolerates them.
    row = -shape_height
    while not board.collides((row + 1 + dr, column + dc) for dr, dc in shape):
        row += 1

    # Resting half-out of the top of the board does not count as a placement.
    if row < 0:
        return None
    return row


def apply_placement(board: Board, placement: Placement) -> tuple[Board, int]:
    """Lock a placement in and clear any completed rows.

    Returns the resulting board and how many rows it cleared. This is the one
    place that "commit a move" is defined, shared by :meth:`Game.step` and by any
    scoring function that needs to look at the board a move would produce.
    """
    locked = board.place(placement.cells, placement.kind)
    return locked.clear_lines()


def legal_placements(board: Board, kind: str) -> list[Placement]:
    """Every placement of ``kind`` that lands fully inside ``board``.

    An empty list means the piece cannot be placed at all, which is how this
    engine detects game over.
    """
    piece = PIECES[kind]
    placements: list[Placement] = []

    for rotation, shape in enumerate(piece.rotations):
        span = piece.width(rotation)
        for column in range(board.width - span + 1):
            row = _drop(board, shape, column)
            if row is None:
                continue
            cells = tuple((row + dr, column + dc) for dr, dc in shape)
            placements.append(
                Placement(
                    kind=kind,
                    rotation=rotation,
                    column=column,
                    row=row,
                    cells=cells,
                )
            )
    return placements
