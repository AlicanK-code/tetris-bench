"""Board features: the numbers that describe how much trouble a stack is in.

These four are the classic Tetris heuristic features, and they are deliberately
plain functions of a :class:`Board` -- no agent, no game, no LLM. That keeps them
usable in three places at once: the hand-written heuristic agent, the per-game
statistics logged for a run, and the feedback summary a model receives between
games in the improvement loop.

What each one is for:

- **aggregate height** -- how full the board is overall, and so roughly how close
  the game is to ending.
- **max height** -- the single worst column, which is what actually kills you.
- **bumpiness** -- how jagged the surface is. A jagged surface only accepts
  particular pieces, so it quietly reduces your options several moves ahead.
- **holes** -- empty cells with a block above them. The expensive one: a buried
  gap cannot be filled without first clearing every row on top of it, so a single
  hole degrades a whole region of the board.
"""

from __future__ import annotations

from tetris_bench.engine.board import Board


def aggregate_height(board: Board) -> int:
    """The sum of every column's height."""
    return sum(board.column_heights())


def max_height(board: Board) -> int:
    """The height of the tallest column, or 0 on an empty board."""
    return max(board.column_heights(), default=0)


def bumpiness(board: Board) -> int:
    """The total height difference between neighbouring columns.

    A flat surface scores 0. Only adjacent pairs are compared, so a board can be
    tall and smooth (low bumpiness) or short and jagged (high bumpiness).
    """
    heights = board.column_heights()
    # strict=False is deliberate: heights[1:] is one shorter, which is what pairs
    # each column with its right-hand neighbour and leaves the last one unpaired.
    return sum(abs(left - right) for left, right in zip(heights, heights[1:], strict=False))


def holes(board: Board) -> int:
    """The number of empty cells that have at least one block above them.

    Counted per column, top down: once a block has been seen in a column, every
    empty cell below it is a hole. Two details that are easy to get wrong --
    empty space *above* the stack is not a hole, and a column can contain several
    separate holes, all of which count.
    """
    total = 0
    for col in range(board.width):
        blocked = False
        for row in range(board.height):
            if board.is_filled(row, col):
                blocked = True
            elif blocked:
                total += 1
    return total
