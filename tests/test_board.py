"""Tests for the playfield grid."""

import pytest

from tetris_bench.engine.board import EMPTY, Board


def test_empty_board_dimensions_and_contents():
    board = Board.empty(10, 20)
    assert board.width == 10
    assert board.height == 20
    assert all(row == EMPTY * 10 for row in board.rows)
    assert board.column_heights() == (0,) * 10


def test_empty_board_rejects_zero_size():
    with pytest.raises(ValueError, match="non-empty"):
        Board.empty(0, 20)


def test_from_strings_rejects_ragged_rows():
    with pytest.raises(ValueError, match="same width"):
        Board.from_strings(["....", "..."])


def test_from_strings_rejects_no_rows():
    with pytest.raises(ValueError, match="at least one row"):
        Board.from_strings([])


def test_is_filled():
    board = Board.from_strings([".X.", "..."])
    assert board.is_filled(0, 1)
    assert not board.is_filled(0, 0)


class TestCollides:
    board = Board.from_strings(
        [
            "....",
            "....",
            "XX..",
        ]
    )

    def test_free_space_does_not_collide(self):
        assert not self.board.collides([(0, 0), (1, 3)])

    def test_occupied_cell_collides(self):
        assert self.board.collides([(2, 0)])

    def test_past_left_wall_collides(self):
        assert self.board.collides([(0, -1)])

    def test_past_right_wall_collides(self):
        assert self.board.collides([(0, 4)])

    def test_below_floor_collides(self):
        assert self.board.collides([(3, 0)])

    def test_above_ceiling_is_allowed(self):
        """Negative rows are legal mid-flight so a piece can fall in from above."""
        assert not self.board.collides([(-5, 0), (-1, 0)])


def test_place_returns_a_new_board_and_leaves_the_original_alone():
    before = Board.empty(4, 3)
    after = before.place([(2, 0), (2, 1)], "O")
    assert after.rows == ("....", "....", "OO..")
    assert before.rows == ("....", "....", "....")


def test_place_rejects_cells_outside_the_board():
    board = Board.empty(4, 3)
    with pytest.raises(ValueError, match="outside the board"):
        board.place([(3, 0)], "I")


def test_place_rejects_already_filled_cells():
    board = Board.from_strings(["X..."])
    with pytest.raises(ValueError, match="already filled"):
        board.place([(0, 0)], "I")


class TestClearLines:
    def test_no_full_rows_is_a_no_op(self):
        board = Board.from_strings(["....", "XX.."])
        cleared_board, count = board.clear_lines()
        assert count == 0
        assert cleared_board is board

    def test_single_full_row_is_removed(self):
        board = Board.from_strings(["....", "X...", "XXXX"])
        cleared_board, count = board.clear_lines()
        assert count == 1
        assert cleared_board.rows == ("....", "....", "X...")

    def test_four_full_rows_are_removed_at_once(self):
        board = Board.from_strings(["....", "XXXX", "XXXX", "XXXX", "XXXX"])
        cleared_board, count = board.clear_lines()
        assert count == 4
        assert cleared_board.rows == ("....",) * 5

    def test_surviving_rows_keep_their_order(self):
        board = Board.from_strings(["A...", "XXXX", "B...", "XXXX", "C..."])
        cleared_board, count = board.clear_lines()
        assert count == 2
        assert cleared_board.rows == ("....", "....", "A...", "B...", "C...")

    def test_height_is_preserved(self):
        board = Board.from_strings(["....", "XXXX"])
        cleared_board, _ = board.clear_lines()
        assert cleared_board.height == board.height


def test_column_heights_measures_from_the_floor():
    board = Board.from_strings(
        [
            "...X",
            ".X.X",
            "XX.X",
        ]
    )
    # column 0 tops out in the bottom row, column 3 reaches the ceiling,
    # column 2 is empty.
    assert board.column_heights() == (1, 2, 0, 3)


def test_column_heights_ignores_holes_underneath():
    """Height is the top of the column, so a buried gap does not reduce it."""
    board = Board.from_strings(["X", ".", "X"])
    assert board.column_heights() == (3,)


def test_occupancy_drops_piece_identity():
    board = Board.from_strings(["I.", "OZ"])
    assert board.occupancy() == ((True, False), (True, True))


def test_str_renders_rows_on_separate_lines():
    board = Board.from_strings(["..", "XX"])
    assert str(board) == "..\nXX"


def test_boards_are_hashable_so_states_can_be_snapshotted():
    assert hash(Board.empty(4, 4)) == hash(Board.empty(4, 4))
