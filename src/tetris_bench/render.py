"""Turning game state into the text a model actually reads.

Everything a prompt shows lives here, so the whole model-facing surface is in one
reviewable file. Three renderers:

- :func:`render_board` -- the grid itself
- :func:`render_state` -- the grid plus the structured metadata around it
- :func:`render_placements` -- the numbered list of legal moves

Two choices worth knowing about.

**Occupancy, not piece identity.** By default a filled cell is ``#`` whatever
piece put it there. Tetris is Markovian in occupancy: which placements are legal,
which rows clear, and what the board becomes next depend only on whether a cell
is filled, so the identity of the piece that filled it cannot change the best
move. ``show_pieces=True`` keeps the letters for feedback snapshots and
debugging, where *how* a stack was built is genuinely informative.

**Placements are offered by index.** A model picks ``3``, not "rotation 1,
column 7". Choosing from a list it has been handed cannot produce an illegal
move, whereas describing a move freely can -- and an invalid output is a wasted
call plus a row in the failure column.
"""

from __future__ import annotations

from collections.abc import Sequence

from tetris_bench.engine.board import EMPTY, Board
from tetris_bench.engine.game import Game
from tetris_bench.engine.placements import Placement
from tetris_bench.metrics import board_stats

FILLED = "#"


def column_header(width: int) -> str:
    """A row of column indices to sit above the grid.

    Columns past 9 show their last digit only. Keeping it one character per
    column is what makes the header line up with the grid, which is the entire
    reason it helps -- a model can read a column number straight down.
    """
    return "".join(str(col % 10) for col in range(width))


def render_board(board: Board, *, show_pieces: bool = False, header: bool = True) -> str:
    """Render the board as a text grid, top row first.

    With ``show_pieces=False`` every filled cell is ``#``; with ``True`` the
    piece letters the board stores are kept.
    """
    if show_pieces:
        rows = list(board.rows)
    else:
        rows = ["".join(EMPTY if cell == EMPTY else FILLED for cell in row) for row in board.rows]

    if header:
        return "\n".join([column_header(board.width), *rows])
    return "\n".join(rows)


def render_placements(placements: Sequence[Placement]) -> str:
    """Render the legal moves as a numbered list a model can choose from.

    The index is the answer format. ``lands`` is the lowest row the piece
    touches, which is the cheapest way to convey how deep a move goes without
    making the model re-derive the geometry.
    """
    if not placements:
        return "(no legal placements)"
    width = len(str(len(placements) - 1))
    return "\n".join(
        f"{index:>{width}}  rot={placement.rotation} col={placement.column} "
        f"lands row {placement.landing_row}"
        for index, placement in enumerate(placements)
    )


def render_state(game: Game, *, show_pieces: bool = False, show_placements: bool = False) -> str:
    """Render the full prompt-facing state: grid, metadata and current stats.

    Note there is no hold piece. The engine has none: hold roughly doubles the
    branching factor per turn and adds a state dimension to reason about, for a
    benchmark whose subject is the quality of a scoring function rather than the
    breadth of the move vocabulary.
    """
    stats = board_stats(game.board)
    sections = [
        render_board(game.board, show_pieces=show_pieces),
        "",
        f"current piece   {game.current}",
        f"next pieces     {' '.join(game.next_pieces)}",
        f"score           {game.score}",
        f"lines cleared   {game.lines_cleared}",
        f"pieces placed   {game.pieces_placed}",
        f"max height      {stats.max_height}",
        f"holes           {stats.holes}",
        f"bumpiness       {stats.bumpiness}",
    ]
    if show_placements:
        sections += ["", "legal placements:", render_placements(game.legal_placements())]
    return "\n".join(sections)
