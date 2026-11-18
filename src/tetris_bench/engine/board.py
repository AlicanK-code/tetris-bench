"""The playfield: an immutable grid of locked cells.

Row 0 is the **top** of the board and row ``height - 1`` is the floor, so
dropping a piece means increasing its row index. Rows are stored as strings --
``"."`` for an empty cell and the piece's letter for a filled one -- which makes
a board cheap to copy, hashable, directly printable when debugging, and safe to
hand to a sandboxed scoring function later on.

The board is immutable: :meth:`Board.place` and :meth:`Board.clear_lines` return
new boards rather than modifying this one. For a 10x20 grid the copying cost is
irrelevant, and in exchange every board state can be snapshotted into a feedback
log without worrying about it changing underneath us.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from tetris_bench.engine.pieces import Cell

EMPTY = "."
"""The character marking an empty cell."""

DEFAULT_WIDTH = 10
DEFAULT_HEIGHT = 20


@dataclass(frozen=True)
class Board:
    """A rectangular playfield of locked cells, top row first."""

    rows: tuple[str, ...]

    @classmethod
    def empty(cls, width: int = DEFAULT_WIDTH, height: int = DEFAULT_HEIGHT) -> Board:
        """Create a board with no locked cells."""
        if width <= 0 or height <= 0:
            raise ValueError(f"board must be non-empty, got {width}x{height}")
        return cls(rows=tuple(EMPTY * width for _ in range(height)))

    @classmethod
    def from_strings(cls, rows: Iterable[str]) -> Board:
        """Build a board from text rows, mainly so tests can draw a board inline.

        Any character other than ``"."`` counts as filled, which lets a test
        write ``"XXXX......"`` without caring which piece the cells came from.
        """
        materialised = tuple(rows)
        if not materialised:
            raise ValueError("board must have at least one row")
        widths = {len(row) for row in materialised}
        if len(widths) != 1:
            raise ValueError(f"all rows must be the same width, got widths {sorted(widths)}")
        return cls(rows=materialised)

    @property
    def height(self) -> int:
        """The number of rows."""
        return len(self.rows)

    @property
    def width(self) -> int:
        """The number of columns."""
        return len(self.rows[0])

    def is_filled(self, row: int, col: int) -> bool:
        """Whether the cell at ``(row, col)`` holds a locked block."""
        return self.rows[row][col] != EMPTY

    def collides(self, cells: Iterable[Cell]) -> bool:
        """Whether any of ``cells`` is blocked.

        A cell is blocked if it is outside the side walls, below the floor, or on
        top of a locked block. Cells **above** the ceiling (negative rows) are
        not collisions: that is what lets a piece start off-screen and fall in.
        Whether a piece may finally come to rest up there is a separate question,
        answered in :mod:`tetris_bench.engine.placements`.
        """
        for row, col in cells:
            if col < 0 or col >= self.width:
                return True
            if row >= self.height:
                return True
            if row >= 0 and self.is_filled(row, col):
                return True
        return False

    def place(self, cells: Iterable[Cell], kind: str) -> Board:
        """Return a new board with ``cells`` locked in as pieces of type ``kind``."""
        grid = [list(row) for row in self.rows]
        for row, col in cells:
            if not (0 <= row < self.height and 0 <= col < self.width):
                raise ValueError(f"cell ({row}, {col}) is outside the board")
            if grid[row][col] != EMPTY:
                raise ValueError(f"cell ({row}, {col}) is already filled")
            grid[row][col] = kind
        return Board(rows=tuple("".join(row) for row in grid))

    def clear_lines(self) -> tuple[Board, int]:
        """Remove every full row, returning the new board and how many went.

        Surviving rows keep their order and fall to the bottom; fresh empty rows
        are added at the top to keep the height constant.
        """
        kept = [row for row in self.rows if EMPTY in row]
        cleared = self.height - len(kept)
        if cleared == 0:
            return self, 0
        fresh = [EMPTY * self.width] * cleared
        return Board(rows=tuple(fresh + kept)), cleared

    def column_heights(self) -> tuple[int, ...]:
        """Height of each column, measured from the floor.

        A column whose topmost block sits in row ``r`` has height
        ``height - r``; an empty column has height 0.
        """
        heights: list[int] = []
        for col in range(self.width):
            height = 0
            for row in range(self.height):
                if self.is_filled(row, col):
                    height = self.height - row
                    break
            heights.append(height)
        return tuple(heights)

    def occupancy(self) -> tuple[tuple[bool, ...], ...]:
        """A plain true/false view of the grid, with piece identity dropped.

        This is the shape of board that metrics and model-written scoring
        functions care about: they only ever ask whether a cell is filled.
        """
        return tuple(tuple(cell != EMPTY for cell in row) for row in self.rows)

    def __str__(self) -> str:
        """Render the board as text, one row per line."""
        return "\n".join(self.rows)
