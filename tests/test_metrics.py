"""Tests for board feature metrics."""

import pytest

from tetris_bench.engine.board import Board
from tetris_bench.metrics import aggregate_height, bumpiness, holes, max_height


def test_empty_board_has_no_features():
    board = Board.empty(10, 20)
    assert aggregate_height(board) == 0
    assert max_height(board) == 0
    assert bumpiness(board) == 0
    assert holes(board) == 0


def test_single_column_board_does_not_break_bumpiness():
    """There are no adjacent pairs to compare, so the sum is empty."""
    assert bumpiness(Board.from_strings(["X"])) == 0


class TestHeight:
    def test_aggregate_height_sums_columns(self):
        board = Board.from_strings(["...X", ".X.X", "XX.X"])
        assert aggregate_height(board) == 1 + 2 + 0 + 3

    def test_max_height_takes_the_worst_column(self):
        assert max_height(Board.from_strings(["...X", ".X.X", "XX.X"])) == 3

    def test_height_is_measured_to_the_top_of_the_column(self):
        """A hole underneath does not reduce the height above it."""
        board = Board.from_strings(["X", ".", "X"])
        assert aggregate_height(board) == 3
        assert max_height(board) == 3


class TestBumpiness:
    def test_flat_surface_is_zero(self):
        assert bumpiness(Board.from_strings(["....", "XXXX"])) == 0

    def test_staircase_sums_adjacent_differences(self):
        # heights 0, 1, 2 -> |0-1| + |1-2|
        assert bumpiness(Board.from_strings(["...", "..X", ".XX"])) == 2

    def test_tower_beside_a_gap(self):
        # heights 3, 1, 1 -> |3-1| + |1-1|
        assert bumpiness(Board.from_strings(["X..", "X..", "XXX"])) == 2

    def test_only_neighbours_are_compared(self):
        """A tall board can be perfectly smooth."""
        tall_and_flat = Board.from_strings(["XXXX"] * 5)
        assert bumpiness(tall_and_flat) == 0
        assert aggregate_height(tall_and_flat) == 20


class TestHoles:
    def test_no_holes_on_a_flat_stack(self):
        assert holes(Board.from_strings(["....", "XXXX"])) == 0

    def test_open_space_above_the_stack_is_not_a_hole(self):
        assert holes(Board.from_strings([".", ".", "X", "X"])) == 0

    def test_a_single_buried_gap(self):
        assert holes(Board.from_strings(["X", ".", "X"])) == 1

    def test_several_gaps_in_one_column_all_count(self):
        """The common bug is stopping after the first gap."""
        assert holes(Board.from_strings(["X", ".", ".", "X"])) == 2

    def test_alternating_gaps(self):
        # blocks at rows 0 and 2; empties at rows 1 and 3 are both covered
        assert holes(Board.from_strings(["X", ".", "X", "."])) == 2

    def test_holes_counted_per_column(self):
        board = Board.from_strings(
            [
                "X.X",
                "..X",
                "XXX",
            ]
        )
        # col 0: block row 0, gap row 1 -> 1. col 1: empty until row 2 -> 0.
        # col 2: full -> 0.
        assert holes(board) == 1

    def test_overhang_creates_a_hole(self):
        board = Board.from_strings(
            [
                "XX",
                ".X",
            ]
        )
        assert holes(board) == 1


@pytest.mark.parametrize(
    ("rows", "expected"),
    [
        ([".", ".", ".", "."], (0, 0, 0, 0)),
        (["X", ".", ".", "X"], (4, 4, 0, 2)),
        ([".", ".", "X", "X"], (2, 2, 0, 0)),
        (["X", ".", "X", "."], (4, 4, 0, 2)),
        (["....", "XXXX"], (4, 1, 0, 0)),
        (["...", "..X", ".XX"], (3, 2, 2, 0)),
        (["X..", "X..", "XXX"], (5, 3, 2, 0)),
    ],
)
def test_feature_table(rows, expected):
    """All four features over a table of hand-checked boards."""
    board = Board.from_strings(rows)
    actual = (aggregate_height(board), max_height(board), bumpiness(board), holes(board))
    assert actual == expected
